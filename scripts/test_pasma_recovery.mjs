import assert from "node:assert/strict";
import {LA_PASMA_ORDER,buildLaPasmaRecovery} from "../src/pasma_recovery.mjs";

const basePairs=new Map([
["CLAVADO EN UN BAR",13],["SALTA",54],["NO PUEDO VIVIR SIN TI",47],
["ESO QUE TÚ ME DAS",25],["INSURRECCIÓN",30],["QUERIDA MILAGROS",52],
["CADILLAC SOLITARIO",9],["DÉJAME",18],["FRÍO",28]
]);
const customTitles=LA_PASMA_ORDER.filter(x=>!basePairs.has(x));
assert.equal(customTitles.length,14);
const archivedExtras=[...customTitles,...customTitles].map(title=>({title,text:"línea uno\nlínea dos\nlínea tres"}));
const archived={};
archived["quintoElemento.customSongs.v1"]=JSON.stringify(archivedExtras);
const passIds=LA_PASMA_ORDER.map(t=>basePairs.has(t)?basePairs.get(t):71+customTitles.indexOf(t));
const passes=[
{id:"pass-other",name:"PASE JOSE LUIS",songs:[71,75,93,13]},
{id:"pasma",name:"LA PASMA (NUEVA)",songs:passIds}
];
archived["quintoElemento.passes.v1"]=JSON.stringify(passes);
archived["quintoElemento.chords.v2.75"]=JSON.stringify({lines:{},words:{"0:0":"RE","1:2":"LA"},intro:"",instrumentals:{},references:[]});
archived["quintoElemento.chords.v2.89"]=archived["quintoElemento.chords.v2.75"];
const current={
"quintoElemento.customSongs.v1":JSON.stringify([{title:"PERO A TU LADO",text:"nueva canción añadida"}]),
"quintoElemento.passes.v1":JSON.stringify(passes),
"quintoElemento.chords.v2.71":JSON.stringify({words:{"0:0":"MI"},lines:{},instrumentals:{},intro:"",references:[]}),
"quintoElemento.lyrics.v1.71":"nueva canción añadida",
"quintoElemento.title.v1.71":"PERO A TU LADO",
// Orphan slots persisted from an older 99-song layout despite the now 72-song UI.
"quintoElemento.lyrics.v1.72":"línea uno\nlínea dos\nlínea tres",
"quintoElemento.chords.v2.75":JSON.stringify({words:{"0:2":"FA"},lines:{},intro:"",instrumentals:{},references:[]})
};
const before=JSON.stringify(current);
const {state,summary}=buildLaPasmaRecovery(current,archived);
assert.equal(JSON.stringify(current),before,"Must never mutate current state");
assert.equal(summary.originalCount,72);
assert.equal(summary.afterCount,86);
assert.equal(summary.recoveredCount,14);
assert.equal(summary.skippedArchiveDuplicateCount,14);
assert.ok(summary.orphanIndexedKeysArchived>=2);
assert.ok(summary.currentOrphanChordMapsUsed>=1);
assert.equal(summary.changedKeys>0,true);
const newCustom=JSON.parse(state["quintoElemento.customSongs.v1"]);
assert.equal(newCustom.length,15);
assert.equal(newCustom[0].title,"PERO A TU LADO");
assert.equal(newCustom[1].title,"CIEN GAVIOTAS");
assert.equal(state["quintoElemento.lyrics.v1.71"],"nueva canción añadida");
assert.equal(state["quintoElemento.chords.v2.71"],current["quintoElemento.chords.v2.71"]);
const recoveredChordId=72+customTitles.indexOf("MIL CALLES LLEVAN HACIA TI");
assert.equal(JSON.parse(state["quintoElemento.chords.v2."+recoveredChordId]).words["1:2"],"LA");
assert.equal(JSON.parse(state["quintoElemento.chords.v2."+recoveredChordId]).words["0:2"],"FA");
const outPasses=JSON.parse(state["quintoElemento.passes.v1"]);
const pasma=outPasses.find(p=>p.name==="LA PASMA (NUEVA)");
assert.equal(pasma.songs.length,23);
assert.equal(new Set(pasma.songs).size,23);
assert.equal(pasma.songs[0],72);
assert.equal(pasma.songs[1],13);
assert.equal(pasma.songs[22],85);
const other=outPasses.find(p=>p.id==="pass-other");
assert.deepEqual(other.songs,[72,76,72+customTitles.indexOf("EL RITMO DEL GARAJE"),13]);
assert.equal(summary.fixedOtherPasses[0].refsChanged,3);
const second=buildLaPasmaRecovery(state,archived);
assert.equal(second.summary.recoveredCount,0);
assert.equal(second.summary.afterCount,86);
const bad=JSON.parse(JSON.stringify(archived));
const badExtras=JSON.parse(bad["quintoElemento.customSongs.v1"]);
badExtras[14].text="otra letra que no coincide";
bad["quintoElemento.customSongs.v1"]=JSON.stringify(badExtras);
assert.throws(()=>buildLaPasmaRecovery(current,bad),/letras distintas/);
const bad2=JSON.parse(JSON.stringify(archived));
const badPasses=JSON.parse(bad2["quintoElemento.passes.v1"]);
badPasses[1].songs.pop();
bad2["quintoElemento.passes.v1"]=JSON.stringify(badPasses);
assert.throws(()=>buildLaPasmaRecovery(current,bad2),/23 posiciones/);
console.log("PASMA_RECOVERY_TEST=PASSED");
console.log(JSON.stringify({before:summary.originalCount,after:summary.afterCount,restored:summary.recoveredCount,otherRefsRepaired:summary.fixedOtherPasses[0].refsChanged,duplicatesSkipped:summary.skippedArchiveDuplicateCount}));
