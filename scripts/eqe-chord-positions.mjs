// EQE isolated chord positioning engine — no browser, D1 or app imports.
// Keeps existing word and line chords untouched.
export function cloneChordData(data) {
  return JSON.parse(JSON.stringify(data || {}));
}
export function characterCount(text) {
  return Array.from(String(text ?? '')).length;
}
export function placeAtCharacter(data, line, offset, chord, lyrics) {
  if (!Number.isSafeInteger(line) || line < 0) throw new RangeError('line');
  const count = Math.max(1, characterCount(lyrics)); // virtual slot for genuinely empty lines
  if (!Number.isSafeInteger(offset) || offset < 0 || offset >= count) throw new RangeError('offset');
  const next = cloneChordData(data);
  next.positions ||= {};
  const key = String(line);
  const entries = (Array.isArray(next.positions[key]) ? next.positions[key] : [])
    .filter(p => p.offset !== offset);
  if (String(chord || '').trim()) entries.push({offset, chord: String(chord).trim()});
  entries.sort((a,b) => a.offset - b.offset);
  if (entries.length) next.positions[key] = entries;
  else delete next.positions[key];
  return next;
}
export function copyChordLines(data, sourceStart, count, destination, lyricsLines, replace=false) {
  if (![sourceStart,count,destination].every(Number.isSafeInteger) || count < 1 || sourceStart < 0 || destination < 0 ||
    sourceStart + count > lyricsLines.length || destination + count > lyricsLines.length) throw new RangeError('block');
  const next = cloneChordData(data);
  next.lines ||= {};
  next.words ||= {};
  next.positions ||= {};
  // Make immutable snapshot BEFORE touching any destination; overlap is safe.
  const snapshot = Array.from({length:count},(_,delta)=>{
    const line=sourceStart+delta;
    return {
      lineChord: next.lines[line] || null,
      words: Object.entries(next.words).filter(([k])=> Number(k.split(':')[0]) === line)
        .map(([k,v])=>({index: Number(k.split(':')[1]), chord:v})),
      positions: cloneChordData(next.positions[String(line)] || [])
    };
  });
  if (!replace) {
    for (let offset=0;offset<count;offset++){
      const index=destination+offset;
      if (next.lines[index] || Object.keys(next.words).some(k=>Number(k.split(':')[0])===index) ||
          (next.positions[String(index)] || []).length) throw new Error('DESTINATION_HAS_CHORDS');
    }
  }
  // Explicit replace only; never touches lyrics, intro, passes, references or instrumentals.
  // Positional chords must land within the target line. Abort instead of silently shifting them.
  for (let offset=0;offset<count;offset++){
    const targetLength=Math.max(1,characterCount(lyricsLines[destination+offset]));
    if(snapshot[offset].positions.some(p=>!Number.isSafeInteger(p.offset)||p.offset<0||p.offset>=targetLength))
      throw new Error('DESTINATION_POSITION_OUT_OF_RANGE');
  }
  for (let offset=0;offset<count;offset++){
    const to=destination+offset;
    delete next.lines[to];
    delete next.positions[String(to)];
    for (const key of Object.keys(next.words)) if(Number(key.split(':')[0])===to) delete next.words[key];
    const src=snapshot[offset];
    if(src.lineChord) next.lines[to]=src.lineChord;
    for(const w of src.words) next.words[to+':'+w.index]=w.chord;
    if(src.positions.length) next.positions[String(to)]=src.positions;
  }
  return next;
}
