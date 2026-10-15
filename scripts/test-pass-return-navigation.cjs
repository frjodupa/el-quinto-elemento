const assert=require('node:assert/strict');
const fs=require('node:fs');
const s=fs.readFileSync('public/index.html','utf8');
const checks=[
  ['pass back handler',/getElementById\('back'\)\.onclick=function\(\)\{[\s\S]*?qeReturnToPassIndex/],
  ['pass song origin',/qeSongPassOrigin=\{id:p\.id,songIndex:songIndex/],
  ['start pass origin',/qeSongPassOrigin=\{id:p\.id,songIndex:p\.songs\[0\]/],
  ['return to existing pass',/function\(\)\{[\s\S]*?var pass=getPass\(origin\.id\);/],
  ['restore current song position',/songIndex:active\.songs\[active\.position\]/],
  ['global index resets origin',/window\.qeSongPassOrigin=null;\s*if\(window\.clearActivePass\)/],
];
for(const [name,pattern] of checks){assert.match(s,pattern,name);}
console.log('EQE navigation invariants: '+checks.length+' passed');
