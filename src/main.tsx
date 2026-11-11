import React from 'react';
import {createRoot} from 'react-dom/client';
import App from './App';
createRoot(document.getElementById('root')!).render(<App/>);

if('serviceWorker' in navigator&&window.isSecureContext){
 window.addEventListener('load',()=>{navigator.serviceWorker.register('/sw.js').catch(()=>{/* The app still runs without offline installation support. */})});
}
