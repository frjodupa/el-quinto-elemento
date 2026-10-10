#!/usr/bin/env python3
"""Find and rank alternate UG chord tabs for the songbook entries currently missing chords.
Only source metadata and similarity scores are exported. Never writes to Cloudflare.
"""
import difflib
import hashlib
import json
import re
import time
from pathlib import Path
import audit_songbook as a

OUT=Path("missing_chords_search_output")
OUT.mkdir(parents=True,exist_ok=True)
TARGETS={
 "76":{"title":"SABOR DE AMOR","artist":"Danza Invisible","queries":["Sabor de Amor","Danza Invisible Sabor de Amor"]},
 "79":{"title":"EL RITMO DEL GARAJE","artist":"Loquillo","queries":["Ritmo de Garaje","El Ritmo del Garage","Loquillo Ritmo"]},
 "80":{"title":"ENAMORADO DE LA MODA JUVENIL","artist":"Radio Futura","queries":["Enamorado de la Moda Juvenil","Radio Futura Enamorado"]},
}
def normalize(line):
 return a.normalized_lyrics(line).replace("\n"," ").strip()
def line_match_stats(model,text):
 src=[normalize(x) for x in model.get("lines") or []]
 tgt=[normalize(x) for x in text.splitlines()]
 src=[x for x in src if x]; tgt=[x for x in tgt if x]
 # Match partial arrangements: count each TARGET lyric line if any source line
 # corresponds exactly or very closely; repetitions are preserved and counted.
 scores=[]
 for t in tgt:
  best=max((difflib.SequenceMatcher(None,t,s).ratio() for s in src),default=0)
  scores.append(best)
 return {"sourceLines":len(src),"targetLines":len(tgt),
         "targetExactMatched":sum(s>=0.98 for s in scores),
         "targetStrongMatched":sum(s>=0.86 for s in scores),
         "targetStrongPct":round(100*sum(s>=0.86 for s in scores)/max(1,len(tgt)),1)}
def artist_ok(actual,expected):
 x=a.deaccent(actual.lower());y=a.deaccent(expected.lower())
 return bool(x and y and (x in y or y in x or ("loquillo" in x and "loquillo" in y)))
def title_ok(actual,expected):
 x=a.deaccent(actual.lower());y=a.deaccent(expected.lower())
 sx=re.sub(r"[^a-z]+","",x).replace("garage","garaje")
 sy=re.sub(r"[^a-z]+","",y).replace("garage","garaje")
 return sx==sy or (sx and sy and difflib.SequenceMatcher(None,sx,sy).ratio()>=0.83)
def main():
 storage,info=a.load_remote_storage()
 songs={x["id"]:x for x in a.build_songbook(storage)}
 results={}
 for sid,spec in TARGETS.items():
  cur=songs[sid]
  opts={}
  errors=[]
  for q in spec["queries"]:
   try:
    a.limiter.wait()
    found=a.ug_run(["-mode","search","-query",q])
    for tab in (found.get("tabs") or [])[:30]:
     id=int(tab.get("id") or 0)
     if not id:continue
     if not artist_ok(str(tab.get("artist_name") or ""),spec["artist"]):continue
     if not title_ok(str(tab.get("song_name") or ""),spec["title"]):continue
     opts[id]=tab
   except Exception as e:errors.append(f"search {q}: {str(e)[:200]}")
  candidates=[]
  for tabid,tab in list(opts.items())[:12]:
   try:
    a.limiter.wait()
    full=a.ug_run(["-mode","fetch","-id",str(tabid)])
    content=str(full.get("content") or "")
    if not content:continue
    model=a.ug_to_model(content)
    stats=line_match_stats(model,cur["texto"])
    sim=a.similarity(cur["texto"],model["lyrics"])
    mapped,coverage=a.map_placements(model,cur["texto"])
    candidates.append({"id":tabid,"title":full.get("song_name") or tab.get("song_name"),
      "artist":full.get("artist_name") or tab.get("artist_name"),
      "url":full.get("urlWeb") or f"https://tabs.ultimate-guitar.com/tab/{tabid}",
      "sourceHash":hashlib.sha256(content.encode()).hexdigest(),
      "wholeLyricsSimilarityPct":round(100*sim,1),"mappedPct":round(100*coverage,1),
      "sourceChordAnchors":len(model.get("placements") or []),
      "mappedAnchors":len(mapped),"rating":tab.get("rating"),
      **stats})
   except Exception as e:errors.append(f"fetch {tabid}: {str(e)[:200]}")
  candidates.sort(key=lambda t:(t["wholeLyricsSimilarityPct"],t["targetStrongPct"],t["mappedAnchors"]),reverse=True)
  results[sid]={"title":cur["titulo"],"expectedArtist":spec["artist"],
     "currentChords":a.count_chords(cur["letraConAcordes"]),"candidates":candidates,"errors":errors}
  print(json.dumps({"id":sid,"count":len(candidates),"top":candidates[:5],"errors":errors},ensure_ascii=False),flush=True)
 Path(OUT/"RANKED_SOURCE_CANDIDATES.json").write_text(json.dumps(results,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
 print("COMPLETED_NOT_APPLIED",flush=True)
if __name__=="__main__":main()
