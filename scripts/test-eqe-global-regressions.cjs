const fs=require('node:fs');
const assert=require('node:assert/strict');
const source=fs.readFileSync('public/index.html','utf8');
const checks=[
 ['setlist return uses originating pass ID',/window\.qeReturnToPassIndex=function\(\)[\s\S]*?getPass\(origin\.id\)/],
 ['setlist open preserves saved order',/window\.activePass=\{id:p\.id,name:p\.name,songs:p\.songs\.slice\(\),position:pos\}/],
 ['navigation moves within pass',/window\.passNextSong=function\(\)[\s\S]*?openSong\(p\.songs\[p\.position\]\)/],
 ['header shows next song from pass',/getSongTitle\(nextIndex\)/],
 ['PDF prints individual pass in saved order',/function passPrintHtml\(p\)[\s\S]*?\(p\.songs\|\|\[\]\)\.map/],
 ['PDF includes a date',/Fecha de impresión:/],
 ['system appearance is observed',/prefers-color-scheme: dark/],
 ['pass changes stored locally',/function savePasses\(arr\)[\s\S]*?localStorage\.setItem\(passesKey\(\)/]
];
for(const [name,pattern] of checks)assert.match(source,pattern,name);
console.log('Global EQE guards passed: '+checks.length);
