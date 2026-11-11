import {readFileSync} from 'node:fs';
import vm from 'node:vm';
import assert from 'node:assert/strict';
import {test} from 'node:test';
const handlers={};
const removed=[];
vm.runInNewContext(readFileSync(new URL('../sw.js',import.meta.url),'utf8'),{
 self:{location:{origin:'https://stillroom.test'},clients:{claim:()=>Promise.resolve()},skipWaiting:()=>Promise.resolve(),addEventListener:(name,handler)=>{handlers[name]=handler}},
 URL,Response,
 caches:{keys:async()=>['stillroom-shell-old','another-app-cache'],delete:async name=>{removed.push(name)},open:async()=>({addAll:async()=>{},put:async()=>{}}),match:async()=>undefined},
 fetch:async()=>new Response('app shell')
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
