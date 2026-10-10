#!/usr/bin/env python3
"""Read-only: discover artist-verified UG sources for critically incomplete EQE songs.

Run against current Cloudflare state, preserve user's stored lyrics/chords, and
report ONLY source IDs, similarity, confident chord anchors, conflict counters.
Never writes or publishes third-party lyrics.
"""
import difflib
import hashlib
import json
import os
import re
from pathlib import Path

import audit_songbook as a
import strict_line_chords_86 as align

OUT=Path("eqe-low-coverage-source-review")
OUT.mkdir(exist_ok=True)
TARGETS={
 5:("AQUÍ NO HAY PLAYA","Los Refrescos",["aqui no hay playa","refrescos aqui no hay playa"]),
 26:("ESPALDAS MOJADAS","Tam Tam Go",["espaldas mojadas","tam tam go espaldas mojadas"]),
 43:("MI AGÜITA AMARILLA","Toreros Muertos",["mi aguita amarilla","toreros muertos mi aguita amarilla"]),
 54:("SALTA","Tequila",["salta tequila","salta"]),
 62:("TE SIGO SOÑANDO","Depedro",["te sigo soñando","depedro te sigo sonando"]),
 70:("YO SOY QUIEN ESPIA LOS JUEGOS DE LOS NIÑOS","Ilegales",["yo soy quien espia los juegos de los ninos","ilegales yo soy quien espia"]),
 73:("ESCUELA DE CALOR","Radio Futura",["escuela de calor","radio futura escuela de calor"]),
}
MAX_FETCH=6
MIN_LINE_CONF=0.985

def norm(text):
    t=a.deaccent(str(text or "")).lower()
    return re.sub("[^a-z0-9]+"," ",t).strip()
def norm_simple(text):
    return re.sub("[^a-z0-9]","",norm(text))
def same_artist(expected,actual):
    exp,act=norm(expected),norm(actual)
    if not exp or not act:return False
    exp=exp.replace("los ","").replace("the ","").replace("el ","")
    act=act.replace("los ","").replace("the ","").replace("el ","")
    exp=exp.replace("tam tam go","tamtamgo")
    act=act.replace("tam tam go","tamtamgo")
    return exp in act or act in exp or (exp=="tamtamgo" and act=="tamtamgo")
def same_song(expected,actual):
    exp,act=norm_simple(expected),norm_simple(actual)
    if exp==act:return True
    return difflib.SequenceMatcher(None,exp,act).ratio()>=0.90
def aligned_chords(model,target):
    matches=align.source_line_matches(model,align.segment_candidates(target))
    proposed={}
    candidates={}
    for m in matches:
        if m["score"]<MIN_LINE_CONF:continue
        for line,word,chord in m["placements"]:
            key=f"{line}:{word}"
            candidates.setdefault(key,set()).add(chord)
    safe={k:next(iter(v)) for k,v in candidates.items() if len(v)==1}
    ambiguous={k:v for k,v in candidates.items() if len(v)>1}
    return safe,ambiguous,len(matches)
def score_baseline(song,safe):
    existing=song["letraConAcordes"].get("words",{})
    pairs=[]
    for key,chord in safe.items():
        old=existing.get(key)
        if old:
            current=a.chord_root(old)
            source=a.chord_root(chord)
            if current and source:
                pairs.append((current,source))
    ratio=sum(x==y for x,y in pairs)/max(1,len(pairs))
    conflicts=sum(x!=y for x,y in pairs)
    new={k:v for k,v in safe.items() if not existing.get(k)}
    return {"comparableExistingAnchors":len(pairs),"sameRootPct":round(100*ratio,1),
            "conflictingExistingAnchors":conflicts,"candidateNewAnchors":len(new),
            "candidateLinesWithNewAnchors":len({k.split(":")[0] for k in new})}
def main():
    storage,meta=a.load_remote_storage()
    songs=a.build_songbook(storage)
    if len(songs)!=86:raise RuntimeError(f"Expected 86 live songs but found {len(songs)}")
    result=[]
    for sid,(expected,artist,queries) in TARGETS.items():
        song=songs[sid]
        if norm_simple(song["titulo"])!=norm_simple(expected):
            raise RuntimeError("Song index/title mismatch: "+str(sid))
        hits={}
        errors=[]
        for query in queries:
            try:
                a.limiter.wait()
                data=a.ug_run(["-mode","search","-query",query])
                for tab in data.get("tabs",[]):
                    try:id=int(tab.get("id"))
                    except Exception:continue
                    title=tab.get("song_name") or ""
                    performer=tab.get("artist_name") or ""
                    if id and same_song(expected,title) and same_artist(artist,performer):
                        hits[id]=tab
            except Exception as exc:errors.append("search: "+str(exc)[:150])
        inspected=[]
        # Prefer higher user-rated tabs but include alternatives.
        ranked=sorted(hits.values(),key=lambda x:(float(x.get("rating") or 0),float(x.get("votes") or 0)),reverse=True)[:MAX_FETCH]
        for meta_tab in ranked:
            uid=int(meta_tab["id"])
            try:
                a.limiter.wait()
                tab=a.ug_run(["-mode","fetch","-id",str(uid)])
                content=str(tab.get("content") or "")
                if not content:continue
                if not same_artist(artist,tab.get("artist_name")) or not same_song(expected,tab.get("song_name")):
                    continue
                model=a.ug_to_model(content)
                sim=a.similarity(song["texto"],model["lyrics"])
                safe,ambiguous,matches=aligned_chords(model,song["texto"])
                baseline=score_baseline(song,safe)
                inspected.append({"tabId":uid,
                    "artist":tab.get("artist_name"),"title":tab.get("song_name"),
                    "url":tab.get("urlWeb") or f"https://tabs.ultimate-guitar.com/tab/{uid}",
                    "sha256":hashlib.sha256(content.encode()).hexdigest(),
                    "rating":meta_tab.get("rating"),"votes":meta_tab.get("votes"),
                    "wholeLyricSimilarityPct":round(100*sim,1),
                    "sourceChordAnchors":len(model["placements"]),
                    "sourceLineMatches":matches,"safeSourcePositions":len(safe),
                    "ambiguousSourcePositions":len(ambiguous),**baseline})
            except Exception as exc:errors.append(f"tab {uid}: "+str(exc)[:150])
        inspected.sort(key=lambda x:(x["wholeLyricSimilarityPct"],x["candidateNewAnchors"],x["sameRootPct"]),reverse=True)
        result.append({"id":sid,"title":song["titulo"],"expectedArtist":artist,
                       "currentChords":a.count_chords(song["letraConAcordes"]),
                       "sourcesFound":len(inspected),"candidates":inspected,"errors":errors})
        print("LOW_COVERAGE_SOURCES="+json.dumps({k:v for k,v in result[-1].items() if k!="candidates"},ensure_ascii=False),flush=True)
        if inspected:
            print("BEST_SOURCE="+json.dumps({"id":sid,**inspected[0]},ensure_ascii=False),flush=True)
    (OUT/"SOURCE_REVIEW.json").write_text(json.dumps({"readOnly":True,"songCount":86,"results":result},ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("ALL_TARGETS_REVIEWED=YES",flush=True)
if __name__=="__main__":main()
