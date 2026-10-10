/* EQE: diagnóstico sin escritura de acordes, letras, D1 ni red.
 * Ejecutar: node scripts/test-song-import-integrity.cjs
 * Lee el parser REAL desde src/worker.js y registra posibles pérdidas.
 */
"use strict";
const assert=require("node:assert/strict");
const fs=require("node:fs");
const path=require("node:path");
const vm=require("node:vm");

const worker=fs.readFileSync(path.join(__dirname,"../src/worker.js"),"utf8");
const prelude=worker.split("export default {")[0]
  .replace(/^import\s+.*?;\s*$/gm,"");
const context={};
vm.runInNewContext(prelude+"\n globalThis.__parseSongContent=parseSongContent;",context,{timeout:2500});
const parse=context.__parseSongContent;
assert.equal(typeof parse,"function");

const simple=parse("[ch]C[/ch]HOLA [ch]G[/ch]MUNDO","ultimate-guitar");
assert.equal(simple.text,"HOLA MUNDO");
assert.equal(simple.chordData.words["0:0"],"DO");
assert.equal(simple.chordData.words["0:1"],"SOL");

const paired=parse("C       G\nHOLA    MUNDO","cifraclub");
assert.equal(paired.text,"HOLA MUNDO");
assert.ok(Object.keys(paired.chordData.words).length>0);

const findings=[];
const collision=parse("[ch]C[/ch][ch]G[/ch]HOLA MUNDO","ultimate-guitar");
if(collision.chordCount<2)
  findings.push({code:"MULTIPLE_CHORDS_SAME_WORD",detail:"Dos acordes sobre una palabra se reducen a una única entrada words; el anterior se sobrescribe",observed:collision.chordData.words["0:0"]});
const lineFields=parse("C    G\nHOLA MUNDO","cifraclub");
if(Object.keys(lineFields.chordData.lines).length===0)
  findings.push({code:"LINE_CHORDS_NOT_POPULATED",detail:"El importador nunca crea anclajes lines desde líneas de acordes"});
const duplicatedIntro=parse("Intro\nC C G\n\nHOLA MUNDO","cifraclub");
if((duplicatedIntro.chordData.intro.match(/DO/g)||[]).length<2)
  findings.push({code:"INTRO_REPETITIONS_LOST",detail:"Intro elimina repeticiones de acordes con Set"});
if(simple.chordData.references.length===0)
  findings.push({code:"SOURCE_REFERENCE_NOT_IN_PARSER",detail:"El parser entrega references vacío; verificar si la interfaz agrega la referencia al importar"});

console.log(JSON.stringify({status:"diagnostic_only",baselineTests:"PASS",findings},null,2));
if(!findings.length) console.log("Sin incidencias reproducidas en estos casos");
