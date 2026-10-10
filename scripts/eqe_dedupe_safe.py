#!/usr/bin/env python3
"""Full live D1 inventory + safe deduplication of duplicated custom songs.

DRY_RUN is default. APPLY_DEDUPE=1 writes only when all invariants hold, after
creating a mandatory manual Cloudflare backup. No lyric changes or deletion of
the first 85 unique entries. Existing pass song indices are migrated.
"""
import copy
import hashlib
import json
import os
import re
import time
import unicodedata
from collections import defaultdict
from pathlib import Path

import requests
import audit_songbook as a

OUT=Path(os.environ.get("EQE_DEDUPE_DIR","dedupe_output"))
OUT.mkdir(parents=True,exist_ok=True)
LIVE=a.LIVE_BASE
HEADERS={**a.HEADERS,"Content-Type":"application/json"}
FIRST_EXTRA=71
EXPECTED_CUSTOM=28
EXPECTED_TOTAL=99
EXPECTED_UNIQUE=85
EXPECTED_PAIR_MAP={i:i-14 for i in range(85,99)}
PASS_KEY="quintoElemento.passes.v1"
CUSTOM_KEY="quintoElemento.customSongs.v1"

def normalize_title(s):
    return " ".join(unicodedata.normalize("NFC",str(s or "")).casefold().split())

def sha_storage(obj):
    return hashlib.sha256(json.dumps(obj,sort_keys=True,ensure_ascii=False,separators=(",",":")).encode()).hexdigest()

def jparse(s,default):
    try:
        x=json.loads(s) if isinstance(s,str) else s
        return x if isinstance(x,type(default)) else default
    except Exception:return default

def count(d):return a.count_chords(d)

def live():
    storage,meta=a.load_remote_storage()
    if not isinstance(storage,dict):
        raise RuntimeError("Export live storage no es diccionario")
    ts=meta.get("payload",{}).get("updatedAt",0)
    return storage,ts

def merged_chord_data(primary,secondary):
    primary=a.normalize_chord_data(primary)
    secondary=a.normalize_chord_data(secondary)
    dest=copy.deepcopy(primary)
    added=0
    for key in ("lines","words","instrumentals","instrumentalsText"):
        for index,value in secondary[key].items():
            if not str(value).strip():continue
            if not str(dest[key].get(index,"")).strip():
                dest[key][index]=value
                added+=1
            elif dest[key][index]!=value:
                raise RuntimeError("Conflicto en acordes "+key+" índice "+str(index))
    for key in ("intro","introText"):
        if not dest[key] and secondary[key]:
            dest[key]=secondary[key]
            added+=1
        elif dest[key] and secondary[key] and dest[key]!=secondary[key]:
            raise RuntimeError("Conflicto de secciones: "+key)
    if dest["references"]!=secondary["references"]:
        # References may encode locations. Never silently combine different IDs.
        if dest["references"] and secondary["references"]:
            raise RuntimeError("Conflicto entre referencias de duplicados")
        if not dest["references"]:dest["references"]=copy.deepcopy(secondary["references"])
    return dest,added

def build_plan(storage,updated_at):
    all_songs=a.build_songbook(storage)
    custom=jparse(storage.get(CUSTOM_KEY,"[]"),[])
    if len(all_songs)!=EXPECTED_TOTAL or len(custom)!=EXPECTED_CUSTOM:
        raise RuntimeError(f"Inventario inesperado: total={len(all_songs)}, extras={len(custom)}; se requieren 99 / 28")
    indexed={int(s["id"]):s for s in all_songs}
    pairs=[]
    clean=copy.deepcopy(storage)
    for duplicate,keep in EXPECTED_PAIR_MAP.items():
        first,extra=indexed[keep],indexed[duplicate]
        if normalize_title(first["titulo"])!=normalize_title(extra["titulo"]):
            raise RuntimeError(f"Pareja {keep}/{duplicate} tiene títulos diferentes")
        if a.normalized_lyrics(first["texto"])!=a.normalized_lyrics(extra["texto"]):
            raise RuntimeError(f"Pareja {keep}/{duplicate}: letra distinta, requiere revisión manual")
        merged,added=merged_chord_data(first["letraConAcordes"],extra["letraConAcordes"])
        if added:
            clean[f"quintoElemento.chords.v2.{keep}"]=json.dumps(merged,ensure_ascii=False,separators=(",",":"))
        pairs.append({"keepId":keep,"removeId":duplicate,"title":first["titulo"],
            "chordsKeepBefore":count(first["letraConAcordes"]),"chordsDuplicate":count(extra["letraConAcordes"]),
            "chordsAfter":count(merged),"mergedExtraSlots":added})
    # All 28 custom entries are confirmed: 14 distinct and 14 repeated.
    clean[CUSTOM_KEY]=json.dumps(custom[:14],ensure_ascii=False,separators=(",",":"))
    removed_keys=[]
    for key in list(clean):
        # Only per-song indexed keys for duplicate slots; not other application settings.
        if key.startswith("quintoElemento.") and re.search(r"\.(?:8[5-9]|9[0-8])$",key):
            removed_keys.append(key)
            del clean[key]

    passes=jparse(storage.get(PASS_KEY,"[]"),[])
    changed_passes=0
    replaced_refs=0
    for p in passes:
        if not isinstance(p,dict):
            raise RuntimeError("Formato de pase inválido")
        old=p.get("songs",[])
        if not isinstance(old,list):
            raise RuntimeError("Pase songs no es una lista")
        new=[]
        for i in old:
            if isinstance(i,bool) or not isinstance(i,int):
                raise RuntimeError("Referencia de canción no numérica en pase")
            if i<0 or i>=EXPECTED_TOTAL:raise RuntimeError("Índice del pase fuera de inventario")
            if i in EXPECTED_PAIR_MAP:
                replaced_refs+=1
            new.append(EXPECTED_PAIR_MAP.get(i,i))
        if new!=old:
            p["songs"]=new
            changed_passes+=1
    if changed_passes:clean[PASS_KEY]=json.dumps(passes,ensure_ascii=False,separators=(",",":"))

    # Detect unknown index references outside the dedicated pass data model.
    other_refs=[]
    for key,value in storage.items():
        lower=key.lower()
        if key==PASS_KEY:continue
        if any(tag in lower for tag in ("pass","setlist","playlist","repertor","sequence","queue")):
            if any(re.search(r"(?<!\d)"+str(idx)+r"(?!\d)",str(value)) for idx in EXPECTED_PAIR_MAP):
                other_refs.append(key)
    if other_refs:
        raise RuntimeError("Hay otros datos con posibles referencias a duplicados: "+",".join(other_refs))

    # Verify only intended Cloudflare keys changed.
    changed=[key for key in clean if storage.get(key)!=clean[key]]
    if set(clean)-set(storage):
        raise RuntimeError("Cambió la estructura de claves en una dirección imprevista")
    if not removed_keys and not changed:
        raise RuntimeError("Nada que limpiar: ya migrado")
    if sum(1 for s in all_songs if s["titulo"])!=EXPECTED_TOTAL:
        raise RuntimeError("Alguna canción original carece de título")
    report={"status":"READY","dryRun":os.getenv("APPLY_DEDUPE")!="1","liveUpdatedAt":updated_at,
        "liveSnapshotSha256":sha_storage(storage),
        "originalEntries":len(all_songs),"uniqueEntries":EXPECTED_UNIQUE,
        "duplicateRecordsRemoved":len(EXPECTED_PAIR_MAP),"pairs":pairs,
        "passesCount":len(passes),"passesRemapped":changed_passes,
        "passSongReferencesRemapped":replaced_refs,
        "removedIndexedKeyCount":len(removed_keys),"changedStoredKeyCount":len(changed),
        "existingBaseSongsPreserved":71}
    return clean,report

def publish_report(report,file="DEDUPE_PREFLIGHT.json"):
    (OUT/file).write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({k:v for k,v in report.items() if k!="pairs"},ensure_ascii=False),flush=True)
    for entry in report.get("pairs",[]):
        print(f"PAIR {entry['keepId']} <- {entry['removeId']}: {entry['title']} {entry['chordsKeepBefore']} / {entry['chordsDuplicate']} -> {entry['chordsAfter']}",flush=True)

def main():
    initial,ts=live()
    proposed,report=build_plan(initial,ts)
    publish_report(report)
    if os.getenv("APPLY_DEDUPE")!="1":return
    # Confirm current storage is unchanged before mandatory backup.
    latest,latest_ts=live()
    if sha_storage(latest)!=report["liveSnapshotSha256"]:
        raise RuntimeError("Otro dispositivo cambió datos en D1: no se borra nada")
    response=requests.post(LIVE+"/api/backups",headers=HEADERS,json={"action":"create"},timeout=30)
    response.raise_for_status()
    backup=response.json()
    if not backup.get("ok") or not backup.get("id"):
        raise RuntimeError("No se ha confirmado backup obligatorio; abortado")
    # Backup may take time: check latest storage once more.
    latest2,ts2=live()
    if sha_storage(latest2)!=report["liveSnapshotSha256"]:
        raise RuntimeError("D1 cambió después de backup; abortado, backup "+str(backup["id"]))
    resp=requests.put(LIVE+"/api/sync",headers=HEADERS,json={"data":proposed},timeout=60)
    resp.raise_for_status()
    if not resp.json().get("ok"):
        raise RuntimeError("Cloudflare no confirmó la actualización; revisar backup "+str(backup["id"]))
    after,_=live()
    if sha_storage(after)!=sha_storage(proposed):
        raise RuntimeError("Verificación posterior no coincide; copia de restauración "+str(backup["id"]))
    # Secondary invariant after write: 85 song records, all passes valid.
    songs_after=a.build_songbook(after)
    if len(songs_after)!=EXPECTED_UNIQUE:
        raise RuntimeError("Número final de canciones incorrecto")
    report.update({"status":"APPLIED_AND_VERIFIED","backupId":backup["id"],
        "finalEntries":len(songs_after),"finalSnapshotSha256":sha_storage(after)})
    publish_report(report,"DEDUPE_APPLIED.json")

if __name__=="__main__":main()
