#!/usr/bin/env node
// Offline-only asset install. Run on the experimental branch from repo root.
// Usage: node scripts/install-eqe-official-icon.mjs /path/to/eqe_icons_official
// NO deploy, NO D1 changes, NO network.
import {readFile,copyFile,writeFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import path from 'node:path';
const source=process.argv[2];
if(!source)throw Error('Provide official icons directory');
const names=['apple-touch-icon.png','premium-icon-180.png','premium-icon-192.png','premium-icon-512.png','premium-icon-maskable-512.png'];
const expected={
'apple-touch-icon.png':'df01cfe72fa75587ca66e1fc822e8143c09e3d78',
'premium-icon-180.png':'df01cfe72fa75587ca66e1fc822e8143c09e3d78',
'premium-icon-192.png':'4c1d516bf57fb0b0999b42df9a9e971091260d03',
'premium-icon-512.png':'626a7017622927491b800c76f9ff58ae6e4a23b4',
'premium-icon-maskable-512.png':'626a7017622927491b800c76f9ff58ae6e4a23b4'
};
for(const name of names){
 const buf=await readFile(path.join(source,name));
 const hash=createHash('sha1').update(Buffer.from('blob '+buf.length+'\\0')).update(buf).digest('hex');
 if(hash!==expected[name])throw Error('Icon hash mismatch: '+name);
}
const manifestPath='public/manifest.webmanifest';
const indexPath='public/index.html';
const swPath='public/sw.js';
let manifest=JSON.parse(await readFile(manifestPath,'utf8'));
let html=await readFile(indexPath,'utf8'),sw=await readFile(swPath,'utf8');
if(!html.includes('apple-touch-icon.png')||!sw.includes('premium-icon-192.png'))throw Error('Unexpected PWA layout');
const version=Number((await readFile('public/version.json','utf8') && JSON.parse(await readFile('public/version.json','utf8')).version));
if(!Number.isInteger(version))throw Error('Invalid version');
const next=version+1;
for(const name of names) await copyFile(path.join(source,name),path.join('public',name));
for(const icon of manifest.icons||[])icon.src=icon.src.replace(/\\?v=\\d+/,'?v='+next);
await writeFile(manifestPath,JSON.stringify(manifest,null,2)+'\\n');
html=html.replace(/(manifest\\.webmanifest\\?v=)\\d+/g,'$1'+next).replace(/(apple-touch-icon\\.png\\?v=)\\d+/g,'$1'+next)
 .replace(/(premium-icon-(?:192|512)\\.png\\?v=)\\d+/g,'$1'+next)
 .replace(/const APP_VERSION=\\d+;/,'const APP_VERSION='+next+';')
 .replace(/(sw\\.js\\?v=)\\d+/g,'$1'+next);
await writeFile(indexPath,html);
sw=sw.replace(/const CACHE='quinto-elemento-v\\d+';/,`const CACHE='quinto-elemento-v${next}';`)
 .replace(/(manifest\\.webmanifest\\?v=)\\d+/g,'$1'+next)
 .replace(/(premium-icon-(?:180|192|512|maskable-512)\\.png\\?v=)\\d+/g,'$1'+next);
await writeFile(swPath,sw);
await writeFile('public/version.json',JSON.stringify({version:next},null,2)+'\\n');
console.log('Official EQE icons staged. Version',next,'- DO NOT DEPLOY until regression tests pass.');
