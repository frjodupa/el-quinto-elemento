const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const html=fs.readFileSync('public/index.html','utf8'),a=html.indexOf('function fillExactRepeatedChords(i,d,previous){'),b=html.indexOf('function saveChordData(i,d)',a);
assert.ok(a>=0&&b>a);
function run(song,current,previous){
  const ctx={getSongText:()=>song};
  vm.runInNewContext(html.slice(a,b)+';this.fill=fillExactRepeatedChords;',ctx);
  return ctx.fill(0,current,previous);
}
const song='PRIMERA LINEA\nSEGUNDA LINEA\nDISTINTA\nPRIMERA LINEA\nSEGUNDA LINEA';
let d=run(song,{lines:{0:'RE',1:'LA'},words:{}},{lines:{},words:{}});
assert.equal(d.lines[3],'RE');assert.equal(d.lines[4],'LA');
d=run(song,{lines:{0:'RE',1:'LA'},words:{}},{lines:{0:'RE',1:'LA'},words:{}});
assert.equal(d.lines[3],undefined,'not allowed to duplicate existing unchanged chords');
d=run(song,{lines:{0:'RE',1:'LA',3:'DO'},words:{}},{lines:{0:'RE',1:'LA',3:'DO'},words:{}});
assert.equal(d.lines[3],'DO');assert.equal(d.lines[4],undefined);
d=run(song,{lines:{0:'RE',1:'LA'},words:{}},{lines:{0:'DO'},words:{}});
assert.equal(d.lines[3],undefined,'editing a preexisting chord must not generate other chords');assert.equal(d.lines[4],undefined);
d=run('UNO\nDOS\nCAMBIO\nUNO\nOTRO',{lines:{0:'RE'},words:{}},{lines:{},words:{}});
assert.equal(d.lines[3],undefined,'different lyrics never inferred');
console.log('Safe chord edit-only test: 5 passes');
