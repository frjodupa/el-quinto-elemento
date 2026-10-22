const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const M=require('../public/sync-merge.js');
const P='quintoElemento.';
const lyric=i=>P+'lyrics.v1.'+i,chord=i=>P+'chords.v2.'+i;
let total=0;
function check(name,f){f();total++;console.log('PASS '+name)}
const song=(i,text)=>({[lyric(i)]:text,[chord(i)]:JSON.stringify({words:{'0:0':'DO'},lines:{}})});
check('independent song edits merge across devices',()=>{
 const base={...song(0,'ORIGINAL'),...song(1,'ORIGINAL')};
 const local={...base,[lyric(0)]:'IPAD'},remote={...base,[lyric(1)]:'MAC'};
 const r=M.merge(base,local,remote,71);assert.equal(r.conflicts.length,0);assert.equal(r.data[lyric(0)],'IPAD');assert.equal(r.data[lyric(1)],'MAC');
});
check('lyrics and chord coordinates stay atomic',()=>{
 const base=song(0,'ONE LINE'),local={...base,[lyric(0)]:'TWO\nLINES'},remote={...base,[chord(0)]:'{"words":{"0:0":"SOL"}}'};
 const r=M.merge(base,local,remote,71);assert.equal(r.data,null);assert.equal(r.conflicts[0].id,'song:0');assert.equal(r.conflicts[0].local[lyric(0)],'TWO\nLINES');
});
check('first upgrade does not guess which legacy song wins',()=>{assert.equal(M.merge(null,song(0,'IPAD'),song(0,'CLOUD'),71).conflicts.length,1)});
check('first upgrade accepts remote-only song',()=>{const r=M.merge(null,{},song(0,'CLOUD'),71);assert.equal(r.data[lyric(0)],'CLOUD')});
check('literal lyrics preserve quotes, null and numeric-looking text',()=>{for(const text of ['"HOLA"','null','1.00'])assert.equal(M.merge({},song(0,text),{},71).data[lyric(0)],text)});
check('JSON property ordering is not a conflict',()=>{assert.equal(M.merge(null,{[chord(0)]:'{"lines":{},"words":{}}'},{[chord(0)]:'{"words":{},"lines":{}}'},71).conflicts.length,0)});
check('delete propagates only from known baseline',()=>{assert.equal(M.merge(song(0,'X'),{},song(0,'X'),71).data[lyric(0)],undefined)});
check('delete versus edit is retained as conflict',()=>{assert.equal(M.merge(song(0,'X'),{},song(0,'Y'),71).conflicts.length,1)});
check('explicit resolution preserves complete selected song',()=>{const l=song(0,'IPAD'),r=song(0,'CLOUD');assert.deepEqual(M.merge(null,l,r,71,{'song:0':'local'}).data,l)});
check('two simultaneous additions cannot overwrite the same song id',()=>{
 const k=P+'customSongs.v1',b={[k]:'[]'},l={[k]:'[{"title":"A","text":"A"}]'},r={[k]:'[{"title":"B","text":"B"}]'};
 assert.equal(M.merge(b,l,r,71).conflicts[0].id,'catalogue');
});
check('catalogue collision never attaches a pass to another song',()=>{
 const k=P+'customSongs.v1',p=P+'passes.v1',b={[k]:'[]'},l={[k]:'[{"title":"A","text":"A"}]',[p]:'[{"id":"only-local","songs":[71]}]'},r={[k]:'[{"title":"B","text":"B"}]'};
 const x=M.merge(b,l,r,71,{catalogue:'remote'});assert.equal(x.data[p],undefined);assert.equal(JSON.parse(x.data[k])[0].title,'B');
});
check('pass edit and unrelated song edit combine',()=>{
 const k=P+'passes.v1',pass={id:'a',name:'PASE',songs:[0]},b={...song(0,'A'),[k]:JSON.stringify([pass])};
 const l={...b,[lyric(0)]:'B'},r={...b,[k]:JSON.stringify([{...pass,name:'NOMBRE'}])};
 const x=M.merge(b,l,r,71);assert.equal(JSON.parse(x.data[k])[0].name,'NOMBRE');assert.equal(x.data[lyric(0)],'B');
});
check('pass reorders conflict rather than silently combining',()=>{
 const k=P+'passes.v1',s=arr=>({[k]:JSON.stringify([{id:'a',songs:arr}])});assert.equal(M.merge(s([0,1]),s([1,0]),s([0,2]),71).conflicts.length,1);
});
check('invalid references cannot be uploaded',()=>{assert.throws(()=>M.merge({}, {[P+'passes.v1']:'[{"id":"a","songs":[999]}]'}, {},71),/referencia/)});

function device(server){
 class Storage {constructor(){this.map=new Map()}get length(){return this.map.size}key(i){return Array.from(this.map.keys())[i]||null}getItem(k){return this.map.has(k)?this.map.get(k):null}setItem(k,v){this.map.set(k,String(v))}removeItem(k){this.map.delete(k)}}
 const localStorage=new Storage(),listeners={},elements=new Map(),errors=[];let editing=false;
 function node(){return {children:[],textContent:'',disabled:false,appendChild(n){this.children.push(n)},replaceChildren(){this.children=[]},remove(){},click(){},setAttribute(){},classList:{contains(){return false}},parentNode:{appendChild(){}},};}
 const document={hidden:false,activeElement:null,body:node(),getElementById(id){if(!elements.has(id))elements.set(id,node());return elements.get(id)},createElement(){return node()},querySelector(){return editing?{}:null},addEventListener(){}};
 const ctx={console:{error(...args){errors.push(args)}},Storage,localStorage,document,navigator:{onLine:true},setTimeout(){return 1},clearTimeout(){},setInterval(){return 1},AbortController,Blob,URL,CustomEvent:class{},baseSongCount:71,APP_VERSION:98,customSongs:[],songs:Array.from({length:71},()=>({title:'SONG'})),render(){},loadCustomSongs(){return JSON.parse(localStorage.getItem(P+'customSongs.v1')||'[]')},normalizeMasterTitle:s=>s,normalizeMasterText:s=>s,getSongTitle:i=>'SONG '+i};
 ctx.window={EQESyncMerge:M,addEventListener(k,f){(listeners[k]||(listeners[k]=[])).push(f)},dispatchEvent(){}};
 ctx.fetch=async(url,options)=>{
   if(options.method==='GET')return {ok:true,json:async()=>({data:structuredClone(server.data),updatedAt:server.ts})};
   const b=JSON.parse(options.body);if(server.beforePut){const fn=server.beforePut;server.beforePut=null;fn()}
   if(b.expectedUpdatedAt!==server.ts)return {ok:false,status:409,json:async()=>({error:'STALE_SNAPSHOT'})};
   server.data=structuredClone(b.data);server.ts++;server.puts++;return {ok:true,json:async()=>({updatedAt:server.ts})};
 };
 vm.createContext(ctx);vm.runInContext(fs.readFileSync('public/sync-client.js','utf8'),ctx);
 return {ctx,errors,storage:localStorage,online(v){ctx.navigator.onLine=v},editing(v){editing=v},sync:()=>ctx.window.eqeSyncNow(),state(){const s={};for(const[k,v]of localStorage.map)if(k.startsWith(P))s[k]=v;return s},status(){return elements.get('cloudSyncStatus')?.textContent}};
}
(async()=>{
 const server={data:{...song(0,'A'),...song(1,'B'),...song(2,'C')},ts:100,puts:0};
 const ipad=device(server),mac=device(server),iphone=device(server);
 await ipad.sync();await mac.sync();await iphone.sync();
 assert.equal(ipad.state()[lyric(0)],'A');total++;console.log('PASS new device downloads shared state');
 const parallel=device(server);await Promise.all([parallel.sync(),parallel.sync()]);assert.equal(parallel.status(),'☁ Sincronizado');assert.equal(parallel.errors.length,0);total++;console.log('PASS overlapping sync callers await reconciliation');
 ipad.storage.setItem(lyric(0),'IPAD');mac.storage.setItem(lyric(1),'MAC');iphone.storage.setItem(lyric(2),'IPHONE');
 await ipad.sync();await mac.sync();await iphone.sync();await ipad.sync();await mac.sync();
 for(const d of [ipad,mac,iphone]){assert.deepEqual(d.state(),server.data);assert.equal(d.status(),'☁ Sincronizado');assert.equal(d.errors.length,0)}
 assert.equal(server.data[lyric(0)],'IPAD');assert.equal(server.data[lyric(1)],'MAC');assert.equal(server.data[lyric(2)],'IPHONE');total++;console.log('PASS iPad/Mac/iPhone converge after independent edits');
 ipad.online(false);ipad.storage.setItem(lyric(0),'OFFLINE');await ipad.sync();assert.equal(server.data[lyric(0)],'IPAD');ipad.online(true);await ipad.sync();assert.equal(server.data[lyric(0)],'OFFLINE');total++;console.log('PASS offline edits upload on reconnection');
 await mac.sync();ipad.storage.setItem(lyric(0),'ONE');mac.storage.setItem(lyric(0),'TWO');await ipad.sync();const puts=server.puts;await mac.sync();assert.equal(server.puts,puts);assert.equal(mac.state()[lyric(0)],'TWO');assert.ok(mac.storage.getItem('qeSync.conflicts.v2'));total++;console.log('PASS simultaneous same-song edit retains both without writing');
 const late=device(server);await late.sync();late.storage.setItem(lyric(1),'CAPTURED');server.beforePut=()=>late.storage.setItem(lyric(1),'WHILE UPLOADING');await late.sync();assert.equal(late.state()[lyric(1)],'WHILE UPLOADING');assert.equal(late.storage.getItem('qeSync.dirty'),'1');await late.sync();assert.equal(server.data[lyric(1)],'WHILE UPLOADING');total++;console.log('PASS edits during upload remain pending and then sync');
 const race=device(server);await race.sync();race.storage.setItem(lyric(2),'RACE');server.beforePut=()=>{server.data[lyric(1)]='OTHER DEVICE';server.ts++};await race.sync();assert.equal(server.data[lyric(1)],'OTHER DEVICE');assert.equal(server.data[lyric(2)],'RACE');total++;console.log('PASS CAS conflict refetches and combines without lost update');
 const editor=device(server);await editor.sync();editor.editing(true);server.data[lyric(2)]='REMOTE WHILE EDITING';server.ts++;await editor.sync();assert.notEqual(editor.state()[lyric(2)],'REMOTE WHILE EDITING');editor.editing(false);await editor.sync();assert.equal(editor.state()[lyric(2)],'REMOTE WHILE EDITING');total++;console.log('PASS editor is not changed by background pull');
 const full=device(server);await full.sync();full.storage.setItem(lyric(0),'LOCAL QUOTA');server.data[lyric(2)]='REMOTE QUOTA';server.ts++;
 // Journal write fails before local mutation; original edit survives.
 // rawSet was captured already, so force the storage map to reject writes.
 const set=full.storage.map.set.bind(full.storage.map);full.storage.map.set=(k,v)=>{if(k==='qeSync.journal.v2')throw Object.assign(new Error('quota'),{name:'QuotaExceededError'});return set(k,v)};
 await full.sync();assert.equal(full.state()[lyric(0)],'LOCAL QUOTA');assert.equal(full.errors.length,1);assert.equal(full.status(),'⚠ Sincronización pendiente');total++;console.log('PASS quota failure never clears local song data');
 for(const d of [ipad,mac,iphone,late,race,editor])assert.equal(d.errors.length,0);
 console.log(total+' sync tests PASS (Node simulation; not physical Safari)');
})().catch(e=>{console.error(e);process.exitCode=1});
