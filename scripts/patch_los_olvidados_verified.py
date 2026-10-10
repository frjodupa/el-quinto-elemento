#!/usr/bin/env python3
"""Single-song chord-only patch for LOS OLVIDADOS, Pedro Pastor.

Cautious source pinned at AcordesWeb; only nine *previously blank*
lines may gain chords. All existing lyrics/chords/metadata and 23-song PASMA
pass remain intact. Uses Cloudflare backup and live checksum verification.
Dry-run unless APPLY_VERIFIED_LOS_OLVIDADOS=1.
"""
import copy
import hashlib
import json
import os
from collections import defaultdict
from pathlib import Path
import requests

import audit_songbook as a
import strict_line_chords_86 as align
import audit_alternative_sources_86 as sources

SID=39
TITLE="LOS OLVIDADOS"
URL="https://acordesweb.com/cancion/pedro-pastor/los-olvidados"
SOURCE_SHA="b44823941f0ea6bfc3373658be20adb091cf7e2767381b1af6a096d125ff9dfe"
OUT=Path("eqe-los-olvidados-guarded")
OUT.mkdir(exist_ok=True)
APPLY=os.getenv("APPLY_VERIFIED_LOS_OLVIDADOS","0")=="1"
HEADERS={**a.HEADERS,"Content-Type":"application/json"}

def compact_hash(storage):
 return hashlib.sha256(json.dumps(storage,ensure_ascii=False,sort_keys=True,separators=(",",":")).encode()).hexdigest()

def snapshot():
 storage,meta=a.load_remote_storage()
 songs={int(x["id"]):x for x in a.build_songbook(storage)}
 if not 86<=len(songs)<=120 or SID not in songs:
  raise RuntimeError("Live inventory changed unexpectedly; no write")
 if align.normalize_label(songs[SID]["titulo"])!=align.normalize_label(TITLE):
  raise RuntimeError("Current ID 39 no longer matches Pedro Pastor title")
 return storage,songs[SID],meta

def plan(song,model):
 old=a.normalize_chord_data(song["letraConAcordes"])
 if a.count_chords(old)!=13:raise RuntimeError("Song baseline chord count changed: stop")
 matches=align.source_line_matches(model,align.segment_candidates(song["texto"]))
 strong=[m for m in matches if m["score"]>=.985]
 if len(strong)<50:raise RuntimeError("Fewer original matching lyric fragments than validated")
 anchor=defaultdict(set)
 for match in strong:
  for li,wi,ch in match["placements"]:
   if not a.is_chord(ch):continue
   if not 0<=li<len(song["texto"].splitlines()):continue
   if not 0<=wi<len(song["texto"].splitlines()[li].split()):continue
   anchor[f"{li}:{wi}"].add(ch)
 unambiguous={k:next(iter(v)) for k,v in anchor.items() if len(v)==1}
 ambiguous={k for k,v in anchor.items() if len(v)>1}
 verify=sources.roots_agreement(old,unambiguous)
 if not (verify["existingOverlaps"]>=9
         and verify["candidateShift"]==0
         and verify["existingRootAgreementPct"]==100
         and verify["shiftMarginPct"]>=50):
  raise RuntimeError("Current song tonality no longer confirmed")
 protected_lines=set(int(k.split(":")[0]) for k,v in old["words"].items() if v)
 protected_lines.update(int(k) for k,v in old["lines"].items() if v and str(k).isdigit())
 eligible={}
 for key,chord in unambiguous.items():
  li=int(key.split(":")[0])
  if key in ambiguous or li in protected_lines or old["words"].get(key):continue
  if not a.is_chord(chord):continue
  eligible[key]=chord
 distinct=len({k.split(":")[0] for k in eligible})
 if len(eligible)!=9 or distinct!=9:
  raise RuntimeError(f"Expected exactly 9 previously blank lines, got {len(eligible)} anchors on {distinct} lines")
 updated=copy.deepcopy(old)
 for key,chord in eligible.items():updated["words"][key]=chord
 if a.count_chords(updated)!=22:raise RuntimeError("Expected 13 + 9 chord symbols")
 for section in ("lines","intro","introText","instrumentals","instrumentalsText","references"):
  if updated[section]!=old[section]:raise RuntimeError("Protected section changed: "+section)
 for key,ch in old["words"].items():
  if updated["words"].get(key)!=ch:raise RuntimeError("Old chord changed")
 detail={"id":SID,"title":TITLE,"source":URL,"sourceSha256":SOURCE_SHA,
  "readOnly":not APPLY,"matchingLyricFragments":len(strong),
  "sourceAmbiguousChordPositionsExcluded":len(ambiguous),
  "oldChords":13,"addedChordPositions":len(eligible),"newChords":22,
  "newlyCoveredPhysicalLines":distinct,"keyAgreementPct":verify["existingRootAgreementPct"],
  "keyShift":0,"originalLyricsUnchanged":True,
  "introInstrumentalReferencesPreserved":True,
  "keysAddedAtOriginalWordIndices":sorted(eligible, key=lambda s:tuple(map(int,s.split(":"))))}
 return updated,detail

def dump(filename,v):
 (OUT/filename).write_text(json.dumps(v,ensure_ascii=False,indent=2)+"\n")
 print(filename.upper()+"="+json.dumps(v,ensure_ascii=False),flush=True)

def main():
 storage,song,meta=snapshot()
 model,m=sources.fetch_sheet(URL)
 if m["htmlSha256"]!=SOURCE_SHA:
  raise RuntimeError("Original external chord source changed: stop")
 updated,detail=plan(song,model)
 dump("PREVIEW.json",detail)
 if not APPLY:return
 # optimistic D1 concurrency lock - do not overwrite a more recent user edit.
 current,cur_song,_=snapshot()
 if compact_hash(current)!=compact_hash(storage):
  raise RuntimeError("Live storage changed after preflight, abort no writes")
 if cur_song["letraConAcordes"]!=song["letraConAcordes"] or cur_song["texto"]!=song["texto"]:
  raise RuntimeError("Live lyrics/chords changed, abort")
 b=requests.post(a.LIVE_BASE+"/api/backups",headers=HEADERS,json={"action":"create"},timeout=30)
 b.raise_for_status()
 back=b.json()
 if not (back.get("ok") and back.get("id")):
  raise RuntimeError("Cloudflare backup unconfirmed: no song write")
 fresh,_,_=snapshot()
 if compact_hash(fresh)!=compact_hash(storage):
  raise RuntimeError("Live changed after backup, safe abort")
 target=copy.deepcopy(storage)
 target["quintoElemento.chords.v2.39"]=json.dumps(updated,ensure_ascii=False,separators=(",",":"))
 res=requests.put(a.LIVE_BASE+"/api/sync",json={"data":target},headers=HEADERS,timeout=60)
 res.raise_for_status()
 if res.json().get("ok") is not True:raise RuntimeError("Sync not confirmed")
 observed,live_song,_=snapshot()
 if compact_hash(observed)!=compact_hash(target):
  raise RuntimeError("Post write D1 hash mismatch; backup ID "+str(back["id"]))
 if live_song["texto"]!=song["texto"] or live_song["letraConAcordes"]!=updated:
  raise RuntimeError("Post write lyrics/chords integrity failed; backup ID "+str(back["id"]))
 detail.update({"status":"APPLIED_AND_VERIFIED","backupId":back["id"],
   "liveSnapshotKeys":len(storage),"newSnapshotKeys":len(observed)})
 dump("APPLIED.json",detail)

if __name__=="__main__":main()
