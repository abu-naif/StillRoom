import {readFileSync} from 'node:fs';
import {transformSync} from 'esbuild';
import assert from 'node:assert/strict';
import {test} from 'node:test';
const source=readFileSync(new URL('../src/api.ts',import.meta.url),'utf8');
const {api,ConnectionError}=await import('data:text/javascript;base64,'+Buffer.from(transformSync(source,{loader:'ts',format:'esm'}).code).toString('base64'));
test('network recovery retries reads and preserves send idempotency keys',async()=>{
 const original=globalThis.fetch;
 try{
  const calls=[];
  globalThis.fetch=async(url,options)=>{calls.push(options);if(calls.length===1)throw new TypeError('Failed to fetch');return Response.json({id:12})};
  assert.deepEqual(await api('messages/send',{client_id:'stable-message-id',text:'hello'}),{id:12});
  assert.equal(calls.length,2);assert.equal(calls[0].body,calls[1].body);
  assert.equal(calls[1].cache,'no-store');
 }finally{globalThis.fetch=original}
});
test('unsafe mutations are never automatically replayed and connection failures are readable',async()=>{
 const original=globalThis.fetch;let count=0;
 try{globalThis.fetch=async()=>{count++;throw new TypeError('Failed to fetch')};
  await assert.rejects(api('friends/request',{username:'friend'}),ConnectionError);assert.equal(count,1);
 }finally{globalThis.fetch=original}
});
test('authentication and validation errors are not retried',async()=>{
 const original=globalThis.fetch,originalWindow=globalThis.window;let calls=0,expired=0;
 try{globalThis.window={dispatchEvent:()=>expired++};globalThis.fetch=async()=>{calls++;return Response.json({error:'Sign in again.'},{status:401})};
  await assert.rejects(api('social'),/Sign in again/);assert.equal(calls,1);assert.equal(expired,1);
 }finally{globalThis.fetch=original;globalThis.window=originalWindow}
});
test('proxy failures recover while malformed responses have a clear error',async()=>{
 const original=globalThis.fetch;let count=0;
 try{globalThis.fetch=async()=>++count===1?new Response('Bad gateway',{status:502}):Response.json({ok:true});
  assert.deepEqual(await api('social'),{ok:true});assert.equal(count,2);
  globalThis.fetch=async()=>new Response('<html>proxy</html>');await assert.rejects(api('social'),/invalid response/);
 }finally{globalThis.fetch=original}
});
test('read retries stop after a second network failure',async()=>{
 const original=globalThis.fetch;let calls=0;
 try{globalThis.fetch=async()=>{calls++;throw new TypeError('Failed to fetch')};
  await assert.rejects(api('social'),ConnectionError);assert.equal(calls,2);
 }finally{globalThis.fetch=original}
});
