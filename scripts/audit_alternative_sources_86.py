#!/usr/bin/env python3
"""Independent second-source audit for poorly covered EQE songs.

Fetch chord symbols and source-line positions from AcordesWeb, then map only
near-identical lyric fragments onto CURRENT D1, without copying source lyrics
to disk or changing D1. Different musical key / partial sources are flagged.
"""
import collections
import hashlib
import json
import os
import re
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup

import audit_songbook as a
import strict_line_chords_86 as align
from audit_repeated_chords_86 import validate_state,load_state

OUT=Path("eqe-alternative-sources")
OUT.mkdir(exist_ok=True)

SOURCES={
 39:("LOS OLVIDADOS","Pedro Pastor","https://acordesweb.com/cancion/pedro-pastor/los-olvidados"),
 43:("MI AGÜITA AMARILLA","Toreros Muertos","https://acordesweb.com/cancion/toreros-muertos/mi-agita-amarilla"),
 62:("TE SIGO SOÑANDO","Depedro","https://acordesweb.com/cancion/depedro/te-sigo-sonando"),
 73:("ESCUELA DE CALOR","Radio Futura","https://acordesweb.com/cancion/radio-futura/escuela-de-calor"),
 77:("SABOR DE AMOR","Danza Invisible","https://acordesweb.com/cancion/danza-invisible/sabor-de-amor"),
 80:("EL RITMO DEL GARAJE","Loquillo","https://acordesweb.com/cancion/loquillo/el-ritmo-del-garaje")
}
def fetch_sheet(url):
 a.limiter.wait()
 r=requests.get(url,timeout=27,headers={"User-Agent":"Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/120.0 Safari/537.36"})
 r.raise_for_status()
 html=r.text
 soup=BeautifulSoup(html,"html.parser")
 pre=soup.select_one("pre#chordsPre") or soup.select_one("pre")
 if not pre:
  raise RuntimeError("No chord sheet pre element")
 raw_chord_tags=0
 for item in list(pre.select("a")):
  t=item.get_text(" ",strip=True)
  if not a.is_chord(t):continue
  item.replace_with(" [ch]"+t+"[/ch] ")
  raw_chord_tags+=1
 for br in list(pre.select("br")):
  br.replace_with("\n")
 data=pre.get_text("",strip=False)
 # HTML escaped text and tabs are retained inside pre.
 filtered=[]
 for li in data.replace("\xa0"," ").splitlines():
  stripped=li.strip()
  if not stripped:filtered.append("");continue
  if re.match(r"^(?:Intro|Instrumental|Verse|Coro|Estribillo|Solo)\s*:\s*$",stripped,re.I):continue
  if re.search(r"(?:afinacion:|capo:|tuning:|copyright)",stripped,re.I):continue
  filtered.append(li)
 model=a.ug_to_model("\n".join(filtered))
 return model,{"http":r.status_code,"htmlSha256":hashlib.sha256(html.encode()).hexdigest(),
    "sourceChordLinks":raw_chord_tags,"sourceParsedLyricLines":len(model["lines"]),
    "sourceParsedChordPositions":len(model["placements"]),"sourceLinesRaw":len(filtered)}

def roots_agreement(existing,safe):
 overlap=[]
 for key,chord in safe.items():
  old=str(existing["words"].get(key,"") or "")
  if old and a.chord_root(old) in a.CHROMATIC and a.chord_root(chord) in a.CHROMATIC:
   overlap.append((a.chord_root(old),a.chord_root(chord)))
 shift_scores=[]
 for shift in range(12):
  matches=sum(a.CHROMATIC[(a.CHROMATIC.index(s)+shift)%12]==d for d,s in overlap)
  shift_scores.append({"shift":shift,"matches":matches})
 shift_scores.sort(key=lambda x:(-x["matches"],x["shift"]))
 confidence=shift_scores[0]["matches"]/max(1,len(overlap))
 margin=(shift_scores[0]["matches"]-shift_scores[1]["matches"])/max(1,len(overlap))
 return {"existingOverlaps":len(overlap),"candidateShift":shift_scores[0]["shift"],
   "existingRootAgreementPct":round(100*confidence,1),"shiftMarginPct":round(100*margin,1),
   "shiftScores":shift_scores}

def audit(song,model,metadata):
 old=a.normalize_chord_data(song["letraConAcordes"])
 rawlines=song["texto"].splitlines()
 matches=align.source_line_matches(model,align.segment_candidates(song["texto"]))
 strong=[m for m in matches if m["score"]>=.985]
 chords=collections.defaultdict(set)
 for m in strong:
  for li,wi,ch in m["placements"]:
   if a.is_chord(ch) and 0<=li<len(rawlines) and 0<=wi<len(rawlines[li].split()):
    chords[f"{li}:{wi}"].add(ch)
 unique={k:next(iter(v)) for k,v in chords.items() if len(v)==1}
 conflict=sum(len(v)>1 for v in chords.values())
 overlap=roots_agreement(old,unique)
 old_lines=set(int(k.split(":")[0]) for k,v in old["words"].items() if v and k.split(":")[0].isdigit())
 old_lines.update(int(k) for k,v in old["lines"].items() if v and k.isdigit())
 new={k:v for k,v in unique.items() if k not in old["words"] or not old["words"][k]}
 unfilled={k:v for k,v in new.items() if int(k.split(":")[0]) not in old_lines}
 unchanged_chord_count=a.count_chords(old)
 result={
  "id":song["id"],"title":song["titulo"],
  "currentLyricLines":sum(bool(x.strip()) for x in rawlines),
  "currentChordCount":unchanged_chord_count,"currentlyCoveredLyricLines":len(old_lines),
  "fullLyricSimilarityPct":round(a.similarity(song["texto"],model["lyrics"])*100,1),
  "exactSourceFragmentsMatched":len(strong),"potentialUniqueChordPositions":len(unique),
  "conflictingSourcePositions":conflict,"potentialNewChordPositions":len(new),
  "potentialNewAnchorsOnBlankLines":len(unfilled),
  "potentialNewLyricLinesCovered":len(set(int(k.split(":")[0]) for k in unfilled)),
  **overlap,**metadata
 }
 # Do not treat the chords as source-authoritative without independent
 # confirmation of matching key and sufficient existing-harmony overlap.
 result["safeForAutomaticUpdate"]=(len(strong)>=6 and len(unfilled)>=5
    and result["fullLyricSimilarityPct"]>=85
    and result["existingOverlaps"]>=6
    and result["existingRootAgreementPct"]>=90
    and result["shiftMarginPct"]>=15
    and result["candidateShift"]==0
    and conflict==0)
 result["status"]="auto_candidate_requires_final_recheck" if result["safeForAutomaticUpdate"] else "manual_harmony_or_source_review"
 return result

def main():
 storage,_=load_state()
 by_id={int(s["id"]):s for s in validate_state(storage)}
 result=[]
 for sid,(title,artist,url) in SOURCES.items():
  if align.normalize_label(by_id[sid]["titulo"])!=align.normalize_label(title):
   raise RuntimeError("D1 title mismatch ID "+str(sid))
  try:
   model,meta=fetch_sheet(url)
   row=audit(by_id[sid],model,meta)
   row["artist"]=artist
   row["sourceURL"]=url
  except Exception as e:
   row={"id":sid,"title":title,"artist":artist,"sourceURL":url,
       "status":"source_unavailable","error":str(e)[:220],"safeForAutomaticUpdate":False}
  result.append(row)
  print("ALT_SOURCE="+json.dumps(row,ensure_ascii=False),flush=True)
 output={"currentInventory":len(by_id),"readOnly":True,"sourceCount":len(SOURCES),
   "autoCandidates":sum(bool(x["safeForAutomaticUpdate"]) for x in result),
   "sources":result}
 (OUT/"ALTERNATIVE_CHORD_SOURCE_REPORT.json").write_text(json.dumps(output,ensure_ascii=False,indent=2)+"\n")
 print("ALTERNATIVE_SOURCE_AUDIT_DONE="+json.dumps({"count":len(result),"autoCandidates":output["autoCandidates"]}),flush=True)
if __name__=="__main__":main()
