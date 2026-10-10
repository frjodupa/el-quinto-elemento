#!/usr/bin/env python3
"""Safely enrich repeated lyric lines using chords already present in SAME song.

Strict: exact token sequence, unique same-position chord voicing across all
annotated repetitions. No external inference, no title/lyric changes, no changes
to existing chords. Dry-run by default. Live write requires explicit env opt-in,
a fresh Cloudflare backup, optimistic D1 timestamp, and post-write verification.
"""
import copy
import hashlib
import json
import os
import re
import unicodedata
from collections import defaultdict
from pathlib import Path
import requests
import audit_songbook as a

OUT=Path("eqe-repeat-chord-audit")
OUT.mkdir(exist_ok=True)
APPLY=os.environ.get("APPLY_SAFE_REPEATS","0")=="1"
PASS_KEY="quintoElemento.passes.v1"
CUSTOM_KEY="quintoElemento.customSongs.v1"
EXACT_INVENTORY=86
EXPECTED_CUSTOM=15
PASS_NAME="LA PASMA (NUEVA)"
EXPECTED_PASS_SIZE=23
NOTE="Copies only uniquely agreed chord placements from exactly matching repeated lyrics within the same song."
HEADERS={**a.HEADERS,"Content-Type":"application/json"}

def digest(obj):
    return hashlib.sha256(json.dumps(obj,sort_keys=True,ensure_ascii=False,separators=(",",":")).encode()).hexdigest()

def parse(value, default):
    if isinstance(value,type(default)):return copy.deepcopy(value)
    try:
        o=json.loads(value) if isinstance(value,str) else value
        return o if isinstance(o,type(default)) else copy.deepcopy(default)
    except (ValueError,TypeError):
        return copy.deepcopy(default)

def tokens(line):
    if not line or not line.strip():return ()
    if a.chord_line(line) or re.match(r"^\s*(intro|instrumental|solo|coro|chorus|estrofa|verso|puente|final|coda)\s*:?(\s*[0-9]*)?$",line,re.I):return ()
    pieces=[]
    for raw in str(line).split():
        w=unicodedata.normalize("NFKD",raw.casefold())
        w="".join(x for x in w if not unicodedata.combining(x))
        w=re.sub(r"[^a-z0-9]+","",w)
        if not w:return ()
        pieces.append(w)
    return tuple(pieces) if len(pieces)>=3 else ()

def line_payload(data,li):
    words={}
    for k,v in data["words"].items():
        if not str(v).strip():continue
        m=re.fullmatch(r"(\d+):(\d+)",str(k))
        if m and int(m.group(1))==li:words[int(m.group(2))]=str(v)
    value=data["lines"].get(str(li),"")
    return {"words":words,"line":str(value or "").strip()}

def chord_positions(payload):
    return len(payload["words"])+int(bool(payload["line"]))

def make_candidates(song):
    raw_lines=song["texto"].splitlines()
    old=song["letraConAcordes"]
    groups=defaultdict(list)
    for li,line in enumerate(raw_lines):
        tok=tokens(line)
        if tok:groups[tok].append(li)
    result=copy.deepcopy(old)
    edits=[]
    skipped=defaultdict(int)
    for normalized,lines in groups.items():
        if len(lines)<2:continue
        chorded={}
        blank=[]
        for li in lines:
            data=line_payload(old,li)
            if chord_positions(data):chorded[li]=data
            else:blank.append(li)
        if not chorded or not blank:continue
        signatures={json.dumps(v,sort_keys=True,ensure_ascii=False) for v in chorded.values()}
        if len(signatures)!=1:
            skipped["repeated_line_harmonic_conflicts"]+=len(blank)
            continue
        donor=next(iter(chorded.values()))
        if not donor["words"] and not donor["line"]:
            continue
        if any(wi<0 or wi>=len(normalized) for wi in donor["words"]):
            skipped["invalid_word_positions"]+=len(blank)
            continue
        if any(not a.is_chord(v) for v in donor["words"].values()):
            skipped["unrecognized_chord_symbols"]+=len(blank)
            continue
        if donor["line"] and not a.split_chords(donor["line"]):
            skipped["unrecognized_line_chords"]+=len(blank)
            continue
        # The underlying original text is exact token-for-token, including punctuation-stripped words.
        for target in blank:
            if tokens(raw_lines[target]) != normalized:
                raise RuntimeError("Repeated lyric token mismatch")
            if line_payload(result,target)["words"] or line_payload(result,target)["line"]:
                raise RuntimeError("Refusing to overwrite chords on target")
            for wi,val in donor["words"].items():
                result["words"][f"{target}:{wi}"]=val
            if donor["line"]:
                result["lines"][str(target)]=donor["line"]
            edits.append({
                "toLine":target,"copiedWordAnchors":len(donor["words"]),
                "copiedLineChord":bool(donor["line"]), "donorCandidates":len(chorded),
                "exactRepeatCount":len(lines)
            })
    if result["intro"]!=old["intro"] or result["instrumentals"]!=old["instrumentals"] or result["introText"]!=old["introText"] or result["instrumentalsText"]!=old["instrumentalsText"] or result["references"]!=old["references"]:
        raise RuntimeError("Protected structures changed")
    for section in ("words","lines"):
        for k,v in old[section].items():
            if result[section].get(k)!=v:raise RuntimeError("Existing chord overwritten")
    return result,edits,dict(skipped)

def validate_state(storage):
    custom=parse(storage.get(CUSTOM_KEY,"[]"),[])
    songs=a.build_songbook(storage)
    passes=parse(storage.get(PASS_KEY,"[]"),[])
    if len(songs)!=EXACT_INVENTORY or len(custom)!=EXPECTED_CUSTOM:
        raise RuntimeError(f"Unexpected songbook census: songs={len(songs)} custom={len(custom)}")
    seen=set()
    for s in songs:
        title=a.deaccent(s["titulo"]).casefold().strip()
        if not title or title in seen:raise RuntimeError("Duplicate or blank titles; do not apply")
        seen.add(title)
    found=[p for p in passes if isinstance(p,dict) and p.get("name")==PASS_NAME]
    if len(found)!=1 or len(found[0].get("songs",[]))!=EXPECTED_PASS_SIZE:
        raise RuntimeError("LA PASMA pass is missing or wrong size")
    for p in passes:
        if not isinstance(p,dict) or not isinstance(p.get("songs"),list):
            raise RuntimeError("Invalid pass structure")
        for i in p["songs"]:
            if isinstance(i,bool) or not isinstance(i,int) or not 0<=i<len(songs):
                raise RuntimeError("Broken pass reference")
    return songs

def load_state():
    state,meta=a.load_remote_storage()
    updated=meta.get("payload",{}).get("updatedAt")
    if not isinstance(updated,int):
        raise RuntimeError("Cloudflare timestamp missing; safe D1 compare-and-swap is impossible")
    return state,updated

def patch_plan(state):
    songs=validate_state(state)
    next_state=copy.deepcopy(state)
    affected=[]
    skipped=defaultdict(int)
    for song in songs:
        new_data,edits,ignored=make_candidates(song)
        for k,v in ignored.items():skipped[k]+=v
        if not edits:continue
        sid=song["id"]
        key=f"quintoElemento.chords.v2.{sid}"
        original=parse(state.get(key,"{}"),{})
        # Never discard custom or unknown stored chord fields.
        if not isinstance(original.get("words"),dict) or not isinstance(original.get("lines"),dict):
            raise RuntimeError("Stored chord structure unrecognized for ID "+sid)
        stored=copy.deepcopy(original)
        for section in ("words","lines"):
            for k,v in new_data[section].items():
                if not str(v).strip():continue
                if k not in stored[section]:
                    stored[section][k]=v
                elif stored[section][k]!=v:
                    raise RuntimeError(f"Chord conflict in stored record {sid}, {section}, {k}")
        for section in original:
            if section not in ("words","lines") and stored[section]!=original[section]:
                raise RuntimeError("Unexpected protected field modification")
        next_state[key]=json.dumps(stored,ensure_ascii=False,separators=(",",":"))
        after=a.normalize_chord_data(stored)
        if a.count_chords(after)<=a.count_chords(song["letraConAcordes"]):
            raise RuntimeError("Non-increasing chord count for "+sid)
        affected.append({"id":int(sid),"title":song["titulo"],
            "beforeChords":a.count_chords(song["letraConAcordes"]),
            "afterChords":a.count_chords(after),
            "addedChords":a.count_chords(after)-a.count_chords(song["letraConAcordes"]),
            "completedExactRepeatedLines":len(edits),
            "details":edits})
    changes={k for k in next_state if next_state[k]!=state.get(k)}
    expected={f"quintoElemento.chords.v2.{s['id']}" for s in affected}
    if changes != expected:
        raise RuntimeError("Unexpected changes outside chord maps")
    return next_state,affected,dict(skipped)

def save(name,obj):
    (OUT/name).write_text(json.dumps(obj,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")

def main():
    state,stamp=load_state()
    result,affected,ignored=patch_plan(state)
    report={"mode":"apply" if APPLY else "read-only", "inventoryCount":EXACT_INVENTORY,
        "source":"repeated identical lines from same song",
        "policy":NOTE,"cloudTimestamp":stamp,
        "snapshotSha256":digest(state),"affectedSongs":len(affected),
        "totalAddedChords":sum(s["addedChords"] for s in affected),
        "totalCompletedLines":sum(s["completedExactRepeatedLines"] for s in affected),
        "protectedLyricsAndExistingChords":True,
        "passReferencesPreserved":True,"skipped":ignored,"songs":affected}
    save("REPEAT_CHORD_PREFLIGHT.json",report)
    print("SAFE_REPETITIONS_REPORT="+json.dumps({k:v for k,v in report.items() if k!="songs"},ensure_ascii=False),flush=True)
    for entry in affected:
        print("REPEAT_SONG="+json.dumps({k:v for k,v in entry.items() if k!="details"},ensure_ascii=False),flush=True)
    if not APPLY:return
    if not affected:
        print("NO_SAFE_CHANGES_TO_APPLY=YES",flush=True)
        return
    fresh,updated=load_state()
    if updated!=stamp or digest(fresh)!=digest(state):
        raise RuntimeError("D1 changed since validation: abort")
    r=requests.post(a.LIVE_BASE+"/api/backups",headers=HEADERS,json={"action":"create"},timeout=45)
    r.raise_for_status()
    backup=r.json()
    if backup.get("ok") is not True or not backup.get("id"):
        raise RuntimeError("Backup not confirmed; abort")
    verify,updated=load_state()
    if updated!=stamp or digest(verify)!=digest(state):
        raise RuntimeError("D1 changed during backup; abort; backup "+str(backup["id"]))
    r=requests.put(a.LIVE_BASE+"/api/sync",headers=HEADERS,
        json={"data":result,"expectedUpdatedAt":stamp},timeout=80)
    if r.status_code==409:
        raise RuntimeError("Concurrent Cloudflare edit prevented; backup "+str(backup["id"]))
    r.raise_for_status()
    if r.json().get("ok") is not True:
        raise RuntimeError("D1 write not confirmed; backup "+str(backup["id"]))
    actual,_=load_state()
    if digest(actual)!=digest(result):
        raise RuntimeError("Post-sync mismatch; use backup "+str(backup["id"]))
    validate_state(actual)
    report["backupId"]=backup["id"]
    report["status"]="APPLIED_AND_VERIFIED"
    save("REPEAT_CHORD_APPLIED.json",report)
    print("REPEAT_CHORD_APPLIED="+json.dumps({k:v for k,v in report.items() if k!="songs"},ensure_ascii=False),flush=True)

if __name__=="__main__":
    main()
