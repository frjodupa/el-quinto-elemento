#!/usr/bin/env python3
"""Source-safe multi-version investigation of every low-chord-coverage song.
Never writes to the worker, alters song text or distributes third-party lyrics.
Records only candidate title, artist, source URL/hash and chord coverage metrics.
"""
import collections
import hashlib
import json
import os
import re
import time
from pathlib import Path

import audit_songbook as a
import audit_current_chord_coverage as cov
import strict_line_chords_86 as align

OUT=Path("eqe-ug-comparison")
OUT.mkdir(exist_ok=True)

ARTISTS={
  7:"No me pises que llevo chanclas",
  8:"Amparanoia",
  13:"Maná",
  16:"Orquesta Mondragón",
  17:"Radio Futura",
  20:"Asfalto",
  21:"Kiko Veneno",
  23:"Ska-P",
  25:"Jarabe de Palo",
  26:"Tam Tam Go",
  35:"Radio Futura",
  39:"Pedro Pastor",
  42:"Julio Iglesias",
  43:"Toreros Muertos",
  46:"Ketama",
  47:"Los Ronaldos",
  51:None, # Personal/custom Christmas arrangement: do not select a namesake by title.
  54:"Tequila",
  55:"Radio Futura",
  58:"Extremoduro",
  62:"Depedro",
  67:"Kiko Veneno",
  69:"Toreros Muertos",
  73:"Radio Futura",
  80:"Loquillo",
  81:"Radio Futura",
  82:"Los Ronaldos",
}

def norm(value):
  return align.normalize_label(value)

def artist_match(source,expected):
  if not expected or not source:return False
  aa=norm(source)
  bb=norm(expected)
  return aa==bb or (aa in bb and len(aa)>=7) or (bb in aa and len(bb)>=7)

def candidate_chords(model,text):
  matches=align.source_line_matches(model,align.segment_candidates(text))
  top=[x for x in matches if x["score"]>=0.985]
  possibilities=collections.defaultdict(set)
  for row in top:
    for li,wi,ch in row["placements"]:
      if a.is_chord(ch):
        possibilities[f"{li}:{wi}"].add(ch)
  unique={k:next(iter(v)) for k,v in possibilities.items() if len(v)==1}
  conflicted={k:v for k,v in possibilities.items() if len(v)>1}
  return unique,conflicted,len(top)

def harmony_match(old,new):
  checked=[]
  for k,ch in new.items():
    cur=str(old["words"].get(k) or "").strip()
    if not cur:continue
    root1=a.chord_root(cur);root2=a.chord_root(ch)
    if root1 in a.CHROMATIC and root2 in a.CHROMATIC:checked.append((root1,root2))
  counts=[]
  for shift in range(12):
    agreement=sum(a.CHROMATIC[(a.CHROMATIC.index(source)+shift)%12]==dest for dest,source in checked)
    counts.append((agreement,shift))
  counts.sort(key=lambda x:(-x[0],x[1]))
  best,shift=counts[0]
  second=counts[1][0]
  return {"overlaps":len(checked),"bestShift":shift,
    "agreementPct":round(100*best/max(1,len(checked)),1),
    "marginPct":round(100*(best-second)/max(1,len(checked)),1)}

def verify_tab(sid,song,expected,tab):
  a.limiter.wait()
  tid=int(tab["id"])
  data=a.ug_run(["-mode","fetch","-id",str(tid)])
  if not artist_match(str(data.get("artist_name") or tab.get("artist_name") or ""),expected):
    raise ValueError("Artist mismatch in fetched source")
  if norm(str(data.get("song_name") or tab.get("song_name") or ""))!=norm(song["titulo"]):
    raise ValueError("Title mismatch in fetched source")
  raw=str(data.get("content") or "")
  if len(raw)<30:raise ValueError("Source empty or too small")
  model=a.ug_to_model(raw)
  unique,ambiguous,match_count=candidate_chords(model,song["texto"])
  old=a.normalize_chord_data(song["letraConAcordes"])
  harmony=harmony_match(old,unique)
  chorded=set()
  for section in ("words","lines"):
    for key,ch in old[section].items():
      if str(ch).strip() and str(key).split(":")[0].isdigit():
        chorded.add(int(str(key).split(":")[0]))
  blank={int(k.split(":")[0]) for k in unique if int(k.split(":")[0]) not in chorded and k not in old["words"]}
  new={k:v for k,v in unique.items() if int(k.split(":")[0]) in blank}
  current_sim=a.similarity(song["texto"],model["lyrics"])
  # Incomplete source versions may match individual lines exactly, but never
  # enter a live write without whole-lyrics/harmonic cross-validation.
  safe=(current_sim>=0.85 and len(unique)>=15 and len(ambiguous)==0
        and harmony["overlaps"]>=5 and harmony["agreementPct"]>=90
        and harmony["marginPct"]>=20 and len(new)>=5)
  return {
    "tabId":tid,
    "artist":expected,
    "title":song["titulo"],
    "sourceURL":data.get("urlWeb") or f"https://tabs.ultimate-guitar.com/tab/{tid}",
    "sha256":hashlib.sha256(raw.encode()).hexdigest(),
    "wholeLyricsSimilarityPct":round(100*current_sim,1),
    "matchedSourceFragments":match_count,
    "uniqueChordAnchors":len(unique),
    "ambiguousAnchors":len(ambiguous),
    "newWordAnchorsOnBlankLines":len(new),
    "newlyCoveredLines":len({int(k.split(":")[0]) for k in new}),
    **harmony,
    "reviewTier":"STRONG_CANDIDATE" if safe else "REVIEW_MANUALLY"
  }

def main():
  state,meta=a.load_remote_storage()
  songs=a.build_songbook(state)
  if not 80<=len(songs)<=110:raise RuntimeError("Unexpected live songbook length")
  passes=cov.parse(state.get("quintoElemento.passes.v1","[]"),[])
  pasma=[p for p in passes if cov.norm(p.get("name"))==cov.norm("LA PASMA (NUEVA)")]
  if len(pasma)!=1 or len(pasma[0].get("songs",[]))!=23:
    raise RuntimeError("LA PASMA passed integrity check failed")
  weak=[]
  for s in songs:
    c=cov.counts(s)
    if c["estimatedMusicalCoveragePct"]<70:
      weak.append((int(s["id"]),s,c))
  counts={"inventory":len(songs),"weakCount":len(weak),"queries":0,
     "tabsInspected":0,"strongCandidates":0,"sourceErrors":0,"skippedUnknownArtists":0}
  results=[]
  max_tab=int(os.getenv("MAX_FETCHES_PER_SONG","3"))
  for sid,song,stats in weak:
    title=song["titulo"]
    artist=ARTISTS.get(sid)
    result={"id":sid,"title":title,"coveragePct":stats["estimatedMusicalCoveragePct"],
      "currentChords":stats["chordsTotal"],
      "expectedArtist":artist,"sources":[],"errors":[]}
    if not artist:
      result["status"]="ARTIST_OR_ORIGINAL_NOT_CONFIRMED"
      counts["skippedUnknownArtists"]+=1
      results.append(result)
      print("UG_WEAK="+json.dumps({k:v for k,v in result.items() if k!="sources"},ensure_ascii=False),flush=True)
      continue
    try:
      a.limiter.wait()
      search=a.ug_run(["-mode","search","-query",title])
      counts["queries"]+=1
      found=search.get("tabs") or []
      candidates=[v for v in found if v.get("id") and artist_match(v.get("artist_name"),artist)
        and norm(v.get("song_name"))==norm(title)]
      # Dedup alternate versions and favor community chord arrangements.
      def rank(row):
        try:return (float(row.get("rating") or 0),int(row.get("votes") or 0))
        except:return (0,0)
      candidates.sort(key=rank,reverse=True)
      for tab in candidates[:max_tab]:
        try:
          item=verify_tab(sid,song,artist,tab)
          counts["tabsInspected"]+=1
          result["sources"].append(item)
          if item["reviewTier"]=="STRONG_CANDIDATE":counts["strongCandidates"]+=1
        except Exception as e:
          counts["sourceErrors"]+=1
          result["errors"].append("tab "+str(tab.get("id"))+": "+str(e)[:150])
    except Exception as e:
      counts["sourceErrors"]+=1
      result["errors"].append("search: "+str(e)[:180])
    result["sources"].sort(key=lambda x:(x["reviewTier"]=="STRONG_CANDIDATE",
      x["newlyCoveredLines"],x["wholeLyricsSimilarityPct"]),reverse=True)
    result["status"]="STRONG_CANDIDATES_REQUIRE_VALIDATION" if any(x["reviewTier"]=="STRONG_CANDIDATE" for x in result["sources"]) else "REVIEW_MANUALLY"
    results.append(result)
    print("UG_WEAK="+json.dumps({
      "id":sid,"title":title,"artist":artist,"status":result["status"],
      "tabsInspected":len(result["sources"]),
      "best":result["sources"][0] if result["sources"] else None,
      "errors":result["errors"][:2]
    },ensure_ascii=False),flush=True)

  report={"readOnly":True,"source":"Pilfer/ultimate-guitar-scraper",
    "liveUpdatedAt":meta.get("payload",{}).get("updatedAt"),
    "totals":counts,"songs":results}
  (OUT/"ALL_WEAK_SONG_SOURCES.json").write_text(
    json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
  print("UG_WEAK_FINAL="+json.dumps(counts,ensure_ascii=False),flush=True)

if __name__=="__main__":
  main()
