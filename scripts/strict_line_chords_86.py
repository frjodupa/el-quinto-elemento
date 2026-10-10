#!/usr/bin/env python3
"""STRICT read-only chord placement audit for the three recovered no-chord songs.

Handles lyric lines split into 2–5 physical rows in EQE, without changing lyric
text. Fetches only pinned UG tabs verified by title, performer, SHA-256. Creates
a proposed "words" chord map and a metadata-only confidence report, NOT a D1
write. The project can review candidate positions before manual/live apply.
"""
import collections
import difflib
import hashlib
import json
import re
import unicodedata
from pathlib import Path
import audit_songbook as a

OUT=Path("eqe-86-strict-placement")
OUT.mkdir(exist_ok=True)

PINNED={
  "77":{"title":"SABOR DE AMOR","artist":"Danza Invisible","id":1036283,
    "sha256":"8721fb338e30cc8c13dc6b8e2cf4866ac07e42d303af6ff355ff8e602a5c373d"},
  "80":{"title":"EL RITMO DEL GARAJE","artist":"Loquillo","id":2639544,
    "sha256":"804b1073c6bb279199ea228005e671000a152b0170ea20cb6e17a56a615cc3b8"},
  "81":{"title":"ENAMORADO DE LA MODA JUVENIL","artist":"Radio Futura","id":1612960,
    "sha256":"bb0a26f83fb6dc1ee26a6d8d3c084fc0c8904114502e724736e000d7dff10ff3"}
}

def normalized_word(value):
    s=unicodedata.normalize("NFKD",str(value or "")).lower()
    s="".join(c for c in s if not unicodedata.combining(c))
    s=s.replace("ñ","n")
    return re.sub("[^a-z0-9]","",s)

def raw_words(value):
    return re.findall(r"\S+",str(value or ""))

def normalized_tokens(value):
    return [x for x in (normalized_word(w) for w in raw_words(value)) if x]

def normalize_label(value):
    return " ".join(normalized_tokens(value))

def chord_root(value):
    return a.chord_root(value)

def chord_keys(model):
    r=collections.defaultdict(list)
    for p in model["placements"]:
        r[int(p["line"])].append((int(p["word"]),str(p["chord"])))
    return r

def segment_candidates(text,max_lines=5):
    lines=str(text).splitlines()
    out=[]
    for i,li in enumerate(lines):
        if not li.strip():continue
        members=[]
        for j in range(i,min(i+max_lines,len(lines))):
            if not lines[j].strip():
                break
            if re.match(r"^\s*(?:intro|instrumental|solo|coro|chorus|estrofa|verso|puente|final)\s*:?\s*$",lines[j],re.I):
                break
            tok=raw_words(lines[j])
            members.append((j,tok))
            flat=[word for _,ws in members for word in ws]
            tok_norm=[normalized_word(t) for t in flat]
            if not all(tok_norm):continue
            if len(tok_norm)>=2:
                out.append({"start":i,"end":j,"words":flat,"tokens":tok_norm,"members":members})
    return out

def map_token_indexes(src,tgt):
    seq=difflib.SequenceMatcher(None,src,tgt,autojunk=False)
    indexes={}
    for src_a,tgt_b,n in seq.get_matching_blocks():
        for k in range(n):indexes[src_a+k]=tgt_b+k
    return indexes,seq.ratio()

def source_line_matches(model,target_segments):
    out=[]
    anchors=chord_keys(model)
    for si,source_line in enumerate(model["lines"]):
        chords=anchors.get(si,[])
        if not chords:continue
        st=normalized_tokens(source_line)
        if len(st)<2:continue
        scorelist=[]
        for seg in target_segments:
            # Shared lyric content only. Never match by title or a single shared word.
            mapping,ratio=map_token_indexes(st,seg["tokens"])
            if ratio<0.86 or len(mapping)<max(2,int(len(st)*.7)):continue
            flat_src=" ".join(st); flat_tgt=" ".join(seg["tokens"])
            char_similarity=difflib.SequenceMatcher(None,flat_src,flat_tgt,autojunk=False).ratio()
            if char_similarity<0.88:continue
            chord_map=[]
            for word,chord in chords:
                if word not in mapping:continue
                w=mapping[word]
                running=0
                for line_index,words in seg["members"]:
                    if w < running+len(words):
                        chord_map.append((line_index,w-running,chord))
                        break
                    running+=len(words)
            if not chord_map:continue
            scorelist.append((0.55*ratio+0.45*char_similarity,seg["start"],seg["end"],tuple(chord_map)))
        if scorelist:
            scorelist.sort(reverse=True)
            # All high-confidence repeated matched lines are retained.
            best=scorelist[0][0]
            # A score >=0.92 means near-exact lyric content and token matching.
            for score,first,last,p in scorelist:
                if score>=.92 and best-score<.085:
                    out.append({"sourceLine":si,"start":first,"end":last,"score":round(score,4),"placements":p})
    return out

def main():
    storage,metadata=a.load_remote_storage()
    songs={s["id"]:s for s in a.build_songbook(storage)}
    results=[]
    for sid,pinned in PINNED.items():
        song=songs.get(sid)
        if not song or normalize_label(song["titulo"])!=normalize_label(pinned["title"]):
            raise RuntimeError(f"Live title changed at {sid}: stop without modifications")
        old=a.normalize_chord_data(song["letraConAcordes"])
        if a.count_chords(old)>0:
            raise RuntimeError(f"Already has chords at {sid}. Do not overwrite a concurrent edit")
        a.limiter.wait()
        full=a.ug_run(["-mode","fetch","-id",str(pinned["id"])])
        raw=str(full.get("content") or "")
        if hashlib.sha256(raw.encode("utf-8")).hexdigest()!=pinned["sha256"]:
            raise RuntimeError(f"UG source changed for {sid}; review manually")
        remote_artist=normalize_label(full.get("artist_name"))
        if normalize_label(pinned["artist"]) not in remote_artist and remote_artist not in normalize_label(pinned["artist"]):
            raise RuntimeError(f"Artist mismatch at {sid}: {remote_artist}")
        model=a.ug_to_model(raw)
        segments=segment_candidates(song["texto"])
        matches=source_line_matches(model,segments)
        proposal=collections.defaultdict(set)
        maxconfidence=collections.defaultdict(float)
        for row in matches:
            for physical_idx,word_idx,chord in row["placements"]:
                k=f"{physical_idx}:{word_idx}"
                proposal[k].add(chord)
                maxconfidence[k]=max(maxconfidence[k],row["score"])
        safe={k:next(iter(v)) for k,v in proposal.items() if len(v)==1 and maxconfidence[k]>=.92}
        conflicted={k:sorted(v) for k,v in proposal.items() if len(v)>1}
        proposed=collections.OrderedDict(sorted(safe.items(),key=lambda item:tuple(int(z) for z in item[0].split(":"))))
        source_lyric_lines=len(model["lines"])
        target_lines=len([s for s in song["texto"].splitlines() if s.strip()])
        covered=len(set(int(k.split(":")[0]) for k in safe))
        r={"id":int(sid),"title":song["titulo"],"artist":pinned["artist"],"sourceTabId":pinned["id"],
          "sourceURL":str(full.get("urlWeb") or f"https://tabs.ultimate-guitar.com/tab/{pinned['id']}"),
          "sourceHash":pinned["sha256"],"sourceChordAnchors":len(model["placements"]),
          "sourceLyricLines":source_lyric_lines,"targetLyricLines":target_lines,
          "sourceLineSegmentsMatched":len(matches),"safeUniqueChordPositions":len(safe),
          "targetLinesWithProposedChords":covered,"targetCoveragePct":round(100*covered/max(1,target_lines),1),
          "conflictingPositions":len(conflicted),"lowConfidencePositions":sum(len(v)==1 and maxconfidence[k]<.92 for k,v in proposal.items()),
          "preservesLyricsAndExistingChords":True,"dryRun":True,"status":"needs_human_chord_placement_review"}
        results.append(r)
        # Proposals contain musical chord symbols/indices only, never lyrics.
        (OUT/f"{sid}_PROPOSED_CHORD_POSITIONS.json").write_text(
          json.dumps({"metadata":r,"words":proposed,"conflicts":conflicted},ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
        print("STRICT_CANDIDATE="+json.dumps(r,ensure_ascii=False),flush=True)
    (OUT/"STRICT_SUMMARY.json").write_text(json.dumps({"songs":results,"readOnly":True},ensure_ascii=False,indent=2)+"\n")
    print("STRICT_COMPLETED_READ_ONLY=YES",flush=True)
if __name__=="__main__":main()
