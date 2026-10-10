#!/usr/bin/env python3
"""Read-only Cloudflare D1 diagnostic of the 23-song 'LA PASMA (NUEVA)' pass.

Never changes song, pass, chord, cloud storage, PWA version or backup data.
Exports only metadata and line indices; no copyrighted lyrics are published.
"""
import collections
import datetime as dt
import json
import pathlib
import re
import time
import unicodedata
import urllib.request

BASE="https://crimson-rice-1fe1.joseduqueparedes.workers.dev"
ORDER=[
"CIEN GAVIOTAS","CLAVADO EN UN BAR","ESCUELA DE CALOR","HACE CALOR",
"LOBO-HOMBRE EN PARÍS","MIL CALLES LLEVAN HACIA TI","SABOR DE AMOR","EL LÍMITE",
"LA CHICA DE AYER","EL RITMO DEL GARAJE","SALTA","NO PUEDO VIVIR SIN TI",
"ESO QUE TÚ ME DAS","INSURRECCIÓN","QUERIDA MILAGROS","ENAMORADO DE LA MODA JUVENIL",
"ADIÓS PAPÁ","CADILLAC SOLITARIO","CAROLINA","CUANDO BRILLE EL SOL",
"DÉJAME","FRÍO","MIÑA TERRA GALEGA"
]
OUTPUT=pathlib.Path("la_pasma_audit")
OUTPUT.mkdir(exist_ok=True)

def fetch(path):
    url=BASE+path+("&" if "?" in path else "?")+"ts="+str(time.time_ns())
    req=urllib.request.Request(url,headers={"Accept":"application/json","Cache-Control":"no-cache",
                                          "User-Agent":"EQE-Pasma-Audit/1.0"})
    with urllib.request.urlopen(req,timeout=35) as r:
        return json.loads(r.read().decode("utf8"))

def norm(x):
    x=unicodedata.normalize("NFKD",str(x or ""))
    x="".join(z for z in x if not unicodedata.combining(z))
    return re.sub(r"[^A-Z0-9]+"," ",x.upper()).strip()

def parse(s,default):
    try:return json.loads(s) if isinstance(s,str) else (s if s is not None else default)
    except Exception:return default

def embedded_songs():
    html=pathlib.Path("public/index.html").read_text(encoding="utf8")
    pos=html.index("let songs=")+len("let songs=")
    return json.JSONDecoder().raw_decode(html[pos:].lstrip())[0]

def chord_summary(val,text):
    d=parse(val,{})
    if not isinstance(d,dict):d={}
    words=d.get("words") or {}
    lines=d.get("lines") or {}
    if not isinstance(words,dict):words={}
    if not isinstance(lines,dict):lines={}
    lyrics=str(text or "").splitlines()
    total_nonempty=sum(bool(x.strip()) for x in lyrics)
    indexes=set()
    count=0
    for k,v in words.items():
        if str(v).strip():
            count+=len(re.split(r"\s*·\s*",str(v).strip()))
            try:indexes.add(int(str(k).split(":")[0]))
            except:pass
    for k,v in lines.items():
        if str(v).strip():
            count+=len(re.split(r"\s*·\s*",str(v).strip()))
            try:indexes.add(int(k))
            except:pass
    intro=d.get("intro") or ""
    if str(intro).strip():count+=len(str(intro).split("·"))
    for v in (d.get("instrumentals") or {}).values():
        if str(v).strip():count+=len(str(v).split("·"))
    valid=sum(1 for i in indexes if 0<=i<len(lyrics) and lyrics[i].strip())
    return {"chords":count,"nonemptyLyricLines":total_nonempty,"lyricLinesWithChord":valid,
            "coveragePct":round(100*valid/max(1,total_nonempty),1),
            "blankChordLines":max(0,total_nonempty-valid),
            "intro":bool(intro),"instrumentals":len(d.get("instrumentals") or {}),
            "references":len(d.get("references") or [])}

def main():
    ex=fetch("/export")
    storage=ex.get("storage") or {}
    base=embedded_songs()
    custom=parse(storage.get("quintoElemento.customSongs.v1","[]"),[])
    if not isinstance(custom,list):custom=[]
    raw=base+custom
    passes=parse(storage.get("quintoElemento.passes.v1","[]"),[])
    if not isinstance(passes,list):passes=[]
    arr=[]
    for i,s in enumerate(raw):
        if not isinstance(s,dict):continue
        title=storage.get(f"quintoElemento.title.v1.{i}",s.get("title") or "")
        body=storage.get(f"quintoElemento.lyrics.v1.{i}",s.get("text") or "")
        arr.append({"id":i,"title":title,"titleKey":norm(title),
            "stats":chord_summary(storage.get(f"quintoElemento.chords.v2.{i}"),body)})
    byTitle=collections.defaultdict(list)
    for a in arr:byTitle[a["titleKey"]].append(a)
    selected=[p for p in passes if norm(p.get("name"))==norm("LA PASMA (NUEVA)")]
    passResults=[]
    for p in selected:
        ids=p.get("songs",[])
        passResults.append({"passId":p.get("id"),"name":p.get("name"),
            "songIDs":ids,"brokenIDRefs":[x for x in ids if not isinstance(x,int) or x<0 or x>=len(arr)],
            "titlesInOrder":[arr[x]["title"] if isinstance(x,int) and 0<=x<len(arr) else "REGISTRO INVÁLIDO" for x in ids]})
    songs=[]
    for pos,title in enumerate(ORDER,1):
        found=byTitle.get(norm(title),[])
        songs.append({"order":pos,"expectedTitle":title,
            "foundIDs":[x["id"] for x in found],
            "variants":[{"id":x["id"],**x["stats"]} for x in found],
            "inPass":bool(any(any(x["id"] in (p.get("songs") or []) for x in found) for p in selected))})
    summary={"totalSongs":len(arr),"baseSongs":len(base),"customSongs":len(custom),
        "passesCount":len(passes),"passesNames":[p.get("name") for p in passes],
        "targetPassExists":bool(selected),"targetPassCount":len(selected),
        "targetPassBrokenIDs":sum(len(p["brokenIDRefs"]) for p in passResults),
        "expected23Present":sum(bool(x["foundIDs"]) for x in songs),
        "expected23Missing":sum(not x["foundIDs"] for x in songs),
        "expected23ZeroChords":sum(not x["variants"] or all(v["chords"]==0 for v in x["variants"]) for x in songs),
        "expected23Under50PctCoverage":sum(bool(x["variants"]) and max(v["coveragePct"] for v in x["variants"])<50 for x in songs),
        "duplicateTitleGroups":sum(len(items)>1 for items in byTitle.values()),
        "exportUpdatedAt":ex.get("updatedAt")}
    try:
        backups=fetch("/api/backups")
        summary["latestBackups"]=(backups.get("backups") or [])[:10]
    except Exception as e:
        summary["backupInspectionError"]=str(e)[:200]
    report={"summary":summary,"targetPass":passResults,"songs":songs,
            "warning":"READ ONLY; no live writes performed"}
    (OUTPUT/"LA_PASMA_23_AUDIT.json").write_text(json.dumps(report,indent=2,ensure_ascii=False)+"\n",encoding="utf8")
    rows=["# LA PASMA (NUEVA): auditoría de 23 canciones","",
      f"Cloudflare: {len(arr)} entradas; {len(custom)} personalizadas",
      f"Pase existente: {'Sí' if selected else 'No'}",
      f"Temas disponibles: {summary['expected23Present']}/23",
      f"Temas sin ningún acorde: {summary['expected23ZeroChords']}",
      f"Referencias rotas del pase: {summary['targetPassBrokenIDs']}","",
      "| # | Canción | IDs actuales | Acordes | Líneas con acordes | En pase |",
      "|---:|---|---|---|---|---|"]
    for x in songs:
        vals=x["variants"]
        rows.append(f"| {x['order']} | {x['expectedTitle']} | {', '.join(map(str,x['foundIDs'])) or 'No existe'} | {', '.join(str(v['chords']) for v in vals) or '—'} | {', '.join(str(v['coveragePct'])+'%' for v in vals) or '—'} | {'Sí' if x['inPass'] else 'No'} |")
    (OUTPUT/"LA_PASMA_23_AUDIT.md").write_text("\n".join(rows)+"\n",encoding="utf8")
    print("LA_PASMA_SUMMARY="+json.dumps(summary,ensure_ascii=False),flush=True)
    print("LA_PASMA_SONGS="+json.dumps(songs,ensure_ascii=False),flush=True)
    print("LA_PASMA_PASSES="+json.dumps(passResults,ensure_ascii=False),flush=True)

if __name__=="__main__":main()
