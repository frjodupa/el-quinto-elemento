#!/usr/bin/env python3
"""Independent exact-lyric / same-key chord audit of six 86-song candidate sources.

No D1 writes. Re-use project-vetted source fetcher, enforce fixed tab IDs
and SHA256s from previous full audit, and report only unambiguous chord anchors
on previously chord-empty original lyric lines. Never copies external lyrics.
"""
import collections
import hashlib
import json
import unicodedata
from pathlib import Path

import audit_songbook as a
import strict_line_chords_86 as align
from audit_repeated_chords_86 import validate_state,load_state

OUT=Path("eqe-six-source-independent")
OUT.mkdir(exist_ok=True)
SOURCES={
 6:("AUNQUE TU NO LO SEPAS","Quique González",2089921,"3384e6abc7e778c4b9b6900e4db279414117b90eb0ab0c6d1602dd0d2b57e30e"),
 11:("CARBÓN Y RAMAS SECAS","Manolo García",1560705,"b4a0ca3aa2139cf196f64dd6de794ec3167d01575e06e9d97ed31321c3d36920"),
 44:("MI GRAN NOCHE","Raphael",1619536,"ae08fdaa7ef01bd1e5951d25e546c53ee570538e93850f23773e033950473e7d"),
 48:("PÁJAROS DE BARRO","Manolo García",1560733,"ef1cc349889437f09a91a4bfc76af37c2fb1d6b077bbe2c92fa6acbba3a4f499"),
 56:("SI ME DAS A ELEGIR","Manu Chao",1561091,"4a641902c8e9bf11ea5d9ef9475d02546d181dec82be4a5d8b2b3da3963c6c2e"), # placeholder overridden below
 74:("HACE CALOR","Andrés Calamaro",2565078,"a470b580cd47e62fcf78b2664ab37fb5600effb118eb7ec23fe26571a973c1c3"),
}
SOURCES[56]=("SI ME DAS A ELEGIR","Manu Chao",1561091,"4a641902c8e9bf11ea5d9ef9475d02546d181dec82be4a5d8b2b3da3963c6c2e")
# Last hash copied independently from the full report before running the workflow.
SOURCES[56]=("SI ME DAS A ELEGIR","Manu Chao",1561091,"4a641902c8e9bf11ea5d9ef9475d02546d181dec82be4a5d8b2b3da3963c6c2e")  # see hash check below

def canonical(s):
    return align.normalize_label(str(s or ""))

def source_model(sid,pin):
    title,artist,tabid,expected_hash=pin
    a.limiter.wait()
    tab=a.ug_run(["-mode","fetch","-id",str(tabid)])
    content=str(tab.get("content") or "")
    actual_hash=hashlib.sha256(content.encode()).hexdigest()
    if expected_hash!=actual_hash:
        raise RuntimeError(f"Pinned original source mismatch for {sid}: {actual_hash}")
    if canonical(title)!=canonical(tab.get("song_name")):
        raise RuntimeError(f"Source title mismatch {sid}")
    actual_artist=canonical(tab.get("artist_name"))
    if canonical(artist) not in actual_artist and actual_artist not in canonical(artist):
        raise RuntimeError(f"Source artist mismatch {sid}: {actual_artist}")
    return a.ug_to_model(content),tab

def assess(song,model):
    existing=song["letraConAcordes"]
    src_matches=align.source_line_matches(model,align.segment_candidates(song["texto"]))
    best=[m for m in src_matches if m["score"]>=.985]
    anchors=collections.defaultdict(set)
    for row in best:
        for li,wi,ch in row["placements"]:
            if a.is_chord(ch):anchors[f"{li}:{wi}"].add(ch)
    unique={k:next(iter(v)) for k,v in anchors.items() if len(v)==1}
    conflicted={k:sorted(v) for k,v in anchors.items() if len(v)>1}
    overlap=[]
    lines=song["texto"].splitlines()
    for key,chord in unique.items():
        old=str(existing["words"].get(key) or "").strip()
        if old and a.chord_root(old) in a.CHROMATIC and a.chord_root(chord) in a.CHROMATIC:
            overlap.append((a.chord_root(old),a.chord_root(chord)))
    score=[]
    for shift in range(12):
        matching=sum(a.CHROMATIC[(a.CHROMATIC.index(src)+shift)%12]==prev for prev,src in overlap)
        score.append((matching,shift))
    score.sort(key=lambda pair:(pair[0],-pair[1]),reverse=True)
    matches,shift=score[0]
    margin=(matches-score[1][0])/max(1,len(overlap))
    harmony=matches/max(1,len(overlap))
    whole=a.similarity(song["texto"],model["lyrics"])
    existing_lines=set()
    for raw_key,value in existing["words"].items():
        if str(value).strip() and ":" in raw_key:
            existing_lines.add(int(raw_key.split(":")[0]))
    for raw_key,value in existing["lines"].items():
        if str(value).strip():
            existing_lines.add(int(raw_key))
    new={}
    for key,ch in unique.items():
        li,wi=(int(x) for x in key.split(":"))
        if li in existing_lines:continue
        if not (0<=li<len(lines) and 0<=wi<len(lines[li].split())):continue
        transformed=a.transpose_chord(ch,shift)
        if not a.is_chord(transformed):continue
        new[key]=transformed
    # Auto candidate only when source original version is almost identical,
    # strong overlap with existing harmony and no key ambiguity.
    approved=whole>=.98 and len(overlap)>=7 and harmony>=.9 and margin>=.15 and len(best)>=5 and len(new)>=2
    return {
        "fullLyricsSimilarity":round(100*whole,1),
        "sourceMatchedLyricSegments":len(best),
        "sourceUnambiguousChordPositions":len(unique),
        "sourceAmbiguousChordPositions":len(conflicted),
        "originalChords":a.count_chords(existing),
        "overlappingOriginalAnchors":len(overlap),"bestKeyShift":shift,
        "sameKeyRootAgreementPct":round(100*harmony,1),
        "bestVsSecondShiftMarginPct":round(100*margin,1),
        "newUniqueAnchorsOnBlankLines":len(new),
        "newlyCoveredPhysicalLines":len({k.split(":")[0] for k in new}),
        "approvedForIndependentChordOnlyFollowup":approved
    }

def main():
    storage,_=load_state()
    by_id={int(s["id"]):s for s in validate_state(storage)}
    results=[]
    for sid,pinned in SOURCES.items():
        if canonical(by_id[sid]["titulo"])!=canonical(pinned[0]):
            raise RuntimeError(f"Wrong title for {sid}")
        model,tab=source_model(sid,pinned)
        row={"id":sid,"song":pinned[0],"artist":pinned[1],
             "tabId":pinned[2],"tabURL":tab.get("urlWeb") or f"https://tabs.ultimate-guitar.com/tab/{pinned[2]}",
             **assess(by_id[sid],model)}
        results.append(row)
        print("INDEPENDENT_SOURCE="+json.dumps(row,ensure_ascii=False),flush=True)
    (OUT/"SIX_SOURCE_RECHECK.json").write_text(json.dumps({"readOnly":True,"results":results},ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
if __name__=="__main__":main()
