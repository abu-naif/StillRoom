import {build} from 'esbuild';
await build({entryPoints:['src/main.tsx'],bundle:true,minify:true,jsx:'automatic',outfile:'app.js',define:{'process.env.NODE_ENV':'"production"'},target:['es2020'],legalComments:'linked'});
console.log('Built app.js. Run python3 start.py to open Stillroom.');
