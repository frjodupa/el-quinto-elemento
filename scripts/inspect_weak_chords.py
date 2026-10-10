#!/usr/bin/env python3
"""Internal diagnostics of existing chord roots and brief identifying fragments.

Metadata-only public output; never dumps entire lyrics or any complete chords+lyrics sheet.
"""
import json
import audit_songbook as a

def main():
 storage,_=a.load_remote_storage()
 songbook={int(s["id"]):s for s in a.build_songbook(storage)}
 for sid in (5,51,62,73):
  s=songbook[sid]
  chord=a.normalize_chord_data(s["letraConAcordes"])
  positions=[]
  for k,v in chord["words"].items():
   if str(v).strip():positions.append({"at":k,"chord":v})
  for k,v in chord["lines"].items():
   if str(v).strip():positions.append({"at":k+":line","chord":v})
  # Just enough to distinguish homonymous songs in original source search.
  heads=[line.strip().split()[:7] for line in s["texto"].splitlines() if len(line.split())>=3][:4]
  print("WEAK_SONG_SIGNATURE="+json.dumps({
    "id":sid,"title":s["titulo"],"currentChordCount":a.count_chords(chord),
    "currentRoots":sorted(set(a.chord_root(v["chord"]) or "-" for v in positions)),
    "currentAnchors":positions[:40],"introChordSymbols":chord["intro"],
    "identificationFragments":heads},ensure_ascii=False),flush=True)
 print("READ_ONLY=YES",flush=True)

if __name__=="__main__":main()
