const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const html=fs.readFileSync('public/index.html','utf8'),sw=fs.readFileSync('public/sw.js','utf8');
let count=0;
for(const m of html.matchAll(/<script\b([^>]*)>([\s\S]*?)<\/script\s*>/gi)){
 if(/\bsrc\s*=/.test(m[1]))continue;new vm.Script(m[2]);count++;
}
assert.equal(count,25);console.log('PASS '+count+' inline scripts compile, including Pases and clipboard');
require('./test-pwa-version.cjs');
const v=JSON.parse(fs.readFileSync('public/version.json')).version;
assert.ok(html.includes('<span class="uiVersion">v'+v+'</span>'));
assert.ok(html.includes("el.textContent='v'+APP_VERSION"));assert.ok(html.includes('buildVersion:APP_VERSION'));
console.log('PASS displayed and exported build version use loaded APP_VERSION');
for(const name of ['sync-client','sync-merge']){assert.ok(html.includes(name+'.js?v='+v));assert.ok(sw.includes(name+'.js?v='+v));new vm.Script(fs.readFileSync('public/'+name+'.js','utf8'))}
assert.ok(!html.includes("var META_DIRTY='qeSync.dirty'"));console.log('PASS only one sync engine and versioned offline modules');
const events={},deleted=[];
const caches={keys:async()=>['unrelated-cache','quinto-elemento-v82','quinto-elemento-v'+v],delete:async k=>deleted.push(k)};
vm.runInNewContext(sw,{self:{addEventListener:(k,f)=>events[k]=f,clients:{claim:async()=>{}},skipWaiting(){}},caches,URL,Promise,setTimeout,clearTimeout});
(async()=>{let p;events.activate({waitUntil:x=>p=x});await p;assert.deepEqual(deleted,['quinto-elemento-v82']);console.log('PASS activation preserves unrelated and current caches')})().catch(e=>{console.error(e);process.exitCode=1});
