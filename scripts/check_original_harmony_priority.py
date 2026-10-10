#!/usr/bin/env python3
"""Read-only validation of original artist chord sheets against current EQE lyrics.

No raw lyrics or scraped chord-sheet text are exported. No D1 write. Attempts
the exact artist's LaCuerda/CifraClub URLs, compares source annotations with
up-to-five-line contiguous excerpts in the current arrangement, records tonal
agreement and new chord suggestions only for matching lines.
"""
import collections
import hashlib
import json
import re
import time
from pathlib import Path
import requests
from bs4 import BeautifulSoup

import audit_songbook as a
import strict_line_chords_86 as align
import audit_current_chord_coverage as cov

OUT=Path("eqe-priority-harmony-audit")
OUT.mkdir(exist_ok=True)
TARGETS={
  26:{"title":"ESPALDAS MOJADAS","artist":"Tam Tam Go","sources":[
    "https://acordes.lacuerda.net/tam_tam_go/espaldas_mojadas.shtml",
    "https://acordes.lacuerda.net/tam_tam_go/espaldas_mojadas-3.shtml",
    "https://www.cifraclub.com/tam-tam-go/espaldas-mojadas/thkghw.html"]},
  62:{"title":"TE SIGO SOÑANDO","artist":"Depedro","sources":[
    "https://acordes.lacuerda.net/depedro/te_sigo_soniando.shtml",
    "https://acordes.lacuerda.net/depedro/te_sigo_soniando-2.shtml",
    "https://acordesweb.com/cancion/depedro/te-sigo-sonando"]},
  73:{"title":"ESCUELA DE CALOR","artist":"Radio Futura","sources":[
    "https://acordes.lacuerda.net/radio_futura/escuela_de_calor-2.shtml",
    "https://www.cifraclub.com/radio-futura/la-escuela-de-calor/",
    "https://www.cifraclub.com/radio-futura/escuela-de-calor/tzgkmw.html"]},
}
def is_tab_line(line):
 s=line.lstrip()
 return bool(re.match(r"^(?:[eBGDAE]\|+|\|[eBGDAE]\||[eBGDAE]:|[xX]-)[-0-9A-Za-z\|/\\~.+()*^\s]+$",s))
def is_chord_row(raw):
 s=str(raw).strip().replace("\xa0"," ")
 if not s or len(s)>190 or is_tab_line(s):return False
 toks=re.findall(r"\S+",s)
 if len(toks)>12:return False
 good=[x.strip("[](){}.,;:") for x in toks]
 return bool(good) and all(a.is_chord(x) for x in good)
def token_placements(chordline,lyric):
 starts=[m.start() for m in re.finditer(r"\S+",lyric)]
 if not starts:return []
 res=[]
 for m in re.finditer(r"\S+",chordline):
  chord=m.group().strip("[](){}.,;:")
  if not a.is_chord(chord):continue
  wi=min(range(len(starts)),key=lambda j:abs(starts[j]-m.start()))
  res.append((wi,chord))
 return res
def lyric_row(raw):
 s=raw.rstrip("\r\n").strip()
 if not s or is_tab_line(s) or is_chord_row(s):return None
 if re.match(r"^(?:riff|intro|instrumental|solo|estribillo|coro|estrofa|puente|final|tab|tonalidad|capo|cejilla|afinacion|repite|\[)",a.deaccent(s).lower()):return None
 if sum(c.isalpha() for c in s)<8:return None
 if re.search(r"[|]{2,}",s):return None
 return s
def prepare_pre(raw):
 result=[];placements=[];pending=None
 for line in str(raw).replace("\r\n","\n").replace("\r","\n").splitlines():
  if not line.strip():continue
  if is_tab_line(line):pending=None;continue
  if is_chord_row(line):
   pending=line
   continue
  lyr=lyric_row(line)
  if not lyr:pending=None;continue
  li=len(result)
  result.append(lyr)
  if pending:
   placements += [{"line":li,"word":w,"chord":ch} for w,ch in token_placements(pending,lyr)]
  pending=None
 return {"lines":result,"placements":placements,"lyrics":"\n".join(result)}
def model_blocks(html):
 soup=BeautifulSoup(html,"html.parser")
 choices=soup.select("pre, pre#chordsPre, div.cifra_cnt, div.cifra, .chordLyrics")
 blocks=[]
 for tag in choices:
  if tag.name=="pre":
   text=tag.get_text("\n",strip=False)
  else:
   # Keep line breaks for chord positions.
   for br in tag.select("br"):br.replace_with("\n")
   text=tag.get_text("",strip=False)
  if len(text)>150:blocks.append((tag.name,text))
 return blocks
def summarize(song,model):
 seg=align.segment_candidates(song["texto"],max_lines=5)
 rows=align.source_line_matches(model,seg)
 agree=collections.defaultdict(set)
 for r in rows:
  if r["score"]<.985:continue
  for li,wi,chord in r["placements"]:
   if a.is_chord(chord):agree[f"{li}:{wi}"].add(chord)
 accepted={k:next(iter(vals)) for k,vals in agree.items() if len(vals)==1}
 conflict={k:vals for k,vals in agree.items() if len(vals)>1}
 old=a.normalize_chord_data(song["letraConAcordes"])
 old_covered={int(k.split(":")[0]) for k,v in old["words"].items() if str(v).strip()}
 old_covered.update(int(k) for k,v in old["lines"].items() if str(v).strip() and str(k).isdigit())
 additional={k:v for k,v in accepted.items() if int(k.split(":")[0]) not in old_covered and not old["words"].get(k)}
 roots=[]
 for k,ch in accepted.items():
  cur=old["words"].get(k)
  if cur and a.chord_root(cur) and a.chord_root(ch):
   roots.append((a.chord_root(cur),a.chord_root(ch)))
 shifts=[]
 for sh in range(12):
  hits=sum(
   a.CHROMATIC[(a.CHROMATIC.index(src)+sh)%12]==dest
   for dest,src in roots if src in a.CHROMATIC and dest in a.CHROMATIC
  )
  shifts.append({"shift":sh,"hits":hits})
 shifts.sort(key=lambda o:(-o["hits"],o["shift"]))
 best=shifts[0]
 return {
  "sourceLyricLines":len(model["lines"]),
  "sourceChordPlacements":len(model["placements"]),
  "fullTextSimilarityPct":round(100*a.similarity(song["texto"],model["lyrics"]),1),
  "highConfidenceSegments":len([r for r in rows if r["score"]>=.985]),
  "uniqueMappedPositions":len(accepted),
  "contradictions":len(conflict),
  "newChordPositionsOnUnchordedLines":len(additional),
  "newlyCoveredLines":len({k.split(":")[0] for k in additional}),
  "matchingOldChordLocations":len(roots),
  "bestTransposition":best["shift"],
  "bestTranspositionAgreementPct":round(100*best["hits"]/max(1,len(roots)),1),
  "secondBestAgreementPct":round(100*shifts[1]["hits"]/max(1,len(roots)),1),
  "rawExistingRoots":dict(collections.Counter(x for x,_ in roots)),
  "chordSymbolSamples":dict(list(collections.Counter(x for x in old["words"].values() if str(x).strip()).most_common(8))),
  "autoApply":False,
  "reason":"Require ≥85% full lyrics, ≥5 root overlaps, ≥90% harmonic agreement and no conflicting positions."
 }
def main():
 storage,meta=a.load_remote_storage()
 songs={int(x["id"]):x for x in a.build_songbook(storage)}
 if len(songs)!=88:raise RuntimeError("Expected 88 live songs, got "+str(len(songs)))
 passes=cov.parse(storage.get("quintoElemento.passes.v1","[]"),[])
 pasma=[p for p in passes if cov.norm(p.get("name"))==cov.norm("LA PASMA (NUEVA)")]
 if len(pasma)!=1 or len(pasma[0].get("songs",[]))!=23:raise RuntimeError("Pasma no longer has 23 songs")
 results=[]
 for sid,cfg in TARGETS.items():
  song=songs[sid]
  if align.normalize_label(song["titulo"])!=align.normalize_label(cfg["title"]):raise RuntimeError("Song ID moved: "+str(sid))
  old=a.normalize_chord_data(song["letraConAcordes"])
  rec={"id":sid,"title":song["titulo"],"expectedArtist":cfg["artist"],
       "existingChordCount":a.count_chords(old),"sources":[]}
  for url in cfg["sources"]:
   a.limiter.wait()
   try:
    res=requests.get(url,timeout=24,headers={"User-Agent":"Mozilla/5.0 (Macintosh; Intel Mac OS X 13_6) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"})
    res.raise_for_status()
    models=[(tag,prepare_pre(raw)) for tag,raw in model_blocks(res.text)]
    scored=[]
    for tag,model in models:
     if not model["placements"]:continue
     cand=summarize(song,model)
     cand["tag"]=tag
     scored.append(cand)
    scored.sort(key=lambda x:(x["newlyCoveredLines"],x["fullTextSimilarityPct"]),reverse=True)
    rec["sources"].append({"url":url,"http":res.status_code,"htmlSha256":hashlib.sha256(res.content).hexdigest(),"blocks":len(models),"best":scored[:2]})
   except Exception as e:
    rec["sources"].append({"url":url,"error":str(e)[:130]})
  results.append(rec)
  print("HARMONY_AUDIT="+json.dumps(rec,ensure_ascii=False),flush=True)
 report={"readOnly":True,"songCount":len(songs),"pasmaCount":len(pasma[0]["songs"]),"targets":results,
         "liveUpdatedAt":meta.get("payload",{}).get("updatedAt")}
 (OUT/"PRIORITY_HARMONY_SOURCE_CHECK.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
 print("HARMONY_AUDIT_COMPLETE=YES",flush=True)
if __name__=="__main__":main()
