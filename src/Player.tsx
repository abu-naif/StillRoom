import {useEffect,useRef} from 'react';
import type {Video} from './App';
import {videoUrl} from './App';
let apiReady:Promise<any>|undefined;
function youtubeAPI(){
 if((window as any).YT?.Player)return Promise.resolve((window as any).YT);
 if(!apiReady)apiReady=new Promise((resolve,reject)=>{
  (window as any).onYouTubeIframeAPIReady=()=>resolve((window as any).YT);
  const script=document.createElement('script');script.src='https://www.youtube.com/iframe_api';
  script.onerror=()=>{apiReady=undefined;reject(new Error('YouTube controls could not load. Progress cannot be saved.'));};
  document.head.appendChild(script);
 });
 return apiReady;
}
export default function Player({video,onProgress,onError}:{video:Video;onProgress:(position:number,title?:string)=>void;onError:(message:string)=>void}){
 const mount=useRef<HTMLDivElement>(null);
 const progress=useRef(onProgress);progress.current=onProgress;
 const reportError=useRef(onError);reportError.current=onError;
 useEffect(()=>{
  if(video.provider!=='youtube')return;
  let disposed=false,player:any,interval:ReturnType<typeof setInterval>,started=false;
  function save(){
   if(!started||!player?.getCurrentTime)return;
   const position=player.getPlayerState()===0?0:player.getCurrentTime();
   progress.current(position,player.getVideoData?.().title);
  }
  youtubeAPI().then(YT=>{
   if(disposed||!mount.current)return;
   const target=document.createElement('div');mount.current.appendChild(target);
   player=new YT.Player(target,{host:'https://www.youtube-nocookie.com',videoId:video.id,
    playerVars:{start:Math.floor(video.start),rel:0,playsinline:1,origin:location.origin},
    events:{onReady:()=>{interval=setInterval(save,5000)},onStateChange:(event:any)=>{if(event.data===1)started=true;save()},onError:()=>reportError.current('YouTube could not play this video. It may be unavailable or embedding may be disabled.')}});
  }).catch(error=>reportError.current(error.message));
  const hidden=()=>{if(document.hidden)save()};
  document.addEventListener('visibilitychange',hidden);window.addEventListener('pagehide',save);window.addEventListener('flush-player',save);
  return()=>{save();disposed=true;clearInterval(interval);document.removeEventListener('visibilitychange',hidden);window.removeEventListener('pagehide',save);window.removeEventListener('flush-player',save);player?.destroy();};
 },[video]);
 return video.provider==='drive'?<iframe title="Your selected Google Drive video" src={videoUrl(video,true)} allow="autoplay; encrypted-media; fullscreen; picture-in-picture" allowFullScreen referrerPolicy="strict-origin-when-cross-origin"/>:<div className="youtube-player" ref={mount}/>;
}
