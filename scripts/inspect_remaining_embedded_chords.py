#!/usr/bin/env python3
"""Metadata-only mapping audit for leftover text chord scaffolds. No writes."""
import json
import audit_songbook as a
import audit_embedded_chord_scaffolds as detector

storage,_=a.load_remote_storage()
songs={int(s["id"]):s for s in a.build_songbook(storage)}
print("CURRENT_SONGS="+str(len(songs)),flush=True)
for sid in [5,10,51]:
 s=songs[sid];lines=s["texto"].splitlines();d=a.normalize_chord_data(s["letraConAcordes"])
 target=[]
 for i,line in enumerate(lines):
  info=detector.row(line)
  if not info["suspect"]:continue
  following=next((j for j in range(i+1,len(lines)) if lines[j].strip()),None)
  previous=next((j for j in range(i-1,-1,-1) if lines[j].strip()),None)
  native=str(d["lines"].get(str(i)) or "").strip()
  next_native=str(d["lines"].get(str(following)) or "").strip() if following is not None else ""
  target.append({"index":i,"chords":info["symbols"],"chordCount":len(info["symbols"]),
    "previousIsChordRow":previous is not None and detector.row(lines[previous])["suspect"],
    "followingIsChordRow":following is not None and detector.row(lines[following])["suspect"],
    "nextPhysicalLine":following,"nextHasNativeLineChords":bool(next_native),
    "nextHasNativeWordChords":following is not None and any(k.startswith(str(following)+":") and v for k,v in d["words"].items()),
    "sameRowHasNativeChords":bool(native),
    "nextIdentifyingWords":lines[following].split()[:3] if following is not None and not detector.row(lines[following])["suspect"] else []})
 report={"id":sid,"title":s["titulo"],"existingNativeChords":a.count_chords(d),"nativeLineKeys":{k:len(a.split_chords(v)) for k,v in d["lines"].items()},"scaffolds":target}
 print("SCAFFOLD_METADATA="+json.dumps(report,ensure_ascii=False),flush=True)
print("AUDIT_READ_ONLY=YES",flush=True)
