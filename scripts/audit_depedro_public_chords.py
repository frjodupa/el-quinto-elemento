#!/usr/bin/env python3
"""Read-only AcordesWeb chord markup probe for Depedro TE SIGO SOÑANDO.

Preserve <br> physical lines, represent chord anchors as [ch] tags, and map
high-confidence source lyric segments onto current song lyric word indices.
Outputs only chord metadata/metrics, never reproduces copyrighted lyrics.
"""
import copy
import hashlib
import json
from collections import defaultdict
from pathlib import Path

import requests
from bs4 import BeautifulSoup
import audit_songbook as a
import strict_line_chords_86 as align
from audit_repeated_chords_86 import load_state
import audit_current_chord_coverage as coverage

def validate_state(storage):
    songs=a.build_songbook(storage)
    if not 80<=len(songs)<=120:
        raise RuntimeError("Unexpected song count: "+str(len(songs)))
    titles=[coverage.norm(s["titulo"]) for s in songs]
    if not all(titles) or len(set(titles))!=len(titles):
        raise RuntimeError("Blank/duplicate titles; do not audit")
    passes=coverage.parse(storage.get("quintoElemento.passes.v1","[]"),[])
    pasma=[p for p in passes if coverage.norm(p.get("name"))==coverage.norm("LA PASMA (NUEVA)")]
    if len(pasma)!=1 or len(pasma[0].get("songs",[]))!=23:
        raise RuntimeError("Unexpected LA PASMA pass state")
    for p in passes:
        for idx in p.get("songs",[]):
            if isinstance(idx,bool) or not isinstance(idx,int) or not 0<=idx<len(songs):
                raise RuntimeError("Invalid pass reference")
    return songs

SONG_ID=62
URL="https://acordesweb.com/cancion/depedro/te-sigo-sonando"
OUT=Path("eqe-depedro-audit")
OUT.mkdir(exist_ok=True)

def source_model(html):
    soup=BeautifulSoup(html,"html.parser")
    pre=soup.select_one("pre#chordsPre")
    if pre is None:raise RuntimeError("AcordesWeb: no #chordsPre")
    # chord is an <a> inside <span>; no chord positions without this structure.
    anchored=0
    for anchor in list(pre.find_all("a")):
        chord=anchor.get_text(" ",strip=True)
        if not a.is_chord(chord):continue
        # The UG parser is already vetted by our other exact-source audits.
        anchor.replace_with(f" [ch]{chord}[/ch] ")
        anchored+=1
    for br in list(pre.find_all("br")):
        br.replace_with("\n")
    content=pre.get_text("",strip=False)
    # Eliminate section headings, do not emit copyrighted content.
    filtered=[]
    for line in content.splitlines():
        lower=a.deaccent(line.strip()).lower()
        if lower.startswith(("intro:","instrumental:","tonalidad:","afinacion:","capo:")):
            continue
        filtered.append(line)
    model=a.ug_to_model("\n".join(filtered))
    return model,anchored,hashlib.sha256(html.encode()).hexdigest(),len(filtered)

def main():
    storage,_=load_state()
    songs=validate_state(storage)
    song=songs[SONG_ID]
    if align.normalize_label(song["titulo"])!="te sigo sonando":
        # Compare canonical words rather than ASCII accent shape in source title.
        if align.normalize_label(song["titulo"])!=align.normalize_label("TE SIGO SOÑANDO"):
            raise RuntimeError("D1 song title ID62 differs")
    r=requests.get(URL,headers={"User-Agent":"EQE Sheet Inspector/1.0"},timeout=24)
    r.raise_for_status()
    model,anchors,html_hash,source_lines=source_model(r.text)
    match=align.source_line_matches(model,align.segment_candidates(song["texto"]))
    confident=[row for row in match if row["score"]>=.985]
    chords=defaultdict(set)
    for row in confident:
        for li,wi,ch in row["placements"]:
            if not a.is_chord(ch):continue
            chords[f"{li}:{wi}"].add(ch)
    consistent={k:next(iter(v)) for k,v in chords.items() if len(v)==1}
    ambiguous={k:v for k,v in chords.items() if len(v)>1}
    original=song["letraConAcordes"]
    old=original["words"]
    overlaps=[]
    for k,new in consistent.items():
        existing=str(old.get(k) or "")
        if existing:
            x,y=a.chord_root(existing),a.chord_root(new)
            if x and y:
                overlaps.append((x,y))
    shifts=[]
    for sh in range(12):
        agree=sum(a.transpose_chord(src,sh)==dest for dest,src in overlaps)
        shifts.append({"shift":sh,"agree":agree,"compared":len(overlaps)})
    shifts.sort(key=lambda d:d["agree"],reverse=True)
    additions={k:v for k,v in consistent.items() if not old.get(k)}
    metrics={
        "id":SONG_ID,"title":song["titulo"],"artist":"Depedro",
        "sourceURL":URL,"sourceHtmlSha256":html_hash,
        "downloadHttp":r.status_code,"sourceChordAnchorsInHtml":anchors,
        "sourceLineCount":source_lines,"parsedLyricLines":len(model["lines"]),
        "parsedChordPlacements":len(model["placements"]),
        "wholeTextSimilarityPct":round(100*a.similarity(song["texto"],model["lyrics"]),1),
        "matchingSourceSegments":len(match),"highConfidenceSegments":len(confident),
        "uniquePositions":len(consistent),"ambiguousPositions":len(ambiguous),
        "existingChords":a.count_chords(original),
        "existingOverlapChords":len(overlaps),"shiftRanking":shifts,
        "candidateNewPositions":len(additions),
        "newlyCoveredPhysicalLines":len({k.split(":")[0] for k in additions}),
        "autoApply":False,"reason":"Strict chord-only review. Source key must be independently confirmed before any write."}
    (OUT/"DE_PEDRO_AUDIT.json").write_text(json.dumps(metrics,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("DEPEDRO_SOURCE_METRICS="+json.dumps(metrics,ensure_ascii=False),flush=True)
if __name__=="__main__":main()
