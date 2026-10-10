#!/usr/bin/env python3
"""Apply a small, independently verified chord-only patch to live EQE D1.

Requires ALLOW_LIVE_WRITE=1. Never modifies titles, lyrics, intros, instrumentals,
references, or existing nonempty chord slots. Creates a Cloudflare backup first.
Stops on changed sources, unexpected chord baselines or low mapping confidence.
"""
import copy
import hashlib
import json
import os
import time
from pathlib import Path

import requests
import audit_songbook as a

OUT=Path(os.getenv("SAFE_PATCH_OUT","safe_patch_output"))
OUT.mkdir(parents=True,exist_ok=True)
ALLOW_WRITE=os.getenv("ALLOW_LIVE_WRITE","0")=="1"

EXPECTED={
 "22":{"title":"EL BLUES DEL AUTOBÚS","artist":"Miguel Ríos","tab_id":1141219,
       "source_hash":"e0ec7b2025e7e2857ada757a070e8717936444c44d3b318e1d694b3dc8260e00",
       "before":60,"min_add":25,"min_conf":0.90,"max_conflicts":3},
 "71":{"title":"CIEN GAVIOTAS","artist":"Duncan Dhu","tab_id":1064038,
       "source_hash":"08df8d887d3a26300757638575af7edad525dc0ed1d1d6c15c51ef295386ef25",
       "before":65,"min_add":25,"min_conf":0.80,"max_conflicts":11},
 "85":{"title":"CIEN GAVIOTAS","artist":"Duncan Dhu","tab_id":1064038,
       "source_hash":"08df8d887d3a26300757638575af7edad525dc0ed1d1d6c15c51ef295386ef25",
       "before":65,"min_add":25,"min_conf":0.80,"max_conflicts":11},
 "77":{"title":"EL LÍMITE","artist":"La Frontera","tab_id":1617810,
       "source_hash":"d823105a466a99266df35e2d609d1993b3ed114c211343152469b046d9b04ee1",
       "before":70,"min_add":35,"min_conf":0.82,"max_conflicts":4},
 "91":{"title":"EL LÍMITE","artist":"La Frontera","tab_id":1617810,
       "source_hash":"d823105a466a99266df35e2d609d1993b3ed114c211343152469b046d9b04ee1",
       "before":70,"min_add":35,"min_conf":0.82,"max_conflicts":4},
}

def dump(name,obj):
 (OUT/name).write_text(json.dumps(obj,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")

def safe_fetch_storage():
 response=a.live_get_json("/export?ts="+str(int(time.time()*1000)))
 data=response.get("storage")
 if not isinstance(data,dict):
  raise RuntimeError("No se pudo recuperar almacenamiento D1 válido")
 return data,response.get("updatedAt")

def current_titles_and_data(storage):
 return {s["id"]:s for s in a.build_songbook(storage)}

def evaluate(s,source,spec):
 old=a.normalize_chord_data(s["letraConAcordes"])
 before=a.count_chords(old)
 if s["titulo"]!=spec["title"]:raise ValueError("Título distinto del manifiesto")
 if before!=spec["before"]:raise ValueError(f"Se ha modificado el cancionero: acordes {before} != {spec['before']}")
 model=a.ug_to_model(source)
 sim=a.similarity(s["texto"],model["lyrics"])
 mapped,coverage=a.map_placements(model,s["texto"])
 shift,conf=a.choose_shift(mapped,old["words"])
 candidate,additions,conflicts=a.apply_mapped_chords(old,mapped,shift)
 after=a.count_chords(candidate)
 if not (sim>=0.97 and coverage>=0.85 and shift==0 and conf>=spec["min_conf"]
         and conflicts<=spec["max_conflicts"] and additions>=spec["min_add"]
         and after==before+additions and a.source_chord_count(model)>=before):
  raise ValueError(f"No supera comprobación estricta: sim={sim:.3f}, cobertura={coverage:.3f}, shift={shift}, confianza={conf:.3f}, conflictos={conflicts}, añadidos={additions}, fuente={a.source_chord_count(model)}")
 # Existing structures, including intro, instrumental and references, must stay byte-for-byte identical.
 for section in ("intro","introText","instrumentals","instrumentalsText","references","lines"):
  if candidate.get(section)!=old.get(section):
   raise ValueError("Se ha alterado estructura protegida: "+section)
 for key,value in old["words"].items():
  if candidate["words"].get(key)!=value:raise ValueError("Ha cambiado un acorde existente: "+key)
 return candidate,{"id":s["id"],"title":s["titulo"],"artist":spec["artist"],"sourceId":spec["tab_id"],
                   "sourceURL":f"https://tabs.ultimate-guitar.com/tab/{spec['tab_id']}",
                   "similarityPct":round(sim*100,2),"mappedPct":round(coverage*100,2),
                   "shift":shift,"shiftConfidencePct":round(conf*100,2),
                   "conflictsRetained":conflicts,"chordsBefore":before,"chordsAfter":after,"chordsAdded":additions}

def main():
 original_storage,updated=safe_fetch_storage()
 all_songs=current_titles_and_data(original_storage)
 originals={}
 for sid in EXPECTED:
  if sid not in all_songs:raise RuntimeError("No existe el registro "+sid)
  originals[sid]=copy.deepcopy(all_songs[sid])
 # Fetch each exact, previously checked UG tab just once, NOT top-ranked search results.
 sources={}
 for spec in EXPECTED.values():
  tid=spec["tab_id"]
  if tid in sources:continue
  a.limiter.wait()
  data=a.ug_run(["-mode","fetch","-id",str(tid)])
  content=str(data.get("content") or "")
  if not content:raise RuntimeError("Fuente vacía: "+str(tid))
  actual=hashlib.sha256(content.encode()).hexdigest()
  if actual!=spec["source_hash"]:raise RuntimeError("La fuente ha cambiado; abortado sin escribir: "+str(tid))
  source_artist=str(data.get("artist_name") or "").casefold()
  # Verify source artist with accent-insensitive identity before use.
  if a.deaccent(spec["artist"]).lower() not in a.deaccent(source_artist).lower() and a.deaccent(source_artist).lower() not in a.deaccent(spec["artist"]).lower():
   raise RuntimeError("Artista de fuente inesperado para "+str(tid)+": "+source_artist)
  sources[tid]=content

 candidates={}; rows=[]
 for sid,spec in EXPECTED.items():
  candidate,row=evaluate(originals[sid],sources[spec["tab_id"]],spec)
  candidates[sid]=candidate
  rows.append(row)
 dump("PATCH_VALIDATION.json",{"status":"validated","dryRun":not ALLOW_WRITE,"songs":rows,"sourceUpdatedAt":updated})

 if not ALLOW_WRITE:
  print(json.dumps({"status":"DRY_RUN_OK","updatedAt":updated,"songs":rows},ensure_ascii=False),flush=True)
  return

 # Capture latest D1 and guarantee every target lyrics/chord record is unchanged.
 latest,latest_updated=safe_fetch_storage()
 latest_songs=current_titles_and_data(latest)
 for sid in EXPECTED:
  if latest_songs[sid]["texto"]!=originals[sid]["texto"] or latest_songs[sid]["titulo"]!=originals[sid]["titulo"]:
   raise RuntimeError("Letra o título cambió en directo, abortado: "+sid)
  if latest_songs[sid]["letraConAcordes"]!=originals[sid]["letraConAcordes"]:
   raise RuntimeError("Acordes cambiaron en directo, abortado: "+sid)

 # Backup is mandatory; do not write if the backup was not confirmed.
 b=requests.post(a.LIVE_BASE+"/api/backups",headers={**a.HEADERS,"Content-Type":"application/json"},
   json={"action":"create"},timeout=30)
 b.raise_for_status()
 backup=b.json()
 if not backup.get("ok") or not backup.get("id"):
  raise RuntimeError("Cloudflare no confirmó copia. Ningún cambio aplicado.")

 # Apply ONLY five selected chord maps to the latest version of all remaining keys.
 for sid,value in candidates.items():
  latest[f"quintoElemento.chords.v2.{sid}"]=json.dumps(value,ensure_ascii=False,separators=(",",":"))
 u=requests.put(a.LIVE_BASE+"/api/sync",headers={**a.HEADERS,"Content-Type":"application/json"},
   json={"data":latest},timeout=60)
 u.raise_for_status()
 if not u.json().get("ok"):raise RuntimeError("D1 no confirmó escritura")
 verified,_=safe_fetch_storage()
 for sid,candidate in candidates.items():
  live=json.loads(verified[f"quintoElemento.chords.v2.{sid}"])
  if live!=candidate:raise RuntimeError("Verificación posterior falló para "+sid)
 report={"status":"APPLIED_AND_VERIFIED","backupId":backup["id"],"songs":rows,
         "versionTouched":False,"originalLyricsTouched":False,
         "introInstrumentalsReferencesPreserved":True,
         "originalStorageKeyCount":len(original_storage),"updatedStorageKeyCount":len(latest)}
 dump("PATCH_APPLIED_STATUS.json",report)
 print(json.dumps(report,ensure_ascii=False),flush=True)

if __name__=="__main__":
 main()
