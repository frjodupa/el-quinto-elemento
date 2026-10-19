/* Auditoría de SOLO LECTURA del cancionero EQE.
 * Ejecutar: node scripts/audit-base-repertoire.cjs
 * NO altera letras, acordes, localStorage, D1, ni Cloudflare.
 */
"use strict";
const fs=require("node:fs");
const path=require("node:path");
const assert=require("node:assert/strict");
const root=path.resolve(__dirname,"..");
const html=fs.readFileSync(path.join(root,"public/index.html"),"utf8");
const start=html.indexOf("let songs=");
assert.ok(start>=0,"No se encuentra el repertorio base");
const open=start+"let songs=".length;
const close=html.indexOf("];",open);
assert.ok(close>open,"No se encuentra el final del repertorio");
const songs=JSON.parse(html.slice(open,close+1));
const refs=JSON.parse(fs.readFileSync(path.join(root,"public/pdf-chords-v44.json"),"utf8"));
const normalize=s=>String(s||"").normalize("NFD").replace(/[\u0300-\u036f]/g,"").toUpperCase().replace(/[^A-Z0-9]+/g," ").trim();
const index=new Map(Object.entries(refs).map(([title,value])=>[normalize(title),value]));
const report=songs.map((song,id)=>{
 const entries=index.get(normalize(song.title))?.entries||[];
 const rows=String(song.text||"").split("\n");
 const malformedEntries=entries.filter(row=>!Array.isArray(row)||typeof row[0]!=="string"||!Array.isArray(row[1])).length;
 const outOfRangeAnchors=entries.reduce((sum,row)=>{
   if(!Array.isArray(row)||!Array.isArray(row[1]))return sum;
   const words=String(row[0]||"").trim().split(/\s+/).filter(Boolean).length;
   return sum+row[1].filter(anchor=>!Array.isArray(anchor)||!Number.isInteger(anchor[0])||anchor[0]<0||anchor[0]>=words||typeof anchor[1]!=="string"||!anchor[1].trim()).length;
 },0);
 return {id,title:song.title,lyricLines:rows.length,referenceLines:entries.length,
  chordAnchors:entries.reduce((sum,row)=>sum+(Array.isArray(row[1])?row[1].length:0),0),
  malformedEntries,outOfRangeAnchors,
  status:entries.length===0?"NO_REFERENCE":entries.length<10?"LOW_REFERENCE":"NEEDS_MUSICAL_REVIEW"};
});
assert.equal(songs.length,71,"Inventario base distinto: revisar antes de comparar");
assert.equal(new Set(songs.map(x=>normalize(x.title))).size,songs.length,"Hay títulos duplicados normalizados");
const totals=Object.fromEntries(["NO_REFERENCE","LOW_REFERENCE","NEEDS_MUSICAL_REVIEW"].map(k=>[k,report.filter(x=>x.status===k).length]));
const structuralIssues=report.filter(row=>row.malformedEntries||row.outOfRangeAnchors);
console.log(JSON.stringify({structuralIssues:structuralIssues.map(row=>({title:row.title,malformedEntries:row.malformedEntries,outOfRangeAnchors:row.outOfRangeAnchors})),source:"repository_base_only",notChecked:["device-local edits","D1","actual musical correctness"],total:songs.length,totals,report},null,2));
