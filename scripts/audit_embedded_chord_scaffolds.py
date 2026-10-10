#!/usr/bin/env python3
"""Detect chord-only text scaffolding mis-imported as song lyrics, read-only.

Classifies chord-only rows with underscores / tab alignment as highly likely
to be misplaced native chord data. Never writes lyrics or chord maps.
"""
import collections
import json
import re
from pathlib import Path
import audit_songbook as a

OUT=Path("eqe-embedded-chord-lines")
OUT.mkdir(exist_ok=True)
def row(line):
 s=line.strip().replace("\t"," ").replace("\u00a0"," ")
 clean=re.sub(r"[_–—·|]+"," ",s)
 chunks=[x.strip("[](){}.,;:!¡?¿-") for x in re.split(r"\s+",clean.strip()) if x.strip()]
 chords=[x for x in chunks if x and a.is_chord(x)]
 words=[x for x in chunks if x and not a.is_chord(x)]
 formatted=("_" in line or "\t" in line or bool(re.search(r"\s{3,}",line)))
 strong=len(chords)>=2 and len(words)==0 and (formatted or len(chords)>=3)
 if not strong and len(chords)>=2 and not words and a.chord_line(line):
  strong=True
 return {"suspect":strong,"symbols":chords,"badTokens":words,"formatting":formatted}
def main():
 storage,_=a.load_remote_storage()
 songs=a.build_songbook(storage)
 reports=[]
 for s in songs:
  suspect=[]
  lines=s["texto"].splitlines()
  native=a.normalize_chord_data(s["letraConAcordes"])
  for li,v in enumerate(lines):
   r=row(v)
   if r["suspect"]:
    next_line=next((j for j in range(li+1,len(lines)) if lines[j].strip()),None)
    same_line_chords=[k for k,x in native["words"].items() if k.startswith(str(li)+":") and x]
    next_line_chords=[k for k,x in native["words"].items() if next_line is not None and k.startswith(str(next_line)+":") and x]
    suspect.append({"lineIndex":li,"symbols":r["symbols"],"nativeOnSourceRow":len(same_line_chords),
      "nextNonemptyLineIndex":next_line,"nativeOnNextRow":len(next_line_chords)})
  if suspect:
   reports.append({"id":int(s["id"]),"title":s["titulo"],"physicalTextLines":len(lines),
    "scaffoldLines":len(suspect),"nativeChordCount":a.count_chords(native),"likelyHiddenChordSymbols":sum(len(x["symbols"]) for x in suspect),
    "strongCandidates":suspect[:80]})
   print("EMBEDDED_CHORD_SCAFFOLDS="+json.dumps({k:v for k,v in reports[-1].items() if k!="strongCandidates"},ensure_ascii=False),flush=True)
 output={"readOnly":True,"inventoryCount":len(songs),"songsWithChordScaffolds":len(reports),
   "suspectPhysicalLines":sum(len(v["strongCandidates"]) for v in reports),
   "sourceAlreadyUserSongText":True,
   "candidates":reports}
 (OUT/"CHORD_SCAFFOLD_DIAGNOSTIC.json").write_text(json.dumps(output,ensure_ascii=False,indent=2)+"\n")
 print("SCaffold_AUDIT_COMPLETE=YES",flush=True)
if __name__=="__main__":main()
