import {useEffect,useRef,useState} from 'react';
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
function DrivePlayer({video,onProgress}:{video:Video;onProgress:(position:number)=>void}){
 const media=useRef<HTMLVideoElement>(null),lastSaved=useRef(-1),started=useRef(false);
 const [fallback,setFallback]=useState(false),[resume,setResume]=useState(video.start>0);
 function save(force=false){const player=media.current;if(!player||!started.current)return;const position=player.ended?0:player.currentTime;if(Number.isFinite(position)&&(force||Math.abs(position-lastSaved.current)>=5)){lastSaved.current=position;onProgress(position)}}
 const saveRef=useRef(save);saveRef.current=save;
 useEffect(()=>{const flush=()=>saveRef.current(true);const hidden=()=>{if(document.hidden)flush()};window.addEventListener('flush-player',flush);window.addEventListener('pagehide',flush);document.addEventListener('visibilitychange',hidden);return()=>{flush();window.removeEventListener('flush-player',flush);window.removeEventListener('pagehide',flush);document.removeEventListener('visibilitychange',hidden)}},[]);
 const source=new URL('https://drive.google.com/uc');source.searchParams.set('export','download');source.searchParams.set('id',video.id);if(video.resourceKey)source.searchParams.set('resourcekey',video.resourceKey);
 return <div className="drive-player">{fallback?<><iframe title="Your selected Google Drive video" src={videoUrl(video,true)} allow="autoplay; encrypted-media; fullscreen; picture-in-picture" allowFullScreen referrerPolicy="strict-origin-when-cross-origin"/><p className="drive-status">This file requires Drive preview. Automatic bookmarks are unavailable in preview; use Remember timestamp below.</p></>:<><video ref={media} src={source.href} controls playsInline preload="metadata" onError={()=>setFallback(true)} onPlay={()=>{started.current=true;setResume(false)}} onTimeUpdate={()=>save()} onPause={()=>save(true)} onSeeked={()=>save(true)} onEnded={()=>save(true)}/>{resume&&<div className="drive-resume"><span>Saved at {Math.floor(video.start/60)}:{String(Math.floor(video.start)%60).padStart(2,'0')}</span><button onClick={()=>{const player=media.current;if(player){player.currentTime=video.start;setResume(false);player.play().catch(()=>{})}}}>Continue from where I left</button><button onClick={()=>{if(media.current)media.current.currentTime=0;setResume(false)}}>Start from beginning</button></div>}<button className="drive-fallback" onClick={()=>{save(true);media.current?.pause();setFallback(true)}}>Use Drive preview</button></>}</div>;
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
 return video.provider==='drive'?<DrivePlayer video={video} onProgress={onProgress}/>:<div className="youtube-player" ref={mount}/>;
}
