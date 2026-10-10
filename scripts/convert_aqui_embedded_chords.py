#!/usr/bin/env python3
"""Convert 33 embedded chord-only text rows in AQUÍ NO HAY PLAYA.

Native EQE chord data stores entire line sequences in data.lines (♫).
This migration removes ONLY formatting/chord scaffolds from lyrics, maps every
other original line 1:1, preserves intro, chords on words, and all song/passes.
DRY RUN by default. APPLY_AQUI_SCAFFOLDS=1 writes after D1 manual backup and
optimistic updatedAt verification.
"""
import copy
import hashlib
import json
import os
from pathlib import Path
import requests

import audit_songbook as a
import audit_embedded_chord_scaffolds as detector
import strict_line_chords_86 as align

SID=5
TITLE="AQUÍ NO HAY PLAYA"
EXPECTED_SCAFFOLDS=33
EXPECTED_HIDDEN_CHORDS=99
EXPECTED_TEXT_LINES=78
EXPECTED_EXISTING_CHORDS=6
APPLY=os.environ.get("APPLY_AQUI_SCAFFOLDS","0")=="1"
OUT=Path("eqe-aqui-chord-conversion")
OUT.mkdir(exist_ok=True)
HEADERS={**a.HEADERS,"Content-Type":"application/json"}

def stamp(data):
 return hashlib.sha256(json.dumps(data,sort_keys=True,ensure_ascii=False,separators=(",",":")).encode()).hexdigest()

def live():
 storage,meta=a.load_remote_storage()
 songs={int(s["id"]):s for s in a.build_songbook(storage)}
 if not 86<=len(songs)<=120 or SID not in songs:
  raise RuntimeError("Unexpected song inventory")
 if align.normalize_label(songs[SID]["titulo"])!=align.normalize_label(TITLE):
  raise RuntimeError("Song ID5 is not Aquí no hay playa")
 return storage,songs,meta

def candidate(song):
 old=song["texto"].splitlines()
 data=a.normalize_chord_data(song["letraConAcordes"])
 if len(old)!=EXPECTED_TEXT_LINES or a.count_chords(data)!=EXPECTED_EXISTING_CHORDS:
  raise RuntimeError("Existing song changed from audited 78-line/6-chord baseline")
 if data["instrumentals"] or data["instrumentalsText"] or data["references"]:
  raise RuntimeError("Preserved instrumental/reference index structures require manual review")
 intro=a.split_chords(data["intro"])
 if [a.chord_root(x) for x in intro]!=["A","C#","D","E"]:
  raise RuntimeError("Original song intro key progression differs")
 scaffold=[]
 for idx,line in enumerate(old):
  check=detector.row(line)
  if check["suspect"]:scaffold.append((idx,check["symbols"]))
 if len(scaffold)!=EXPECTED_SCAFFOLDS or sum(len(s) for _,s in scaffold)!=EXPECTED_HIDDEN_CHORDS:
  raise RuntimeError("Chord scaffold pattern has changed; no write")
 all_scaffold={i for i,_ in scaffold}
 # Adjacent chord-only rows may represent a riff or independent instrumental.
 # Keep ambiguous groups byte-for-byte; convert only one-to-one line anchors.
 unsafe={i for i,_ in scaffold if i-1 in all_scaffold or i+1 in all_scaffold}
 approved=[(i,s) for i,s in scaffold if i not in unsafe and i+1<len(old) and i+1 not in all_scaffold and old[i+1].strip()]
 removed={i for i,_ in approved}
 if len(approved)<26 or len(unsafe)>7:raise RuntimeError("Too many ambiguous chord rows")
 new_lines=[line for idx,line in enumerate(old) if idx not in removed]
 idx_map={old_i:new_i for new_i,old_i in enumerate(i for i in range(len(old)) if i not in removed)}
 if len(new_lines)!=len(old)-len(approved):raise RuntimeError("Index mapping differs")
 new_data=copy.deepcopy(data)
 new_data["words"]={}
 for key,v in data["words"].items():
  if not str(v).strip():continue
  old_line,word=(int(x) for x in key.split(":"))
  if old_line not in idx_map:raise RuntimeError("A previous word chord falls on a scaffold")
  if not 0<=word<len(new_lines[idx_map[old_line]].split()):
   raise RuntimeError("Invalid old word anchor after remapping")
  new_data["words"][f"{idx_map[old_line]}:{word}"]=v
 new_data["lines"]={}
 for key,v in data["lines"].items():
  if not str(v).strip():continue
  old_line=int(key)
  if old_line not in idx_map:raise RuntimeError("Old full-line chord collides with scaffold")
  new_data["lines"][str(idx_map[old_line])]=v
 imported=[]
 destination_indexes=set()
 for source_index,symbols in approved:
  next_idx=source_index+1
  # Scaffolds must be directly followed by actual lyrics, not another
  # scaffold, section heading or an empty line.
  if next_idx>=len(old) or next_idx in removed or not old[next_idx].strip():
   raise RuntimeError(f"Unsafe chord-only row {source_index}: no adjacent lyric")
  if next_idx in destination_indexes:
   raise RuntimeError("Two scaffolds claim same lyric")
  destination_indexes.add(next_idx)
  mapped=idx_map[next_idx]
  if str(mapped) in new_data["lines"] and new_data["lines"][str(mapped)].strip():
   raise RuntimeError("Existing line chords on targeted lyric; would conflict")
  if not (2<=len(symbols)<=5 and all(a.is_chord(t) for t in symbols)):
   raise RuntimeError("Invalid source symbol progression")
  new_data["lines"][str(mapped)]=" · ".join(symbols)
  imported.append({"oldSourceLine":source_index,"originalTargetLine":next_idx,
    "newTargetLine":mapped,"symbols":symbols})
 if len(imported)!=len(approved) or len(new_data["lines"])!=len(approved):
  raise RuntimeError("Scaffolds not transferred one for one")
 approved_symbols=sum(len(s) for _,s in approved)
 if a.count_chords(new_data)!=EXPECTED_EXISTING_CHORDS+approved_symbols:
  raise RuntimeError("Chord-symbol count differs from transferred formatting")
 if new_data["intro"]!=data["intro"] or new_data["introText"]!=data["introText"]:
  raise RuntimeError("Intro altered")
 if new_data["references"]!=data["references"]:
  raise RuntimeError("References altered")
 if sum(bool(x.strip()) for x in new_lines)!=len(new_lines):
  raise RuntimeError("Unexpected blank lyrics following conversion")
 # Strong integrity property: removing inserted formatting lines from the
 # new lyric text reproduces all original non-scaffold lines byte-for-byte.
 original_only=[x for i,x in enumerate(old) if i not in removed]
 if new_lines!=original_only:raise RuntimeError("Unexpected lyric change")
 meta={"id":SID,"title":TITLE,"source":"existing_user_imported_chord_only_rows",
  "readOnly":not APPLY,"oldPhysicalLines":78,"newPhysicalLines":len(new_lines),
  "removedFormattingOnlyRows":len(approved),"chordSymbolsRecovered":approved_symbols,
  "chordRowsLeftForManualReview":sorted(unsafe),
  "previouslyStoredNativeChords":6,
  "newNativeChordCount":a.count_chords(new_data),
  "lineChordSequences":len(imported),
  "wordChordsPreserved":len(data["words"]),
  "introUntouched":True,"passesUntouched":True,
  "originalNonChordTextPreservedByteForByte":True,
  "newLineAnchors":[{"newIndex":x["newTargetLine"],"count":len(x["symbols"])} for x in imported]}
 return "\n".join(new_lines),new_data,meta

def write(name,x):
 (OUT/name).write_text(json.dumps(x,ensure_ascii=False,indent=2)+"\n")
 print(name.upper()+"="+json.dumps(x,ensure_ascii=False),flush=True)

def main():
 state,songs,meta=live()
 text,new_chords,detail=candidate(songs[SID])
 write("PREVIEW.json",detail)
 if not APPLY:return
 fresh,now_songs,_=live()
 if stamp(fresh)!=stamp(state) or now_songs[SID]["texto"]!=songs[SID]["texto"]:
  raise RuntimeError("Live state changed since preflight")
 b=requests.post(a.LIVE_BASE+"/api/backups",headers=HEADERS,json={"action":"create"},timeout=30)
 b.raise_for_status()
 back=b.json()
 if not (back.get("ok") and back.get("id")):
  raise RuntimeError("Manual D1 backup failed; no write")
 verified,check,latest=live()
 if stamp(verified)!=stamp(state):
  raise RuntimeError("Cloudflare state changed since backup; no write")
 ts=int(latest.get("payload",{}).get("updatedAt",-1))
 if ts<=0:raise RuntimeError("No optimistic D1 version")
 updated=copy.deepcopy(state)
 updated[f"quintoElemento.lyrics.v1.{SID}"]=text
 updated[f"quintoElemento.chords.v2.{SID}"]=json.dumps(new_chords,ensure_ascii=False,separators=(",",":"))
 reply=requests.put(a.LIVE_BASE+"/api/sync",headers=HEADERS,
                    json={"data":updated,"expectedUpdatedAt":ts},timeout=65)
 reply.raise_for_status()
 if reply.json().get("ok") is not True:raise RuntimeError("D1 did not confirm write")
 actual,post,_=live()
 if stamp(actual)!=stamp(updated):
  raise RuntimeError("Post write snapshot mismatch: restore backup "+str(back["id"]))
 if post[SID]["texto"]!=text or post[SID]["letraConAcordes"]!=new_chords:
  raise RuntimeError("Post write song map mismatch; backup "+str(back["id"]))
 if len(post)!=len(songs):raise RuntimeError("Unexpected change in song inventory")
 detail.update({"status":"APPLIED_AND_VERIFIED","backupId":back["id"],
  "originalStorageKeys":len(state),"currentStorageKeys":len(updated)})
 write("APPLIED.json",detail)

if __name__=="__main__":main()
