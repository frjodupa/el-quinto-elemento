#!/usr/bin/env node
// Read-only audit of the embedded song catalog. No network or application data writes.
const fs = require('node:fs');
const path = require('node:path');
const html = fs.readFileSync(path.join(__dirname, '..', 'public', 'index.html'), 'utf8');
const marker = 'let songs=';
const start = html.indexOf(marker);
if (start < 0) throw new Error('Song catalog not found');
const end = html.indexOf('];', start);
if (end < 0) throw new Error('Song catalog end not found');
const songs = JSON.parse(html.slice(start + marker.length, end + 1));
const problems = [];
const normalized = new Set();
for (const [i, song] of songs.entries()) {
  const id = String(song.title || '').normalize('NFD').replace(/[\\u0300-\\u036f]/g, '').trim().toUpperCase();
  if (normalized.has(id)) problems.push({number:i+1,title:song.title,type:'duplicate_title'});
  normalized.add(id);
  const lines = String(song.text || '').split(/\\r?\\n/);
  const isolated = lines.filter(line => /^[A-ZÁÉÍÓÚÑ]$/.test(line.trim())).length;
  if (isolated > 10) problems.push({number:i+1,title:song.title,type:'probable_ocr_corruption',count:isolated});
  if (/NO TEXT COULD BE PARSED FROM DOCUMENT/i.test(song.text)) problems.push({number:i+1,title:song.title,type:'pdf_extraction_error'});
  if (/BAJANDO\\.{4,}/.test(song.text)) problems.push({number:i+1,title:song.title,type:'extraneous_annotation'});
  if (/<VARIAS VECES>/i.test(song.text)) problems.push({number:i+1,title:song.title,type:'repeat_annotation'});
}
const result = {total:songs.length,unique_titles:normalized.size,problems};
process.stdout.write(JSON.stringify(result,null,2)+'\\n');
if (songs.length !== 71 || problems.some(p=>p.type==='duplicate_title')) process.exitCode=1;
