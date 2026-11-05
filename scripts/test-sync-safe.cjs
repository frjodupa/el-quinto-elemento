const assert=require('node:assert/strict');
const vm=require('node:vm');
const fs=require('node:fs');
const context={};vm.runInNewContext(fs.readFileSync('public/sync-engine.js','utf8'),context);
const merge=context.QESyncEngine.merge;
const A='quintoElemento.chords.v2.4',B='quintoElemento.lyrics.v1.5',C='quintoElemento.customSongs.v1',D='quintoElemento.passes.v1';
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

check('desktop appends song without changing earlier indexes',null,
 {[C]:'[{"title":"A"}]',[A]:'ipad chords'},
 {[C]:'[{"title":"A"},{"title":"B"}]',[A]:'old chords'},
 null,1); // Same existing chord key differs and must remain protected.
check('desktop adds song and iPad edits an independent chord',null,
 {[C]:'[{"title":"A"}]',[A]:'ipad chords'},
 {[C]:'[{"title":"A"},{"title":"B"}]'},
 {[C]:'[{"title":"A"},{"title":"B"}]',[A]:'ipad chords'},0);
check('two independent pass additions',null,
 {[D]:'[{"id":"p1","name":"Uno","songs":[1]}]'},
 {[D]:'[{"id":"p2","name":"Dos","songs":[2]}]'},
 {[D]:'[{"id":"p1","name":"Uno","songs":[1]},{"id":"p2","name":"Dos","songs":[2]}]'},0);
check('existing pass edited differently',null,
 {[D]:'[{"id":"p1","name":"Uno","songs":[1]}]'},
 {[D]:'[{"id":"p1","name":"Uno","songs":[2]}]'},null,1);

function chord(words,intro='DO'){return JSON.stringify({lines:{},words,intro,introText:'',instrumentals:{},instrumentalsText:{},references:[]})}
{
  const key='quintoElemento.chords.v2.47';
  const b=chord({'0:0':'DO','1:0':'FA'});
  const l=chord({'0:0':'RE','1:0':'FA'});
  const r=chord({'0:0':'DO','1:0':'SOL'});
  const merged=merge({[key]:b},{[key]:l},{[key]:r});
  assert.equal(merged.conflicts.length,0,'separate chord positions must merge');
  const final=JSON.parse(merged.merged[key]);
  assert.equal(final.words['0:0'],'RE');assert.equal(final.words['1:0'],'SOL');
  console.log('PASS independent chord positions within same song');
}
{
  const key='quintoElemento.chords.v2.47';
  const b=chord({'0:0':'DO'});
  const l=chord({'0:0':'RE'});
  const r=chord({'0:0':'MI'});
  assert.equal(merge({[key]:b},{[key]:l},{[key]:r}).conflicts.length,1);
  console.log('PASS conflicting same chord position protected');
}
{
  const key='quintoElemento.chords.v2.47';
  const b=chord({'0:0':'DO'},'DO');
  const l=chord({'0:0':'RE'},'DO');
  const r=chord({'0:0':'DO'},'SOL');
  const result=merge({[key]:b},{[key]:l},{[key]:r});
  assert.equal(result.conflicts.length,0);
  assert.equal(JSON.parse(result.merged[key]).intro,'SOL');
  console.log('PASS independent intro and chord changes');
}
{
  const key='quintoElemento.chords.v2.47';
  const b=chord({'0:0':'DO','0:1':'FA'});
  const l=chord({'0:1':'FA'});
  const r=chord({'0:0':'SOL','0:1':'FA'});
  assert.equal(merge({[key]:b},{[key]:l},{[key]:r}).conflicts.length,1);
  console.log('PASS chord deletion-versus-edit conflict protected');
}

{
 const lyrics='quintoElemento.lyrics.v1.47';
 const chords='quintoElemento.chords.v2.47';
 const base={[lyrics]:'LINE ONE\\nLINE TWO',[chords]:chord({'1:0':'DO'})};
 const local={...base,[lyrics]:'LINE ONE\\nNEW LINE\\nLINE TWO'};
 const remote={...base,[chords]:chord({'1:0':'SOL'})};
 const got=merge(base,local,remote);
 assert.equal(got.hasConflicts,true);
 assert.ok(got.conflicts.some(c=>c.key==='song:47:lyrics-chords'));
 console.log('PASS protect shifted chord anchors after remote chord + local lyric edit');
}
{
 const lyrics='quintoElemento.lyrics.v1.47';
 const chords='quintoElemento.chords.v2.47';
 const base={[lyrics]:'LINE ONE',[chords]:chord({'0:0':'DO'})};
 const local={...base,[lyrics]:'LINE ONE UPDATED'};
 const remote={...base,[lyrics]:'LINE ONE',[chords]:chord({'0:0':'DO'})};
 assert.equal(merge(base,local,remote).hasConflicts,false);
 console.log('PASS safe single-device lyric edit');
}

// Ensure a full cloud snapshot cannot silently replace rehearsal settings after a storage error.
{
 const fs=require('node:fs');
 const html=fs.readFileSync('public/index.html','utf8');
 assert.ok(html.includes('STORAGE_APPLY_FAILED'),'storage failure must be surfaced');
 assert.ok(html.includes('STORAGE_ROLLBACK_FAILED'),'failed rollback must be surfaced');
 assert.ok(html.includes('Object.keys(original).forEach'),'local keys must be restored');
 console.log('PASS local storage recovery guard present');
}
