#!/usr/bin/env python3
"""READ ONLY: 88-song chord completeness and exact-phrase donor inspection.

No POST/PUT, no complete lyrics, no third-party text exports, no overwrites.
Line suggestions are never considered approved just because words match.
"""
import collections
import json
import re
import unicodedata
from pathlib import Path

import audit_songbook as book
import audit_current_chord_coverage as coverage

OUT=Path("eqe-88-verification")
OUT.mkdir(parents=True,exist_ok=True)
PASS_KEY="quintoElemento.passes.v1"
CUSTOM_KEY="quintoElemento.customSongs.v1"

def norm_word(word):
    value=unicodedata.normalize("NFKD",str(word).casefold())
    value="".join(c for c in value if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+","",value)

def phrase_tokens(line):
    if not line.strip() or book.chord_line(line):return ()
    if re.match(r"^\s*(intro|instrumental|solo|coro|chorus|estrofa|verse|verso|puente|final|coda)\s*:?\s*$",line,re.I):return ()
    words=line.split()
    if len(words)<3:return ()
    normalized=tuple(norm_word(w) for w in words)
    if any(not w for w in normalized):return ()
    return normalized

def data_at(d,li):
    result={}
    for key,ch in d["words"].items():
        if not str(ch).strip():continue
        match=re.fullmatch(r"(\d+):(\d+)",str(key))
        if match and int(match.group(1))==li:
            result[int(match.group(2))]=str(ch)
    full=str(d["lines"].get(str(li),"") or "").strip()
    return {"words":result,"line":full}

def equivalent_chords(first,second):
    return json.dumps(first,sort_keys=True,ensure_ascii=False)==json.dumps(second,sort_keys=True,ensure_ascii=False)

def suggest_repeated(s):
    lines=s["texto"].splitlines()
    chords=book.normalize_chord_data(s["letraConAcordes"])
    groups=collections.defaultdict(list)
    for i,line in enumerate(lines):
        phrase=phrase_tokens(line)
        if phrase:groups[phrase].append(i)
    suggested=[]
    skips=collections.Counter()
    for phrase,indices in groups.items():
        if len(indices)<2:continue
        filled=[]
        empty=[]
        for i in indices:
            d=data_at(chords,i)
            if d["words"] or d["line"]:filled.append((i,d))
            else:empty.append(i)
        if not filled or not empty:continue
        first=filled[0][1]
        if not all(equivalent_chords(first,d) for _,d in filled[1:]):
            skips["conflicting_harmonies"]+=len(empty)
            continue
        if any(pos>=len(phrase) or pos<0 for pos in first["words"]):
            skips["bad_word_positions"]+=len(empty)
            continue
        if not all(book.is_chord(c) for c in first["words"].values()):
            skips["unknown_chord_symbols"]+=len(empty)
            continue
        if first["line"] and not book.split_chords(first["line"]):
            skips["unknown_line_chords"]+=len(empty)
            continue
        for to_line in empty:
            suggested.append({
                "line":to_line,
                "donorLines":[row[0] for row in filled],
                "chordSlots":len(first["words"])+bool(first["line"]),
                "allDonorsAgree":True
            })
    return suggested,dict(skips)

def main():
    storage,meta=book.load_remote_storage()
    songs=book.build_songbook(storage)
    custom=coverage.parse(storage.get(CUSTOM_KEY,"[]"),[])
    passes=coverage.parse(storage.get(PASS_KEY,"[]"),[])
    if len(songs)!=88 or len(custom)!=17:raise RuntimeError(f"Live inventory changed (songs {len(songs)}, custom {len(custom)}); no suggestions trusted")
    if len({book.deaccent(s["titulo"]).casefold().strip() for s in songs})!=88:raise RuntimeError("Duplicate song titles in live inventory")
    pasma=[p for p in passes if isinstance(p,dict) and p.get("name")=="LA PASMA (NUEVA)"]
    if len(pasma)!=1 or len(pasma[0].get("songs",[]))!=23:raise RuntimeError("La Pasma missing or not 23 songs")
    ids=pasma[0]["songs"]
    for p in passes:
        for idx in p.get("songs",[]):
            if isinstance(idx,bool) or not isinstance(idx,int) or idx<0 or idx>=88:
                raise RuntimeError("Invalid pass reference: "+str(idx))
    rows=[]
    safe_count=0
    total_slots=0
    weak=[]
    for song in songs:
        stats=coverage.counts(song)
        proposals,skips=suggest_repeated(song)
        sid=int(song["id"])
        safe_count+=len(proposals)
        total_slots+=sum(x["chordSlots"] for x in proposals)
        row={"id":sid,"title":song["titulo"],"chordCount":stats["chordsTotal"],
             "lineCount":stats["lyricLines"],"coveredLines":stats["lyricLinesWithChords"],
             "coveragePct":stats["estimatedMusicalCoveragePct"],
             "orphanChords":stats["orphanChordAnchors"],
             "inPasma":sid in ids,
             "exactRepeatProposals":proposals,"conflicts":skips}
        rows.append(row)
        if row["coveragePct"]<70:weak.append(row)
    result={
       "status":"READ_ONLY_COMPLETE",
       "totalSongs":len(songs),"uniqueTitles":88,"customSongs":len(custom),
       "zeroChords":sum(x["chordCount"]==0 for x in rows),
       "under25Pct":sum(x["coveragePct"]<25 for x in rows),
       "under70Pct":len(weak),"orphanChordCount":sum(x["orphanChords"] for x in rows),
       "passCount":len(passes),"pasmaLength":len(ids),
       "pasmaUnder70Pct":sum(x["coveragePct"]<70 and x["inPasma"] for x in rows),
       "safeExactRepeatSuggestions":safe_count,
       "potentialAdditionalChordAnchors":total_slots,
       "note":"Proposals identify exact matching repeated lyric lines with agreeing chords. NO automatic update; harmony can differ across sections.",
       "songs":rows
    }
    (OUT/"CURRENT_88_AUDIT.json").write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("CURRENT_88_AUDIT="+json.dumps({k:v for k,v in result.items() if k!="songs"},ensure_ascii=False),flush=True)
    for x in weak:
        print("WEAK_SONG="+json.dumps({k:v for k,v in x.items() if k not in ("exactRepeatProposals","conflicts")},ensure_ascii=False),flush=True)
    for x in rows:
        if x["exactRepeatProposals"]:
            print("CHORD_REPEAT_CANDIDATE="+json.dumps({"id":x["id"],"title":x["title"],"proposals":len(x["exactRepeatProposals"]),
                "chordAnchors":sum(y["chordSlots"] for y in x["exactRepeatProposals"])},ensure_ascii=False),flush=True)
if __name__=="__main__":
    main()
