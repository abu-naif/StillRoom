import {test} from 'node:test';
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
import {pathToFileURL} from 'node:url';
import {build} from 'esbuild';
import React from 'react';
import {renderToString} from 'react-dom/server';
const require=createRequire(import.meta.url);
test('signed-in chat renders on first load without initialization errors',async()=>{
 const result=await build({entryPoints:['src/Chat.tsx'],bundle:true,write:false,platform:'node',format:'esm',jsx:'automatic',plugins:[{name:'shared-react',setup(build){build.onResolve({filter:/^[^./]/},args=>({path:pathToFileURL(require.resolve(args.path)).href,external:true}))}}]});
 const {default:Chat}=await import('data:text/javascript;base64,'+Buffer.from(result.outputFiles[0].text).toString('base64'));
 globalThis.window={isSecureContext:false};
 globalThis.matchMedia=()=>({matches:false});
 try{
 const html=renderToString(React.createElement(Chat,{username:'alice',visible:false,onClose:()=>{},onConversationChange:()=>{},requestedPeer:null,notifications:{enabled:true,requests:[],conversations:[],total:0}}));
 assert.match(html,/Add by username/);
 assert.match(html,/username-suggestions/);
 }finally{delete globalThis.matchMedia;delete globalThis.window}
});
