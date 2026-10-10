#!/usr/bin/env python3
"""Strict external-source chord-only candidate validation for existing EQE lyrics.
Read-only by default. Source hash, singer, song title, source-word match and
existing key agreement are mandatory; never imports external lyrics.
"""
import collections
import copy
import hashlib
import json
import os
import re
from pathlib import Path
import requests
import audit_songbook as a
import strict_line_chords_86 as align
from audit_repeated_chords_86 import digest,validate_state,load_state

OUT=Path("eqe-original-song-strict")
OUT.mkdir(exist_ok=True)
APPLY=os.environ.get("APPLY_ORIGINAL_STRICT","0")=="1"
HEADERS={**a.HEADERS,"Content-Type":"application/json"}

SOURCES={
 26:{"title":"ESPALDAS MOJADAS","artist":"Tam Tam Go","tab":4347611,
     "hash":"52ded72abd2673503ce3fa81fe2ab329fa9611fc07145301562aebbe5a004b5c"},
 43:{"title":"MI AGÜITA AMARILLA","artist":"Toreros Muertos","tab":1583888,
     "hash":"746b1c2164dbbeba0459a7e181a02a0ef769489bdfa2dacde448c8f84c885aa9"},
 54:{"title":"SALTA","artist":"Tequila","tab":1581631,
     "hash":"28e96aa2fd7e87d7e04911356b51fb0e1c09ed17677204504289f70f1d0afdfb"},
 70:{"title":"YO SOY QUIEN ESPIA LOS JUEGOS DE LOS NIÑOS","artist":"Ilegales","tab":1605172,
     "hash":"032788e0edde9236da6ea0eb67d8a7676f90a8fd520acdbbe37599e7a71ca6e3"},
 73:{"title":"ESCUELA DE CALOR","artist":"Radio Futura","tab":383853,
     "hash":"745b461b282021c3696719e9800963e88628e0580dfb7c7fa4e1272cc0dffadc"},
}
SOURCE_THRESHOLD=0.985

def fetch_verified(sid,pin):
    a.limiter.wait()
    tab=a.ug_run(["-mode","fetch","-id",str(pin["tab"])])
    raw=str(tab.get("content") or "")
    if not raw or hashlib.sha256(raw.encode()).hexdigest()!=pin["hash"]:
        raise RuntimeError(f"External source changed for {sid}; abort")
    remote_title=align.normalize_label(tab.get("song_name"))
    expected_title=align.normalize_label(pin["title"])
    if expected_title!=remote_title:
        raise RuntimeError(f"Unexpected song title at {sid}: {remote_title}")
    performer=align.normalize_label(tab.get("artist_name"))
    artist=align.normalize_label(pin["artist"])
    if artist not in performer and performer not in artist:
        raise RuntimeError(f"Unexpected artist at {sid}: {performer}")
    model=a.ug_to_model(raw)
    return model,tab

def candidate_positions(model,txt):
    candidates=collections.defaultdict(set)
    src_matched=align.source_line_matches(model,align.segment_candidates(txt))
    usable=[row for row in src_matched if row["score"]>=SOURCE_THRESHOLD]
    for row in usable:
        for li,wi,ch in row["placements"]:
            candidates[f"{li}:{wi}"].add(ch)
    unique={k:next(iter(v)) for k,v in candidates.items() if len(v)==1}
    ambiguous={k:sorted(v) for k,v in candidates.items() if len(v)>1}
    return unique,ambiguous,len(usable)

def score_shifts(current,unique):
    anchors=[]
    for k,ch in unique.items():
        prev=str(current["words"].get(k) or "").strip()
        if not prev:continue
        original=a.chord_root(prev)
        source=a.chord_root(ch)
        if original and source and original in a.CHROMATIC and source in a.CHROMATIC:
            anchors.append((original,source))
    shifted=[]
    for shift in range(12):
        matches=sum(a.CHROMATIC[(a.CHROMATIC.index(src)+shift)%12]==prev for prev,src in anchors)
        shifted.append((matches,shift))
    shifted.sort(reverse=True)
    best_count,best_shift=shifted[0]
    second=shifted[1][0] if len(shifted)>1 else 0
    return {
        "existingCompared":len(anchors),
        "bestShift":best_shift,
        "bestAgreement":best_count/max(1,len(anchors)),
        "runnerUpAgreement":second/max(1,len(anchors)),
        "sourceConflictsAtSelectedShift":len(anchors)-best_count,
        "sameKeyPositions":best_count
    }

def assess_source(sid,pin,song):
    existing=copy.deepcopy(song["letraConAcordes"])
    model,tab=fetch_verified(sid,pin)
    safe,ambiguous,matches=candidate_positions(model,song["texto"])
    shift=score_shifts(existing,safe)
    lyrics=a.similarity(song["texto"],model["lyrics"])
    words=str(song["texto"]).splitlines()
    blank_lines=set()
    for li,ln in enumerate(words):
        if not ln.strip():continue
        has_word=any(str(k).startswith(str(li)+":") and str(v).strip() for k,v in existing["words"].items())
        has_line=bool(str(existing["lines"].get(str(li),"")).strip())
        if not has_word and not has_line:blank_lines.add(li)
    rejected_lines={int(k.split(":")[0]) for k in ambiguous}
    additions={}
    for k,ch in safe.items():
        li,wi=(int(x) for x in k.split(":"))
        if li not in blank_lines or li in rejected_lines:continue
        if not (0<=li<len(words) and 0<=wi<len(words[li].split())):continue
        if not a.is_chord(ch):continue
        v=a.transpose_chord(ch,shift["bestShift"])
        if not a.is_chord(v):continue
        if k in additions and additions[k]!=v:raise RuntimeError("Duplicate chord output")
        additions[k]=v
    complete_lines=len({int(k.split(":")[0]) for k in additions})
    baseline=shift["existingCompared"]
    agreement=shift["bestAgreement"]
    margin=agreement-shift["runnerUpAgreement"]
    permitted=False
    reason=""
    if sid in (43,70):
        permitted=baseline>=5 and agreement>=0.8 and margin>=0.2 and matches>=12 and len(additions)>=5
        reason="at least 5 existing anchors, >=80% same-key concordance, artist+exact lyric mapping"
    elif sid==54:
        permitted=baseline>=2 and agreement>=0.999 and margin>=0.3 and matches>=12 and len(additions)>=5
        reason="two existing anchors fully agree, >=12 exact line matches"
    elif sid==73:
        permitted=lyrics>=0.99 and baseline>=1 and agreement>=0.999 and matches>=4 and shift["bestShift"]==0 and len(additions)>=3
        reason="whole lyric match >=99%, artist exact and no transposition"
    elif sid==26:
        permitted=baseline>=10 and agreement>=0.90 and margin>=0.2 and matches>=20 and len(additions)>=12
        reason="requires >=10 chord checks and >=90% reliable key transposition"
    # Preserving all earlier chord symbols takes precedence over external source.
    report={"id":sid,"title":song["titulo"],"artist":pin["artist"],"sourceTab":pin["tab"],
        "sourceURL":tab.get("urlWeb") or f"https://tabs.ultimate-guitar.com/tab/{pin['tab']}",
        "sourceSha256":pin["hash"],"sourceWordMatchThresholdPct":SOURCE_THRESHOLD*100,
        "wholeLyricSimilarityPct":round(lyrics*100,1),"sourceMatchedLines":matches,
        "ambiguousAnchorsSkipped":len(ambiguous),"sourcePositions":len(safe),
        "originalChords":a.count_chords(existing),"eligibleNewChordAnchors":len(additions),
        "newlyCoveredLines":complete_lines,
        "proposedShift":shift["bestShift"],"baselineAnchorMatches":baseline,
        "baselineRootAgreementPct":round(agreement*100,1),"keyShiftMarginPct":round(margin*100,1),
        "existingConflictsPreserved":shift["sourceConflictsAtSelectedShift"],
        "mayAutoApply":bool(permitted),"policy":reason}
    return additions,report

def write(name,data):
    (OUT/name).write_text(json.dumps(data,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")

def main():
    state,stamp=load_state()
    songs=validate_state(state)
    by_id={int(s["id"]):s for s in songs}
    proposed=copy.deepcopy(state)
    rows=[]
    for sid,pin in SOURCES.items():
        s=by_id[sid]
        if align.normalize_label(s["titulo"])!=align.normalize_label(pin["title"]):
            raise RuntimeError("Current song/title mismatch at "+str(sid))
        additions,report=assess_source(sid,pin,s)
        if report["mayAutoApply"]:
            key=f"quintoElemento.chords.v2.{sid}"
            raw=a.safe_json(state.get(key,"{}"),{})
            if not isinstance(raw,dict) or not isinstance(raw.get("words"),dict):
                raise RuntimeError("Unexpected raw chord storage at "+str(sid))
            current=copy.deepcopy(raw)
            for word,ch in additions.items():
                if current["words"].get(word):
                    raise RuntimeError("Existing chord unexpectedly present: "+word)
                current["words"][word]=ch
            proposed[key]=json.dumps(current,ensure_ascii=False,separators=(",",":"))
        rows.append(report)
        print("SOURCE_CANDIDATE="+json.dumps(report,ensure_ascii=False),flush=True)
    new_count=sum(int(x["eligibleNewChordAnchors"]) for x in rows if x["mayAutoApply"])
    rep={"status":"PREFLIGHT","dryRun":not APPLY,"inventory":len(songs),
         "liveUpdatedAt":stamp,"snapshotSha256":digest(state),
         "sourcePinned":True,"sourceChangedLyrics":False,
         "protectedIntroInstrumentalReferences":True,
         "approvedSongCount":sum(bool(x["mayAutoApply"]) for x in rows),
         "approvedChordAnchors":new_count,"songs":rows}
    write("EXTERNAL_STRICT_PREFLIGHT.json",rep)
    if not APPLY:return
    if not new_count:
        print("NO_APPROVED_UPDATES",flush=True)
        return
    fresh,updated=load_state()
    if updated!=stamp or digest(fresh)!=digest(state):
        raise RuntimeError("Cloudflare data changed before backup; abort")
    backup=requests.post(a.LIVE_BASE+"/api/backups",headers=HEADERS,json={"action":"create"},timeout=45)
    backup.raise_for_status()
    bj=backup.json()
    if bj.get("ok") is not True or not bj.get("id"):raise RuntimeError("Backup not confirmed")
    final,updated=load_state()
    if updated!=stamp or digest(final)!=digest(state):raise RuntimeError("Cloudflare changed during backup; abort")
    upload=requests.put(a.LIVE_BASE+"/api/sync",headers=HEADERS,
        json={"data":proposed,"expectedUpdatedAt":stamp},timeout=80)
    if upload.status_code==409:raise RuntimeError("Concurrent update; backup "+str(bj["id"]))
    upload.raise_for_status()
    if upload.json().get("ok") is not True:raise RuntimeError("Sync not confirmed")
    actual,_=load_state()
    if digest(actual)!=digest(proposed):raise RuntimeError("Post-sync differs; backup "+str(bj["id"]))
    validate_state(actual)
    rep["status"]="APPLIED_AND_VERIFIED"
    rep["backupId"]=bj["id"]
    write("EXTERNAL_STRICT_APPLIED.json",rep)
    print("EXTERNAL_STRICT_APPLIED="+json.dumps({k:v for k,v in rep.items() if k!="songs"},ensure_ascii=False),flush=True)
if __name__=="__main__":main()
