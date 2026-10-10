#!/usr/bin/env python3
"""Read-only secondary audit: LA CUERDA and TUCUATRO original lyrics/chords.

Never writes copyrighted lyrics to disk; reports structural metrics, source
fingerprints, mapping confidence and tonal agreement only.
"""
import collections
import hashlib
import json
import re
from pathlib import Path
import requests
from bs4 import BeautifulSoup
import audit_songbook as a
import strict_line_chords_86 as align
import audit_alternative_sources_86 as alt

OUT=Path("eqe-priority-outside-sources")
OUT.mkdir(exist_ok=True)

TARGETS={
 5:{"title":"AQUÍ NO HAY PLAYA","artist":"The Refrescos",
    "url":"https://acordes.lacuerda.net/the_refrescos/aqui_no_hay_playa.shtml",
    "backup":"https://www.acordesytabs.com/28157/The-Refrescos/Aqui-no-hay-playa.html"},
 51:{"title":"QUÉ NAVIDAD TAN ESPECIAL","artist":"Morella Muñoz",
    "url":"https://tucuatro.com/es/cancion/que-navidad/",
    "backup":None},
}
def clean_chordline(value):
 line=str(value).replace("_"," ").replace("\xa0"," ")
 if not line.strip():return None
 # Inline punctuation like (MI) is a valid chord, not a lyric anchor.
 tokens=re.findall(r"\S+",line)
 good=[x.strip("[](){}.,;:") for x in tokens]
 if good and all(a.is_chord(x) for x in good):
  return " ".join("[ch]"+x+"[/ch]" for x in good)
 return None

def extract_pre_models(html):
 soup=BeautifulSoup(html,"html.parser")
 candidates=[]
 for tag in soup.select("pre, .letra, .lyrics, #letra, #lyrics, #chordsPre, .cancion"):
  t=tag.get_text("\n",strip=False)
  if t and len(t)>250:candidates.append((tag.name,str(tag.get("class",[])),t))
 if not candidates:
  # Fallback only for public document reading, not as an authoritative match.
  candidates.append(("body","fallback",soup.get_text("\n",strip=False)))
 return candidates

def to_model(text):
 transformed=[]
 pending=""
 source_chord_lines=0
 for raw in text.replace("\r\n","\n").splitlines():
  s=raw.rstrip()
  if not s.strip():
   if pending:continue
   continue
  if re.search(r"^(?:intro|parte|solos|afinacion|en el ole|los acordes son|este es el tono|tono:)",a.deaccent(s).strip(),re.I):
   continue
  ch=clean_chordline(s)
  if ch:
   if pending:transformed.append(pending)
   pending=ch
   source_chord_lines+=1
  else:
   if pending:
    transformed.append(pending)
    pending=""
   transformed.append(s)
 if pending:transformed.append(pending)
 m=a.ug_to_model("\n".join(transformed))
 return m,source_chord_lines

def score_source(song,model):
 matches=align.source_line_matches(model,align.segment_candidates(song["texto"]))
 confident=[x for x in matches if x["score"]>=.985]
 map_chords=collections.defaultdict(set)
 for x in confident:
  for line,word,ch in x["placements"]:
   if a.is_chord(ch):
    map_chords[f"{line}:{word}"].add(ch)
 unique={k:next(iter(v)) for k,v in map_chords.items() if len(v)==1}
 old=a.normalize_chord_data(song["letraConAcordes"])
 roots=alt.roots_agreement(old,unique)
 covered={int(k.split(":")[0]) for k,v in old["words"].items() if v}
 covered.update(int(k) for k,v in old["lines"].items() if v and str(k).isdigit())
 new={k:v for k,v in unique.items() if not old["words"].get(k) and int(k.split(":")[0]) not in covered}
 return {"wholeLyricsSimilarityPct":round(100*a.similarity(song["texto"],model["lyrics"]),1),
   "sourceChordPositions":len(model["placements"]),
   "strongExactLineMatches":len(confident),
   "uniqueChordSlots":len(unique),"contradictorySourceSlots":sum(len(v)>1 for v in map_chords.values()),
   "previousChordCount":a.count_chords(old),"newSlotsOnUnchordedLines":len(new),
   "newLyricLinesCovered":len({k.split(":")[0] for k in new}),
   **{k:v for k,v in roots.items() if k!="shiftScores"}}

def main():
 storage,_=a.load_remote_storage()
 songs={int(s["id"]):s for s in a.build_songbook(storage)}
 results=[]
 for sid,info in TARGETS.items():
  if align.normalize_label(songs[sid]["titulo"])!=align.normalize_label(info["title"]):
   raise RuntimeError("Wrong title for ID "+str(sid))
  urls=[u for u in (info["url"],info.get("backup")) if u]
  variants=[]
  for url in urls:
   try:
    a.limiter.wait()
    response=requests.get(url,timeout=28,headers={"User-Agent":"Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/120.0 Safari/537.36"})
    response.raise_for_status()
    raw=response.text
    blocks=extract_pre_models(raw)
    sub=[]
    for tag,cls,content in blocks:
     model,chord_lines=to_model(content)
     if not model["placements"]:continue
     summary=score_source(songs[sid],model)
     summary.update({"tag":tag,"class":cls,"sourceChordLines":chord_lines,
       "chordModelSha256":hashlib.sha256(json.dumps({"lyrics":model["lines"],"anchors":model["placements"]},ensure_ascii=False,sort_keys=True).encode()).hexdigest()})
     sub.append(summary)
    sub.sort(key=lambda r:(r["strongExactLineMatches"],r["newLyricLinesCovered"]),reverse=True)
    variants.append({"sourceURL":url,"httpStatus":response.status_code,
       "htmlSha256":hashlib.sha256(raw.encode()).hexdigest(),
       "blocksInspected":len(blocks),"best":sub[:3],"status":"ok"})
   except Exception as e:
    variants.append({"sourceURL":url,"status":"unavailable","error":str(e)[:180]})
  best=sorted([b for v in variants for b in v.get("best",[])],
    key=lambda z:(z["strongExactLineMatches"],z["newLyricLinesCovered"]),reverse=True)
  item={"id":sid,"title":info["title"],"artist":info["artist"],"currentLyricLines":len([s for s in songs[sid]["texto"].splitlines() if s.strip()]),"sources":variants,
    "bestCandidate":best[0] if best else None, "safeToApplyWithoutReview":False}
  results.append(item)
  print("PRIORITY_CHORD_SOURCE="+json.dumps(item,ensure_ascii=False),flush=True)
 report={"readOnly":True,"songCount":len(songs),"sourceAudit":results}
 (OUT/"READONLY_PRIORITY_SOURCE_AUDIT.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
 print("TWO_SOURCE_AUDIT_COMPLETED=YES",flush=True)
if __name__=="__main__":main()
