(function(){
'use strict';
function pdfEsc(s){
  return String(s).replace(/\\/g,'\\\\').replace(/\(/g,'\\(').replace(/\)/g,'\\)').replace(/[^\x20-\x7e]/g,function(c){
    var n=c.charCodeAt(0);
    var x={8364:128,8216:145,8217:146,8220:147,8221:148,8211:150,8212:151}[n];
    if(x!==undefined)n=x;
    if(n>255)n=63;
    return '\\'+n.toString(8).padStart(3,'0');
  });
}
function asciiPdf(s){return new Uint8Array(Array.from(s,function(c){return c.charCodeAt(0)&255;}));}
function createPdf(){
  var header=document.querySelector('h1').textContent;
  var subtitle=document.querySelector('.printMeta').textContent;
  var songs=Array.from(document.querySelectorAll('ol li')).map(function(li){return li.textContent.trim();});
  var pages=[],page=[];
  songs.forEach(function(song,i){
    if(page.length>=24){pages.push(page);page=[];}
    page.push((i+1)+'. '+song);
  });
  if(page.length||!pages.length)pages.push(page);
  var objs=['','<< /Type /Catalog /Pages 2 0 R >>','','<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>'];
  var kids=[];
  pages.forEach(function(lines,pageIndex){
    var pageId=objs.length,contentId=pageId+1;kids.push(pageId+' 0 R');
    objs.push('<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 4 0 R >> >> /Contents '+contentId+' 0 R >>');
    var ops=['BT','/F1 18 Tf','50 790 Td','('+pdfEsc(header)+') Tj','/F1 10 Tf','0 -24 Td','('+pdfEsc(subtitle)+') Tj','/F1 12 Tf','0 -33 Td'];
    lines.forEach(function(line){ops.push('('+pdfEsc(line)+') Tj');ops.push('0 -27 Td');});
    ops.push('/F1 9 Tf','('+pdfEsc('Página '+(pageIndex+1)+' de '+pages.length)+') Tj','ET');
    var stream=ops.join('\n')+'\n';
    objs.push('<< /Length '+stream.length+' >>\nstream\n'+stream+'endstream');
  });
  objs[2]='<< /Type /Pages /Kids ['+kids.join(' ')+'] /Count '+kids.length+' >>';
  var output='%PDF-1.4\n%PDF\n',offsets=[0];
  for(var i=1;i<objs.length;i++){offsets.push(output.length);output+=i+' 0 obj\n'+objs[i]+'\nendobj\n';}
  var xref=output.length;
  output+='xref\n0 '+objs.length+'\n0000000000 65535 f \n';
  for(var j=1;j<objs.length;j++)output+=String(offsets[j]).padStart(10,'0')+' 00000 n \n';
  output+='trailer\n<< /Size '+objs.length+' /Root 1 0 R >>\nstartxref\n'+xref+'\n%%EOF\n';
  return new Blob([asciiPdf(output)],{type:'application/pdf'});
}
function fileName(){return 'Pase-'+document.querySelector('h1').textContent.trim().normalize('NFD').replace(/[\u0300-\u036f]/g,'').replace(/[^a-zA-Z0-9-]+/g,'-').replace(/^-|-$/g,'')+'.pdf';}
function savePdf(){
  var url=URL.createObjectURL(createPdf()),a=document.createElement('a');
  a.href=url;a.download=fileName();document.body.appendChild(a);a.click();a.remove();
  setTimeout(function(){URL.revokeObjectURL(url);},60000);
}
async function sharePdf(){
  var f=new File([createPdf()],fileName(),{type:'application/pdf'});
  if(navigator.share&&navigator.canShare&&navigator.canShare({files:[f]})){
    try{await navigator.share({files:[f],title:document.querySelector('h1').textContent});return;}
    catch(e){if(e.name==='AbortError')return;}
  }
  savePdf();alert('PDF generado. Si no se abre Compartir, usa el archivo descargado desde Archivos.');
}
document.getElementById('savePdfBtn').addEventListener('click',savePdf);
document.getElementById('sharePdfBtn').addEventListener('click',sharePdf);
document.getElementById('printNativeBtn').addEventListener('click',function(){window.print();});
})();