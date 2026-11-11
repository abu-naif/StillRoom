import {readFileSync} from 'node:fs';
import {transformSync} from 'esbuild';
import assert from 'node:assert/strict';
import {test} from 'node:test';
// Exercise the same helpers that the player, note storage and export use.
const source=readFileSync(new URL('../src/App.tsx',import.meta.url),'utf8');
const helpers=source.slice(source.indexOf('export type Video'),source.indexOf('export default function'));
const {parseVideo,videoUrl,noteKey}=await import('data:text/javascript;base64,'+Buffer.from(transformSync(helpers,{loader:'ts',format:'esm'}).code).toString('base64'));
test('Drive sharing, preview and legacy links use the preview player',()=>{
 for(const link of ['https://drive.google.com/file/d/abc_123-test/view?usp=sharing','drive.google.com/file/d/abc_123-test/preview','https://drive.google.com/open?id=abc_123-test','https://drive.google.com/uc?id=abc_123-test']){
  const video=parseVideo(link);
  assert.equal(video.provider,'drive');
  assert.equal(videoUrl(video,true),'https://drive.google.com/file/d/abc_123-test/preview');
  assert.equal(videoUrl(video),'https://drive.google.com/file/d/abc_123-test/view');
 }
});
test('resource keys survive embedding and export',()=>{
 const video=parseVideo('https://drive.google.com/file/d/abc/view?resourcekey=0-test');
 assert.equal(new URL(videoUrl(video,true)).searchParams.get('resourcekey'),'0-test');
 assert.equal(new URL(videoUrl(video)).searchParams.get('resourcekey'),'0-test');
});
test('YouTube links, timestamps and existing note keys remain supported',()=>{
 for(const link of ['https://youtu.be/dQw4w9WgXcQ?t=1m30s','https://youtube.com/watch?v=dQw4w9WgXcQ&start=90','https://youtube.com/shorts/dQw4w9WgXcQ?t=90']){
 const video=parseVideo(link);
 assert.equal(video.provider,'youtube');assert.equal(video.start,90);
 assert.equal(noteKey(video),'stillroom-note-dQw4w9WgXcQ');
 assert.match(videoUrl(video,true),/start=90$/);
 }
 assert.equal(parseVideo('dQw4w9WgXcQ').provider,'youtube');
 assert.notEqual(noteKey(parseVideo('dQw4w9WgXcQ')),noteKey(parseVideo('https://drive.google.com/file/d/dQw4w9WgXcQ/view')));
});
test('rejects folders, unsupported hosts and malformed links',()=>{
 for(const link of ['', 'https://drive.google.com/drive/folders/abc','https://drive.google.com/open','https://drive.google.com.evil.test/file/d/abc/view','https://example.com/watch?v=dQw4w9WgXcQ','https://drive.google.com/file/d/abc/other','javascript:alert(1)'])assert.equal(parseVideo(link),null,link);
});
