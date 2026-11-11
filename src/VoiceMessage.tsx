import {useEffect,useRef,useState} from 'react';
import {Mic,Pause,Play} from 'lucide-react';

function timestamp(seconds:number){const value=Number.isFinite(seconds)?Math.max(0,Math.floor(seconds)):0;return `${Math.floor(value/60)}:${String(value%60).padStart(2,'0')}`}
export default function VoiceMessage({src,active=true,label='Voice message',durationHint=0}:{src:string;active?:boolean;label?:string;durationHint?:number}){
 const audio=useRef<HTMLAudioElement>(null);
 const [playing,setPlaying]=useState(false),[position,setPosition]=useState(0),[duration,setDuration]=useState(durationHint),[rate,setRate]=useState(1),[error,setError]=useState(''),[loading,setLoading]=useState(false);
 const durationRef=useRef(durationHint);
 function metadata(){const element=audio.current;if(!element)return;let length=Number.isFinite(element.duration)?element.duration:durationHint;if(!length&&element.seekable.length)length=element.seekable.end(element.seekable.length-1);if(Number.isFinite(length)&&length>0){durationRef.current=length;setDuration(length)}}
 useEffect(()=>{const element=audio.current;const pauseOther=(event:Event)=>{if((event as CustomEvent).detail!==audio.current)audio.current?.pause()};window.addEventListener('stillroom-audio-play',pauseOther);return()=>{window.removeEventListener('stillroom-audio-play',pauseOther);element?.pause()}},[]);
 useEffect(()=>{if(!active)audio.current?.pause()},[active]);
 async function toggle(){const element=audio.current;if(!element)return;if(!element.paused){element.pause();return}setError('');setLoading(true);try{await element.play()}catch{setError('Could not play this voice message. Please try again.')}finally{setLoading(false)}}
 function speed(){const next=rate===1?1.5:rate===1.5?2:1;setRate(next);if(audio.current)audio.current.playbackRate=next}
 return <div className="voice-message" role="group" aria-label={label}>
  <audio ref={audio} src={src} preload="metadata" onLoadedMetadata={metadata} onDurationChange={metadata} onProgress={metadata} onTimeUpdate={()=>{setPosition(audio.current?.currentTime||0);metadata()}} onPlay={()=>{window.dispatchEvent(new CustomEvent('stillroom-audio-play',{detail:audio.current}));setPlaying(true)}} onPause={()=>setPlaying(false)} onEnded={()=>{const element=audio.current;if(element){if(!durationRef.current){durationRef.current=element.currentTime;setDuration(element.currentTime)}element.currentTime=0}setPosition(0);setPlaying(false)}} onError={()=>{setLoading(false);setError('Could not load this voice message. Please try again.')}}/>
  <span className="voice-avatar" aria-hidden="true"><Mic size={19}/></span>
  <button type="button" className="voice-play" aria-label={playing?'Pause voice message':'Play voice message'} disabled={loading} onClick={toggle}>{playing?<Pause size={19} fill="currentColor"/>:<Play size={19} fill="currentColor"/>}</button>
  <div className="voice-timeline"><input type="range" aria-label="Voice message position" min={0} max={duration||1} step="0.1" value={Math.min(position,duration||1)} disabled={!duration} onChange={event=>{const value=Number(event.target.value);if(audio.current){audio.current.currentTime=value;setPosition(value)}}}/><div><span>{loading?'Loading…':(duration||position?timestamp(position>0?position:duration):'—:—')}</span><span className="voice-label">{label}</span></div></div>
  <button type="button" className="voice-speed" aria-label={`Playback speed ${rate} times. Change speed`} onClick={speed}>{rate}×</button>
  {error&&<span className="voice-error" role="alert">{error}</span>}
 </div>;
}
