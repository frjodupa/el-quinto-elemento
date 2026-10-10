#!/usr/bin/env python3
import json, re, time, difflib, os
from pathlib import Path
import requests

BASE=os.environ.get("LIVE_BASE","https://crimson-rice-1fe1.joseduqueparedes.workers.dev").rstrip("/")
TARGETS=[x.strip() for x in os.environ.get("TARGET_TITLES","CORAZÓN DE NEÓN|DEPENDE|ECHO DE MENOS|EL BLUES DEL AUTOBÚS|LA NEGRA FLOR").split("|") if x.strip()]
DELAY=float(os.environ.get("REQUEST_DELAY","2"))
OUT=Path(os.environ.get("OUT_DIR","repair_output"))
OUT.mkdir(parents=True,exist_ok=True)

def norm(s):
    s=str(s or "")
    try:
        import unicodedata
        s="".join(c for c in unicodedata.normalize("NFD",s) if unicodedata.category(c)!="Mn")
    except Exception:
        pass
    return re.sub(r"[^A-Z0-9Ñ]+"," ",s.upper()).strip()

def title_sim(a,b):
    return difflib.SequenceMatcher(None,norm(a),norm(b)).ratio()

def words(s):
    return [x for x in norm(s).lower().split() if x]

def bigrams(s):
    w=words(s)
    return w if len(w)<2 else [w[i]+" "+w[i+1] for i in range(len(w)-1)]

def lyric_sim(a,b):
    aa,bb=bigrams(a),bigrams(b)
    if not aa or not bb:return 0.0
    ca={}
    for x in aa: ca[x]=ca.get(x,0)+1
    inter=0
    for x in bb:
        if ca.get(x,0)>0:
            inter+=1; ca[x]-=1
    dice=2*inter/(len(aa)+len(bb))
    coverage=inter/max(1,min(len(aa),len(bb)))
    seq=difflib.SequenceMatcher(None," ".join(words(a))," ".join(words(b))).ratio()
    return max(dice,coverage,seq)

def count_lines(t):
    return len([x for x in str(t or "").splitlines() if x.strip()])

def count_chords(d):
    d=d or {}
    n=len([1 for v in (d.get("words") or {}).values() if v])
    for v in (d.get("lines") or {}).values():
        if v:n+=max(1,len([x for x in re.split(r"\s*·\s*|\s*,\s*",str(v)) if x]))
    if d.get("intro"): n+=max(1,len([x for x in re.split(r"\s*·\s*|\s*,\s*",str(d["intro"])) if x]))
    for v in (d.get("instrumentals") or {}).values():
        if v:n+=max(1,len([x for x in re.split(r"\s*·\s*|\s*,\s*",str(v)) if x]))
    return n

def empty_data():
    return {"lines":{},"words":{},"intro":"","introText":"","instrumentals":{},"instrumentalsText":{},"references":[]}

def normalize_data(d):
    x=json.loads(json.dumps(d or empty_data()))
    for k in ("lines","words","instrumentals","instrumentalsText"):
        if not isinstance(x.get(k),dict):x[k]={}
    if not isinstance(x.get("references"),list):x["references"]=[]
    x["intro"]=str(x.get("intro") or "")
    x["introText"]=str(x.get("introText") or "")
    return x

def norm_line(s):
    return " ".join(words(s))

def migrate_data(old_text,new_text,data):
    data=normalize_data(data)
    old_lines=str(old_text or "").splitlines()
    new_lines=str(new_text or "").splitlines()
    out=empty_data()
    out["intro"]=data["intro"];out["introText"]=data["introText"]
    out["instrumentals"]=json.loads(json.dumps(data["instrumentals"]))
    out["instrumentalsText"]=json.loads(json.dumps(data["instrumentalsText"]))
    out["references"]=json.loads(json.dumps(data["references"]))
    used=set()
    for ni,nl in enumerate(new_lines):
        target=norm_line(nl); oi=-1
        if target:
            for j,ol in enumerate(old_lines):
                if j not in used and norm_line(ol)==target:
                    oi=j;break
        if oi<0 and ni<len(old_lines) and ni not in used: oi=ni
        if oi<0: continue
        used.add(oi)
        if str(oi) in data["lines"]:out["lines"][str(ni)]=data["lines"][str(oi)]
        oldw=words(old_lines[oi]); neww=words(nl); taken=set()
        for nwi,nw in enumerate(neww):
            found=-1
            for owi,ow in enumerate(oldw):
                if owi not in taken and ow==nw:
                    found=owi;break
            if found<0 and nwi<len(oldw) and nwi not in taken:found=nwi
            if found>=0:
                taken.add(found)
                ok=f"{oi}:{found}"; nk=f"{ni}:{nwi}"
                if ok in data["words"]:out["words"][nk]=data["words"][ok]
    return out

def merge_data(base,incoming):
    out=normalize_data(base); inc=normalize_data(incoming)
    for k in ("lines","words"):
        for key,val in inc[k].items():
            if val and not out[k].get(key): out[k][key]=val
    if not out["intro"] and inc["intro"]:out["intro"]=inc["intro"]
    if not out["introText"] and inc["introText"]:out["introText"]=inc["introText"]
    for k in ("instrumentals","instrumentalsText"):
        for key,val in inc[k].items():
            if val and not out[k].get(key):out[k][key]=val
    return out

def extract_songs(html):
    marker="let songs="
    p=html.index(marker)+len(marker)
    while html[p].isspace():p+=1
    start=p; depth=0; quote=None; esc=False
    for i in range(start,len(html)):
        ch=html[i]
        if quote:
            if esc:esc=False
            elif ch=="\\":esc=True
            elif ch==quote:quote=None
            continue
        if ch in ('"',"'"):quote=ch
        elif ch=="[":depth+=1
        elif ch=="]":
            depth-=1
            if depth==0:return json.loads(html[start:i+1])
    raise RuntimeError("songs array not found")

def get_json(url,**kw):
    r=requests.get(url,timeout=40,**kw);r.raise_for_status();return r.json()

def post_json(url,payload):
    r=requests.post(url,json=payload,timeout=60);r.raise_for_status();return r.json()

def put_json(url,payload):
    r=requests.put(url,json=payload,timeout=60);r.raise_for_status();return r.json()

html=Path("public/index.html").read_text(encoding="utf-8")
base_songs=extract_songs(html)
sync=get_json(BASE+"/api/sync?ts="+str(int(time.time()*1000)))
storage=sync.get("data") or {}
custom=[]
try: custom=json.loads(storage.get("quintoElemento.customSongs.v1","[]"))
except Exception: custom=[]
if not isinstance(custom,list):custom=[]
songs=list(base_songs)+[x for x in custom if isinstance(x,dict)]

def song_title(i,s):return str(storage.get(f"quintoElemento.title.v1.{i}",s.get("title","")) or "")
def song_text(i,s):return str(storage.get(f"quintoElemento.lyrics.v1.{i}",s.get("text","")) or "")
def song_artist(i,s):return str(storage.get(f"quintoElemento.artist.v1.{i}",s.get("artist") or s.get("artista") or "") or "")
def chord_data(i):
    try:return normalize_data(json.loads(storage.get(f"quintoElemento.chords.v2.{i}","{}")))
    except Exception:return empty_data()

wanted={norm(x) for x in TARGETS}
audit_all=("*" in TARGETS) or not TARGETS
rows=[]; changed=[]
for i,s in enumerate(songs):
    title=song_title(i,s)
    if not audit_all and norm(title) not in wanted: continue
    current_text=song_text(i,s); current_data=chord_data(i)
    before_lines=count_lines(current_text); before_chords=count_chords(current_data)
    q=(song_artist(i,s)+" "+title).strip()
    time.sleep(DELAY)
    search=get_json(BASE+"/api/song-search",params={"q":q,"ts":int(time.time()*1000)})
    results=search.get("results") or []
    scored=sorted(results,key=lambda r:(title_sim(title,r.get("title","")),float(r.get("rating") or 0),int(r.get("votes") or 0)),reverse=True)
    best=None
    for cand in scored[:3]:
        if title_sim(title,cand.get("title",""))<0.60: continue
        time.sleep(DELAY)
        try:
            fetched=post_json(BASE+"/api/song-fetch",{"source":cand.get("source"),"id":cand.get("id"),"url":cand.get("url")})
            src=fetched.get("song") or {}
            sim=lyric_sim(current_text,src.get("text",""))
            item=(sim,title_sim(title,src.get("title","")),src,cand)
            if best is None or item[:2]>best[:2]:best=item
        except Exception:
            continue
    if not best:
        rows.append({"id":i,"title":title,"action":"sin_fuente","similarity":0,"before_lines":before_lines,"after_lines":before_lines,"before_chords":before_chords,"after_chords":before_chords,"source":""})
        continue
    sim,tsim,src,cand=best
    source_text=str(src.get("text") or "")
    source_data=normalize_data(src.get("chordData") or {})
    source_lines=count_lines(source_text); source_chords=count_chords(source_data)
    action="revision_manual"
    after_lines=before_lines; after_chords=before_chords
    if sim>=0.85:
        replace_lyrics=source_lines>before_lines+2 or len(source_text)>len(current_text)*1.08
        target_text=source_text if replace_lyrics else current_text
        existing_migrated=migrate_data(current_text,target_text,current_data) if replace_lyrics else current_data
        source_mapped=source_data if replace_lyrics else migrate_data(source_text,target_text,source_data)
        merged=merge_data(existing_migrated,source_mapped)
        after_chords=count_chords(merged)
        after_lines=count_lines(target_text)
        if after_chords>before_chords or after_lines>before_lines:
            backup={"id":i,"title":title,"text":current_text,"chordData":current_data}
            (OUT/f"{i}_backup.json").write_text(json.dumps(backup,ensure_ascii=False,indent=2),encoding="utf-8")
            if replace_lyrics: storage[f"quintoElemento.lyrics.v1.{i}"]=target_text
            storage[f"quintoElemento.chords.v2.{i}"]=json.dumps(merged,ensure_ascii=False,separators=(",",":"))
            if src.get("artist"):storage[f"quintoElemento.artist.v1.{i}"]=str(src.get("artist"))
            changed.append(i); action="reparada"
        else:
            action="sin_mejora"
    rows.append({"id":i,"title":title,"action":action,"similarity":round(sim,4),"before_lines":before_lines,"after_lines":after_lines,"before_chords":before_chords,"after_chords":after_chords,"source":src.get("url",""),"provider":src.get("source",""),"source_lines":source_lines,"source_chords":source_chords})

if changed:
    backup=post_json(BASE+"/api/backups",{"action":"create"})
    result=put_json(BASE+"/api/sync",{"data":storage})
    status={"changed":changed,"cloudBackupId":backup.get("id"),"updatedAt":result.get("updatedAt")}
else:
    status={"changed":[]}

(OUT/"TARGETED_REPAIR_REPORT.json").write_text(json.dumps({"status":status,"rows":rows},ensure_ascii=False,indent=2),encoding="utf-8")
md=["# Reparación dirigida v70","","| ID | Canción | Coincidencia | Líneas | Acordes | Fuente | Acción |","|---:|---|---:|---:|---:|---|---|"]
for r in rows:
    md.append(f"| {r['id']} | {r['title']} | {r['similarity']*100:.1f}% | {r['before_lines']}→{r['after_lines']} | {r['before_chords']}→{r['after_chords']} | {r.get('provider') or '—'} | {r['action']} |")
(OUT/"TARGETED_REPAIR_REPORT.md").write_text("\n".join(md)+"\n",encoding="utf-8")
print(json.dumps({"status":status,"rows":rows},ensure_ascii=False))
