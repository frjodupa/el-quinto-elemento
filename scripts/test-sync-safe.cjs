const assert=require('node:assert/strict');
const vm=require('node:vm');
const fs=require('node:fs');
const context={};vm.runInNewContext(fs.readFileSync('public/sync-engine.js','utf8'),context);
const merge=context.QESyncEngine.merge;
const A='quintoElemento.chords.v2.4',B='quintoElemento.lyrics.v1.4',C='quintoElemento.customSongs.v1',D='quintoElemento.passes.v1';
function check(name,b,l,r,expected,conflictCount){const x=merge(b,l,r);assert.equal(x.conflicts.length,conflictCount,name);if(!conflictCount)assert.deepEqual(JSON.parse(JSON.stringify(x.merged)),expected,name);console.log('PASS '+name)}
check('disjoint edits',{[A]:'old',[B]:'old'},{[A]:'new',[B]:'old'},{[A]:'old',[B]:'remote'},{[A]:'new',[B]:'remote'},0);
check('same edit',{[A]:'old'},{[A]:'new'},{[A]:'new'},{[A]:'new'},0);
check('same field collision',{[A]:'old'},{[A]:'ipad'},{[A]:'mac'},null,1);
check('legacy baseline not known',null,{[A]:'ipad'},{[A]:'mac'},null,1);
check('legacy independent keys',null,{[A]:'ipad'},{[B]:'mac'},{[A]:'ipad',[B]:'mac'},0);
check('local delete vs unchanged remote',{[A]:'old'},{},{[A]:'old'},{},0);
check('delete vs edit',{[A]:'old'},{},{[A]:'mac'},null,1);
check('custom songs concurrent', {[C]:'[]'},{[C]:'[{"title":"A"}]'},{[C]:'[{"title":"B"}]'},null,1);
check('pass concurrent', {[D]:'[]'},{[D]:'[1]'},{[D]:'[2]'},null,1);
check('no local edits',{[A]:'old'},{[A]:'old'},{[A]:'mac'},{[A]:'mac'},0);
