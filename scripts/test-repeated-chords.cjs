const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const html=fs.readFileSync('public/index.html','utf8');
const a=html.indexOf('function fillExactRepeatedChords(i,d){');
const b=html.indexOf('function saveChordData(i,d)',a);
assert.ok(a>=0&&b>a,'automatic chord function missing');
function run(song,d){
 const context={getSongText:()=>song};
 vm.runInNewContext(html.slice(a,b)+';this.fill=fillExactRepeatedChords',context);
 return context.fill(0,d);
}
const song='VERSO UNO\nVERSO DOS\nOTRO\nVERSO UNO\nVERSO DOS';
let result=run(song,{lines:{0:'RE',1:'LA'},words:{'0:1':'SOL'}});
assert.equal(result.lines[3],'RE');
assert.equal(result.lines[4],'LA');
assert.equal(result.words['3:1'],'SOL');
result=run(song,{lines:{0:'RE',1:'LA',3:'DO'},words:{}});
assert.equal(result.lines[3],'DO','must retain any manually edited target');
assert.equal(result.lines[4],undefined,'must not partially overwrite manually edited block');
result=run('VERSO UNO\nVERSO DOS\nOTRO\nVERSO UNO\nVERSO DIFERENTE',{lines:{0:'RE'},words:{}});
assert.equal(result.lines[3],undefined,'no matching block');
console.log('EQE repeated chord guards passed');
