import React,{useEffect,useState} from 'react';
import {createRoot} from 'react-dom/client';
import App from './App';
function AppUpdate(){
 const [available,setAvailable]=useState(false);
 useEffect(()=>{
  if(!('serviceWorker' in navigator)||!window.isSecureContext)return;
  let controlled=!!navigator.serviceWorker.controller;
  let registration:ServiceWorkerRegistration|undefined;
  let lastCheck=0;
  const changed=()=>{if(controlled)setAvailable(true);controlled=true};
  const check=()=>{if(!document.hidden&&registration&&Date.now()-lastCheck>60000){lastCheck=Date.now();registration.update().catch(()=>{})}};
  navigator.serviceWorker.addEventListener('controllerchange',changed);
  navigator.serviceWorker.register('/sw.js',{updateViaCache:'none'}).then(value=>{registration=value;check()}).catch(()=>{});
  document.addEventListener('visibilitychange',check);
  window.addEventListener('online',check);
  return()=>{navigator.serviceWorker.removeEventListener('controllerchange',changed);document.removeEventListener('visibilitychange',check);window.removeEventListener('online',check)};
 },[]);
 return available?<div className="app-update" role="status"><span>A Stillroom update is ready. Save any draft before refreshing.</span><button type="button" onClick={()=>location.reload()}>Refresh app</button></div>:null;
}
createRoot(document.getElementById('root')!).render(<><App/><AppUpdate/></>);
