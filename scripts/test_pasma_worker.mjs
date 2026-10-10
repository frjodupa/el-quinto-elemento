import assert from "node:assert/strict";
import worker from "../src/worker.js";
import {LA_PASMA_ORDER} from "../src/pasma_recovery.mjs";

const baseNames=new Map([["CLAVADO EN UN BAR",13],["SALTA",54],["NO PUEDO VIVIR SIN TI",47],
  ["ESO QUE TÚ ME DAS",25],["INSURRECCIÓN",30],["QUERIDA MILAGROS",52],
  ["CADILLAC SOLITARIO",9],["DÉJAME",18],["FRÍO",28]]);
const extras=LA_PASMA_ORDER.filter(x=>!baseNames.has(x));
const archivalCustom=[...extras,...extras].map(title=>({title,text:"Texto de prueba\notra línea de prueba"}));
const sourceIDs=LA_PASMA_ORDER.map(t=>baseNames.has(t)?baseNames.get(t):71+extras.indexOf(t));
const passes=[{id:"oldother",name:"PASE JOSE LUIS",songs:[71,75,93,13]},
  {id:"pasma",name:"LA PASMA (NUEVA)",songs:sourceIDs}];
const source={
  "quintoElemento.customSongs.v1":JSON.stringify(archivalCustom),
  "quintoElemento.passes.v1":JSON.stringify(passes),
  "quintoElemento.chords.v2.75":JSON.stringify({lines:{},words:{"0:0":"DO"},intro:"",references:[]})
};
const current={
  "quintoElemento.customSongs.v1":JSON.stringify([{title:"PERO A TU LADO",text:"original del usuario"}]),
"quintoElemento.title.v1.71":"PERO A TU LADO",
  "quintoElemento.passes.v1":JSON.stringify(passes),
"quintoElemento.lyrics.v1.72":"Texto de prueba\notra línea de prueba",
"quintoElemento.chords.v2.75":JSON.stringify({words:{"0:1":"SOL"},lines:{},intro:"",references:[]})
};
const initialTs=147;
class DB{
  constructor(){
    this.now={id:"main",data:JSON.stringify(current),updated_at:initialTs};
    this.backups=[{id:371,data:JSON.stringify(source),created_at:100,source:"auto"}];
    this.archive=new Map();
    this.hasArchive=false;
    this.nextBackupId=378;
  }
  prepare(sql){return new Statement(this,sql)}
  async batch(stmts){return Promise.all(stmts.map(q=>q.run()))}
}
class Statement{
  constructor(db,sql){this.db=db;this.sql=sql.replace(/\s+/g," ").trim();this.args=[];}
  bind(...args){this.args=args;return this}
  async first(){
    const s=this.sql,db=this.db;
    if(s.includes("sqlite_master"))return db.hasArchive?{name:"eqe_recovery_archive"}:null;
    if(s.includes("SELECT tag FROM eqe_recovery_archive"))return [...db.archive.keys()].filter(k=>k.startsWith("pasma-before-merge-")).map(tag=>({tag}))[0]||null;
    if(s.includes("SELECT data, updated_at FROM app_state"))return {...db.now};
    if(s.includes("SELECT id, data FROM app_backups ORDER"))return db.backups.at(-1)||null;
    throw Error("Unknown .first SQL "+s);
  }
  async all(){
    const s=this.sql;
    if(s.includes("SELECT id,data FROM app_backups ORDER")){
      return {results:[...this.db.backups].reverse()};
    }
    throw Error("Unknown .all SQL "+s);
  }
  async run(){
    const s=this.sql,a=this.args,d=this.db;
    if(s.startsWith("CREATE TABLE IF NOT EXISTS eqe_recovery_archive")){d.hasArchive=true;return {meta:{changes:0}}}
    if(s.startsWith("CREATE TABLE")||s.startsWith("CREATE INDEX"))return {meta:{changes:0}};
    if(s.startsWith("INSERT OR IGNORE INTO eqe_recovery_archive")){
      if(!d.archive.has(a[0]))d.archive.set(a[0],a[2]);return {meta:{changes:1}};
    }
    if(s.startsWith("INSERT INTO app_backups")){
      const id=d.nextBackupId++;
      d.backups.push({id,data:a[0],created_at:a[1],source:a[2]});
      return {meta:{changes:1,last_row_id:id}};
    }
    if(s.startsWith("DELETE FROM app_backups")){d.backups=d.backups.slice(-10);return {meta:{changes:0}}}
    if(s.startsWith("UPDATE app_state")){
      if(a[2]==="main"&&Number(a[3])===Number(d.now.updated_at)){
        d.now={id:"main",data:a[0],updated_at:a[1]};
        return {meta:{changes:1}};
      }
      return {meta:{changes:0}};
    }
    if(s.startsWith("INSERT OR IGNORE INTO app_state"))return {meta:{changes:0}};
    throw Error("Unknown .run SQL "+s);
  }
}
const db=new DB();
const env={DB:db,ASSETS:{fetch:async()=>new Response("unused")}};
const base="https://local.example/api";
async function call(path,options={}){
 const res=await worker.fetch(new Request(base+path,options),env);
 return {status:res.status,data:await res.json()};
}
const preview=await call("/maintenance/la-pasma-recovery");
assert.equal(preview.status,200);
assert.equal(preview.data.ready,true);
assert.equal(preview.data.recoveredCount,14);
assert.equal(preview.data.afterCount,86);
assert.equal(preview.data.backupId,371);
assert.equal(preview.data.updatedAt,initialTs);
const preStale=await call("/maintenance/la-pasma-recovery",{
 method:"POST",headers:{"Content-Type":"application/json"},
 body:JSON.stringify({action:"merge_only",expectedUpdatedAt:999,backupId:371})
});
assert.equal(preStale.status,409);
const posted=await call("/maintenance/la-pasma-recovery",{
 method:"POST",headers:{"Content-Type":"application/json"},
 body:JSON.stringify({action:"merge_only",expectedUpdatedAt:initialTs,backupId:371})
});
assert.equal(posted.status,200);
assert.equal(posted.data.verified,true);
assert.equal(posted.data.recoveredCount,14);
assert.equal(posted.data.afterCount,86);
assert.equal(db.archive.size,2);
assert.equal(db.archive.has("pasma-99-source-371"),true);
const merged=JSON.parse(db.now.data);
const actualExtras=JSON.parse(merged["quintoElemento.customSongs.v1"]);
assert.equal(actualExtras.length,15);
assert.equal(actualExtras[0].title,"PERO A TU LADO");
assert.equal(actualExtras[1].title,"CIEN GAVIOTAS");
assert.ok(posted.data.orphanIndexedKeysArchived>=2);
assert.ok(posted.data.currentOrphanChordMapsUsed>=1);
const actualPasses=JSON.parse(merged["quintoElemento.passes.v1"]);
assert.equal(actualPasses.find(x=>x.id==="pasma").songs[0],72);
assert.equal(actualPasses.find(x=>x.id==="pasma").songs.length,23);
assert.deepEqual(actualPasses.find(x=>x.id==="oldother").songs.slice(0,2),[72,76]);
const noToken=await call("/sync",{
 method:"PUT",headers:{"Content-Type":"application/json"},body:JSON.stringify({data:current})
});
assert.equal(noToken.status,409,"Cached pre-recovery clients cannot overwrite recovered archive");
const oldToken=await call("/sync",{
 method:"PUT",headers:{"Content-Type":"application/json"},
 body:JSON.stringify({data:current,expectedUpdatedAt:initialTs})
});
assert.equal(oldToken.status,409,"Stale clients cannot overwrite recovered archive");
assert.equal(JSON.parse(db.now.data)["quintoElemento.customSongs.v1"],merged["quintoElemento.customSongs.v1"]);
const newToken=await call("/sync",{
 method:"PUT",headers:{"Content-Type":"application/json"},
 body:JSON.stringify({data:merged,expectedUpdatedAt:posted.data.updatedAt})
});
assert.equal(newToken.status,200,"Current clients should be allowed to sync");
assert.equal(newToken.data.ok,true);
console.log("PASMA_WORKER_TEST=PASSED");
console.log(JSON.stringify({backup:posted.data.archivedSourceId,recovered:posted.data.recoveredCount,
 restoredSongs:actualExtras.length+71,passSize:actualPasses[1].songs.length,
 legacyWriteStatus:noToken.status,staleWriteStatus:oldToken.status,currentWriteStatus:newToken.status}));
