import {readFile,writeFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import {build} from 'esbuild';
await build({entryPoints:['src/main.tsx'],bundle:true,minify:true,jsx:'automatic',outfile:'app.js',define:{'process.env.NODE_ENV':'"production"'},target:['es2020'],legalComments:'linked'});
const version=createHash('sha256');
for(const file of ['app.js','styles.css','index.html','manifest.webmanifest','src/sw.js','icons/icon-192.png','icons/icon-512.png','icons/apple-touch-icon.png','icons/notification-badge.png'])version.update(await readFile(file));
await writeFile('sw.js',(await readFile('src/sw.js','utf8')).replaceAll('__STILLROOM_VERSION__',version.digest('hex').slice(0,16)));
console.log('Built app.js and sw.js. Run python3 start.py to open Stillroom.');
