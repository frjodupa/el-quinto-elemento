#!/usr/bin/env python3
"""Guarded chord-only recovery for 3 identified songs that currently have 0 chords.

STRICT source SHA, exact performer/title, very-high-confidence word alignment,
zero existing chords, stable D1 version, pass integrity, and Cloudflare backup.
Dry-run by default. Never replaces lyrics or intro/instrumental/references.
"""
import collections, copy, hashlib, json, os, time
from pathlib import Path
import requests
import audit_songbook as a
import strict_line_chords_86 as align

OUT=Path("eqe-86-three-chord-patch")
OUT.mkdir(exist_ok=True)
APPLY=os.environ.get("APPLY_SAFE_THREE_CHORDS","0")=="1"
MIN_SCORE=0.985
# A high-confidence subset is the only authorized change; never import guesses.
MIN_POSITIONS={"77":25,"80":15,"81":10}
CUSTOM_KEY="quintoElemento.customSongs.v1"
PASS_KEY="quintoElemento.passes.v1"

def status(name,payload):
  (OUT/name).write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")

def digest(obj):
  return hashlib.sha256(json.dumps(obj,sort_keys=True,ensure_ascii=False,separators=(",",":")).encode()).hexdigest()

def live():
  state,remote=a.load_remote_storage()
  updated=remote.get("payload",{}).get("updatedAt")
  if not isinstance(updated,int):raise RuntimeError("No se puede validar versión D1")
  return state,updated

def validate_inventory(state):
  songs={s["id"]:s for s in a.build_songbook(state)}
  customs=a.safe_json(state.get(CUSTOM_KEY,"[]"),[])
  passes=a.safe_json(state.get(PASS_KEY,"[]"),[])
  if len(songs)!=86 or len(customs)!=15 or not isinstance(passes,list):
    raise RuntimeError(f"Repertorio cambió: {len(songs)} canciones, {len(customs)} personalizadas; no escribir")
  pasma=[p for p in passes if p.get("name")=="LA PASMA (NUEVA)"]
  if len(pasma)!=1 or len(pasma[0].get("songs",[]))!=23 or any(int(i)<0 or int(i)>=86 for i in pasma[0]["songs"]):
    raise RuntimeError("La Pasma no está íntegra; abortado")
  return songs

def exact_source(song,pin):
  if align.normalize_label(song["titulo"])!=align.normalize_label(pin["title"]):
    raise RuntimeError("Título no coincide con fuente fijada")
  a.limiter.wait()
  tab=a.ug_run(["-mode","fetch","-id",str(pin["id"])])
  raw=str(tab.get("content") or "")
  if hashlib.sha256(raw.encode("utf-8")).hexdigest()!=pin["sha256"]:
    raise RuntimeError("Fuente externa cambió; no se escribe")
  src=align.normalize_label(tab.get("artist_name"))
  target=align.normalize_label(pin["artist"])
  if not (target in src or src in target):
    raise RuntimeError("Artista de fuente no corresponde")
  model=a.ug_to_model(raw)
  return model,tab

def build_candidates(storage):
  songs=validate_inventory(storage)
  result={}
  meta=[]
  for sid,pin in align.PINNED.items():
    song=songs[sid]
    original=a.normalize_chord_data(song["letraConAcordes"])
    if a.count_chords(original):
      raise RuntimeError(f"{song['titulo']} ya tiene acordes; requiere nueva auditoría")
    model,tab=exact_source(song,pin)
    segments=align.segment_candidates(song["texto"])
    matches=align.source_line_matches(model,segments)
    proposals=collections.defaultdict(set)
    mapped_segments=0
    for row in matches:
      if row["score"]<MIN_SCORE:continue
      mapped_segments+=1
      for li,wi,chord in row["placements"]:
        proposals[f"{li}:{wi}"].add(chord)
    safe={k:next(iter(values)) for k,values in proposals.items() if len(values)==1}
    conflicts=sum(len(values)>1 for values in proposals.values())
    if len(safe)<MIN_POSITIONS[sid]:
      raise RuntimeError(f"Pocas posiciones verificadas para {song['titulo']}: {len(safe)}")
    # Every proposal must map onto an existing token in the original user's text.
    lines=song["texto"].splitlines()
    for key,chord in safe.items():
      li,wi=(int(x) for x in key.split(":"))
      if not (0<=li<len(lines) and 0<=wi<len(lines[li].split())):
        raise RuntimeError("Un acorde quedaría fuera de una palabra real: "+key)
      if not a.is_chord(chord):
        raise RuntimeError("Acorde no reconocido: "+chord)
    newdata=copy.deepcopy(original)
    assert not newdata["words"]
    newdata["words"].update(safe)
    for section in ("lines","intro","introText","instrumentals","instrumentalsText","references"):
      if newdata[section]!=original[section]:
        raise RuntimeError("Cambios en contenido protegido: "+section)
    result[sid]=newdata
    total_lines=sum(bool(x.strip()) for x in lines)
    covered=len(set(int(k.split(":")[0]) for k in safe))
    row={"id":int(sid),"title":song["titulo"],"artist":pin["artist"],"sourceId":pin["id"],
      "sourceURL":str(tab.get("urlWeb") or f"https://tabs.ultimate-guitar.com/tab/{pin['id']}"),
      "scoreThresholdPct":MIN_SCORE*100,"sourceHash":pin["sha256"],
      "chordsBefore":0,"newChordPositions":len(safe),
      "linesWithChords":covered,"lyricLines":total_lines,
      "coveragePct":round(100*covered/max(1,total_lines),1),
      "ambiguousPositionsSkipped":conflicts,
      "lyricTextTouched":False,"introInstrumentalReferencesTouched":False}
    meta.append(row)
    print("PROPOSED_SAFE_PATCH="+json.dumps(row,ensure_ascii=False),flush=True)
  return result,meta

def main():
  original,original_ts=live()
  patches,rows=build_candidates(original)
  proposal={"readOnly":not APPLY,"candidates":rows,"sourceSnapshotTimestamp":original_ts,
            "description":"Only new chord positions; no original lyrics or metadata altered"}
  status("PREFLIGHT.json",proposal)
  if not APPLY:
    print("SAFE_PATCH_DRY_RUN=YES",flush=True)
    return
  latest,latest_ts=live()
  if latest_ts!=original_ts or digest(latest)!=digest(original):
    raise RuntimeError("D1 changed while checking sources; cancel without writing")
  # Mandatory separate manual cloud backup of exact pre-edit snapshot.
  response=requests.post(a.LIVE_BASE+"/api/backups",headers={**a.HEADERS,"Content-Type":"application/json"},
                         json={"action":"create"},timeout=40)
  response.raise_for_status()
  backup=response.json()
  backup_id=backup.get("id")
  if backup.get("ok") is not True or not backup_id:
    raise RuntimeError("No Cloudflare backup ID confirmed: abort before write")
  latest2,latest_ts2=live()
  if latest_ts2!=original_ts or digest(latest2)!=digest(original):
    raise RuntimeError(f"D1 changed after backup #{backup_id}, abort without writing")
  next_state=copy.deepcopy(latest2)
  for sid,newdata in patches.items():
    next_state[f"quintoElemento.chords.v2.{sid}"]=json.dumps(newdata,ensure_ascii=False,separators=(",",":"))
  # Expected-version-aware compare-and-swap; 409 means no edits.
  response=requests.put(a.LIVE_BASE+"/api/sync",headers={**a.HEADERS,"Content-Type":"application/json"},
                        json={"data":next_state,"expectedUpdatedAt":original_ts},timeout=75)
  if response.status_code==409:
    raise RuntimeError(f"Concurrent D1 change; cloud refused upload. Backup #{backup_id}")
  response.raise_for_status()
  if response.json().get("ok") is not True:
    raise RuntimeError(f"Write not confirmed; backup #{backup_id}")
  after,final_ts=live()
  if digest(after)!=digest(next_state):
    raise RuntimeError(f"Post-write mismatch: manual recovery available in backup #{backup_id}")
  final_songs=validate_inventory(after)
  for sid in patches:
    before=original[f"quintoElemento.chords.v2.{sid}"] if f"quintoElemento.chords.v2.{sid}" in original else None
    now=after.get(f"quintoElemento.chords.v2.{sid}")
    if not now:raise RuntimeError(f"Missing chord changes for {sid}")
    if final_songs[sid]["texto"]!=a.build_songbook(original)[int(sid)]["texto"]:
      raise RuntimeError("Lyrics were unexpectedly changed")
  confirmed={"status":"APPLIED_AND_VERIFIED","backupId":backup_id,"oldUpdatedAt":original_ts,
             "newUpdatedAt":final_ts,"songs":rows,"passUnchanged":True,
             "versionsUnchanged":True,"lyricsUnchanged":True}
  status("APPLIED.json",confirmed)
  print("LIVE_SAFE_PATCH_VERIFIED="+json.dumps(confirmed,ensure_ascii=False),flush=True)

if __name__=="__main__":main()
