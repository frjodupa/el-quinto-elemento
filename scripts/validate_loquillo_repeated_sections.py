#!/usr/bin/env python3
"""Per-line corroboration for Loquillo song with repetitions omitted by published tab.
Dry run by default. No lyric or existing chord is ever replaced.
"""
import difflib, hashlib, json, os, time
from pathlib import Path
import requests
import audit_songbook as a
OUT=Path("loquillo_alignment_output");OUT.mkdir(exist_ok=True)
IDS=("79","93")
TITLE="EL RITMO DEL GARAJE"
SOURCE_ID=2639544
SOURCE_HASH="804b1073c6bb279199ea228005e671000a152b0170a56a615cc3b8"
ALLOW=os.getenv("ALLOW_LIVE_WRITE","0")=="1"

def norm(s):
 return a.normalized_lyrics(s).replace("\n"," ").strip()

def remote():
 d=a.live_get_json("/export?ts="+str(int(time.time()*1000)))
 if not isinstance(d.get("storage"),dict):raise RuntimeError("D1 no disponible")
 return d["storage"],d.get("updatedAt")

def dry_validate(song,model):
 text= song["texto"]
 target=text.splitlines()
 orig=a.normalize_chord_data(song["letraConAcordes"])
 if song["titulo"]!=TITLE or a.count_chords(orig)!=0:raise RuntimeError("Título o acordes ya cambiaron")
 src_lines=model["lines"]
 src_norm=[norm(s) for s in src_lines]
 placements_by_src={}
 for p in model["placements"]:
  placements_by_src.setdefault(int(p["line"]),[]).append(p)
 matches=[]
 expanded=[]
 best_idx={}
 for i,tar in enumerate(target):
  nt=norm(tar)
  if not nt:
   expanded.append("");continue
  scores=[difflib.SequenceMatcher(None,nt,x).ratio() if x else 0 for x in src_norm]
  best=max(scores,default=0)
  candidates=[j for j,score in enumerate(scores) if score>=best-0.0001]
  # Choose same-lyric arrangement with chord anchors if available.
  si=max(candidates,key=lambda j:(len(placements_by_src.get(j,[])), -j)) if candidates else -1
  best_idx[i]=(si,best)
  matches.append(best)
  expanded.append(src_lines[si] if si>=0 else "")
 strong=sum(v>=.86 for v in matches)
 exact=sum(v>=.98 for v in matches)
 expanded_sim=a.similarity(text,"\n".join(expanded))
 if strong/max(1,len(matches))<.85 or exact/max(1,len(matches))<.50 or expanded_sim<.85:
  raise RuntimeError(f"Letra insuficientemente validada: total={len(matches)}, strong={strong}, exact={exact}, expanded={expanded_sim:.3f}")
 chordData=a.normalize_chord_data(orig)
 additions=0
 eligible=[]
 for line, (si, score) in best_idx.items():
  if score<.94 or si<0:continue
  ps=placements_by_src.get(si,[])
  if not ps:continue
  sw=src_lines[si].split()
  tw=target[line].split()
  if not tw:continue
  for p in ps:
   wi=int(p["word"])
   if len(sw)<=1 or len(tw)<=1:dest=min(wi,len(tw)-1)
   else:dest=round(wi*(len(tw)-1)/max(1,len(sw)-1))
   dest=max(0,min(dest,len(tw)-1))
   key=f"{line}:{dest}"
   if not chordData["words"].get(key):
    chordData["words"][key]=p["chord"]
    additions+=1
  eligible.append(line)
 if additions<20:
  raise RuntimeError("No se han podido colocar suficientes acordes comprobados: "+str(additions))
 for k in ("lines","intro","introText","instrumentals","instrumentalsText","references"):
  if chordData[k]!=orig[k]:raise RuntimeError("Se modificó estructura protegida: "+k)
 return chordData,{"id":song["id"],"title":TITLE,"sourceId":SOURCE_ID,
                    "sourceURL":f"https://tabs.ultimate-guitar.com/tab/{SOURCE_ID}",
                    "targetLyricLines":len(matches),"strongMatchedLines":strong,
                    "exactMatchedLines":exact,
                    "expandedVersionSimilarityPct":round(expanded_sim*100,2),
                    "chordMatchedLines":len(set(eligible)),
                    "chordsBefore":0,"chordsAfter":a.count_chords(chordData),
                    "added":additions}

def main():
 storage,_=remote()
 songs={x["id"]:x for x in a.build_songbook(storage)}
 a.limiter.wait()
 src=a.ug_run(["-mode","fetch","-id",str(SOURCE_ID)])
 content=str(src.get("content") or "")
 h=hashlib.sha256(content.encode()).hexdigest()
 if h!=SOURCE_HASH:raise RuntimeError("Fuente UG modificada: sin cambios")
 if "loquillo" not in a.deaccent(str(src.get("artist_name") or "")).lower():
  raise RuntimeError("Artista no corresponde a Loquillo")
 model=a.ug_to_model(content)
 candidates={}
 rows=[]
 for sid in IDS:
  cand,row=dry_validate(songs[sid],model)
  candidates[sid]=cand
  rows.append(row)
 status={"dryRun":not ALLOW,"sourcesVerified":True,"rows":rows}
 (OUT/"ALIGNMENT_REPORT.json").write_text(json.dumps(status,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
 if not ALLOW:
  print(json.dumps({"status":"VALIDATION_OK",**status},ensure_ascii=False),flush=True);return
 latest,_=remote()
 newer={x["id"]:x for x in a.build_songbook(latest)}
 for sid in IDS:
  if newer[sid]["texto"]!=songs[sid]["texto"] or newer[sid]["titulo"]!=TITLE or newer[sid]["letraConAcordes"]!=songs[sid]["letraConAcordes"]:
   raise RuntimeError("La canción cambió mientras se verificaba: "+sid)
 b=requests.post(a.LIVE_BASE+"/api/backups",json={"action":"create"},
   headers={**a.HEADERS,"Content-Type":"application/json"},timeout=30)
 b.raise_for_status();j=b.json()
 if not j.get("ok") or not j.get("id"):raise RuntimeError("No hay copia de seguridad, no se escribe")
 for sid,data in candidates.items():
  latest[f"quintoElemento.chords.v2.{sid}"]=json.dumps(data,ensure_ascii=False,separators=(",",":"))
 r=requests.put(a.LIVE_BASE+"/api/sync",json={"data":latest},
   headers={**a.HEADERS,"Content-Type":"application/json"},timeout=60)
 r.raise_for_status()
 if not r.json().get("ok"):raise RuntimeError("Escritura no confirmada")
 verify,_=remote()
 for sid,cand in candidates.items():
  if json.loads(verify[f"quintoElemento.chords.v2.{sid}"])!=cand:raise RuntimeError("Error verificando D1 "+sid)
 done={"status":"APPLIED_AND_VERIFIED","backupId":j["id"],"rows":rows}
 (OUT/"APPLIED_STATUS.json").write_text(json.dumps(done,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
 print(json.dumps(done,ensure_ascii=False),flush=True)
if __name__=="__main__":main()
