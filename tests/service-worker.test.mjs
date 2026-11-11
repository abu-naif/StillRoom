import {readFileSync} from 'node:fs';
import vm from 'node:vm';
import assert from 'node:assert/strict';
import {test} from 'node:test';
const handlers={};
const removed=[],shown=[],opened=[];
let pushResponse={allowed:true,title:'Stillroom',body:'A new message',peer:7,tag:'stillroom-message-7'},offline=false;
vm.runInNewContext(readFileSync(new URL('../sw.js',import.meta.url),'utf8'),{
 self:{registration:{showNotification:async(title,options)=>{shown.push({title,...options})}},location:{origin:'https://stillroom.test'},clients:{claim:()=>Promise.resolve(),matchAll:async()=>[],openWindow:async url=>{opened.push(url)}},skipWaiting:()=>Promise.resolve(),addEventListener:(name,handler)=>{handlers[name]=handler}},
 URL,Response,

 caches:{keys:async()=>['stillroom-shell-old','another-app-cache'],delete:async name=>{removed.push(name)},open:async()=>({addAll:async()=>{},put:async()=>{}}),match:async()=>undefined},
 fetch:async path=>{if(offline)throw new Error('offline');return String(path).startsWith('/api/push/check')?new Response(JSON.stringify(pushResponse),{headers:{'Content-Type':'application/json'}}):new Response('app shell')}
});
test('account APIs, chat attachments, and external content never enter offline caching',()=>{
 for(const url of ['/api/me','/api/history','/api/notifications','/api/messages?peer=1','/api/attachments/123','https://www.youtube.com/embed/test']){
  let intercepted=false;handlers.fetch({request:{url:new URL(url,'https://stillroom.test').href,method:'GET'},respondWith:()=>{intercepted=true}});assert.equal(intercepted,false,url);
 }
});
test('public app shell is available through the service worker',async()=>{
 let result;handlers.fetch({request:{url:'https://stillroom.test/index.html',method:'GET'},respondWith:promise=>{result=promise},waitUntil:()=>{}});
 assert.equal(await (await result).text(),'app shell');
});
test('updates only remove Stillroom app shell caches',async()=>{
 let work;handlers.activate({waitUntil:promise=>{work=promise}});await work;assert.deepEqual(removed,['stillroom-shell-old']);
});

test('push checks current permission before showing a device notification',async()=>{
 let work;
 const event={data:{json:()=>({event:'opaque-event-token'})},waitUntil:promise=>{work=promise}};
 handlers.push(event);await work;
 assert.equal(shown.length,1);
 assert.equal(shown[0].data.peer,7);
 pushResponse={allowed:false};
 handlers.push(event);await work;
 assert.equal(shown.length,1);
 offline=true;
 handlers.push(event);await work;
 assert.equal(shown.length,1);
 offline=false;
});
test('notification clicks open only a same-origin chat URL',async()=>{
 let work,closed=false;
 handlers.notificationclick({notification:{data:{peer:7},close:()=>{closed=true}},waitUntil:promise=>{work=promise}});
 await work;assert.equal(closed,true);assert.equal(opened[0],'/?chat=7#messages');
});
