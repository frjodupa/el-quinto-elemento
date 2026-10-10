#!/usr/bin/env python3
import json,re,time,difflib,unicodedata,requests,os
BASE=os.environ.get("LIVE_BASE","https://crimson-rice-1fe1.joseduqueparedes.workers.dev").rstrip("/")
IDX=35
UG_ID=3336638

def norm(s):
    s="".join(c for c in unicodedata.normalize("NFD",str(s or "")) if unicodedata.category(c)!="Mn")
    return re.sub(r"[^A-Z0-9Ñ]+"," ",s.upper()).strip()
def words(s):return [x for x in norm(s).lower().split() if x]
def bigrams(s):
    w=words(s);return w if len(w)<2 else [w[i]+" "+w[i+1] for i in range(len(w)-1)]
def sim(a,b):
    aa,bb=bigrams(a),bigrams(b)
    ca={}
    for x in aa:ca[x]=ca.get(x,0)+1
    inter=0
    for x in bb:
        if ca.get(x,0)>0:inter+=1;ca[x]-=1
    return max((2*inter/max(1,len(aa)+len(bb))),inter/max(1,min(len(aa),len(bb))),difflib.SequenceMatcher(None," ".join(words(a))," ".join(words(b))).ratio())
def empty():return {"lines":{},"words":{},"intro":"","introText":"","instrumentals":{},"instrumentalsText":{},"references":[]}
def nd(d):
    x=json.loads(json.dumps(d or empty()))
    for k in ("lines","words","instrumentals","instrumentalsText"):
        if not isinstance(x.get(k),dict):x[k]={}
    if not isinstance(x.get("references"),list):x["references"]=[]
    x["intro"]=str(x.get("intro") or "");x["introText"]=str(x.get("introText") or "")
    return x
def count(d):
    d=nd(d);n=sum(1 for v in d["words"].values() if v)
    for v in d["lines"].values():
        if v:n+=max(1,len([x for x in re.split(r"\s*·\s*|\s*,\s*",str(v)) if x]))
    if d["intro"]:n+=max(1,len([x for x in d["intro"].split("·") if x.strip()]))
    for v in d["instrumentals"].values():
        if v:n+=max(1,len([x for x in str(v).split("·") if x.strip()]))
    return n
def nl(s):return " ".join(words(s))
def migrate(old_text,new_text,data):
    data=nd(data); old=str(old_text).splitlines(); new=str(new_text).splitlines(); out=empty()
    out["intro"]=data["intro"];out["introText"]=data["introText"];out["instrumentals"]=data["instrumentals"];out["instrumentalsText"]=data["instrumentalsText"];out["references"]=data["references"]
    used=set()
    for ni,line in enumerate(new):
        target=nl(line);oi=-1
        for j,ol in enumerate(old):
            if j not in used and target and nl(ol)==target:oi=j;break
        if oi<0 and ni<len(old) and ni not in used:oi=ni
        if oi<0:continue
        used.add(oi)
        if str(oi) in data["lines"]:out["lines"][str(ni)]=data["lines"][str(oi)]
        ow,nw=words(old[oi]),words(line);taken=set()
        for nwi,w in enumerate(nw):
            found=next((j for j,x in enumerate(ow) if j not in taken and x==w),-1)
            if found<0 and nwi<len(ow) and nwi not in taken:found=nwi
            if found>=0:
                taken.add(found);ok=f"{oi}:{found}";nk=f"{ni}:{nwi}"
                if ok in data["words"]:out["words"][nk]=data["words"][ok]
    return out
def merge(base,inc):
    out=nd(base);inc=nd(inc)
    for k in ("lines","words"):
        for key,val in inc[k].items():
            if val and not out[k].get(key):out[k][key]=val
    if not out["intro"] and inc["intro"]:out["intro"]=inc["intro"]
    for k in ("instrumentals","instrumentalsText"):
        for key,val in inc[k].items():
            if val and not out[k].get(key):out[k][key]=val
    return out

sync=requests.get(BASE+"/api/sync?ts="+str(int(time.time()*1000)),timeout=30).json()
storage=sync.get("data") or {}
text=str(storage.get(f"quintoElemento.lyrics.v1.{IDX}",""))
if not text:
    # base song text is not in D1 when unedited; fetch export UI isn't needed here because
    # this song has current override only if repaired. Abort rather than guessing.
    raise SystemExit("No current lyric override for ID 35; refusing blind repair")
try:cur=nd(json.loads(storage.get(f"quintoElemento.chords.v2.{IDX}","{}")))
except:cur=empty()
r=requests.post(BASE+"/api/song-fetch",json={"source":"ultimate-guitar","id":UG_ID,"url":"https://tabs.ultimate-guitar.com/tab/radio-futura/paseo-con-la-negra-flor-chords-3336638"},timeout=45)
r.raise_for_status();song=(r.json().get("song") or {})
source_text=str(song.get("text") or "");source_data=nd(song.get("chordData") or {})
score=sim(text,source_text)
if score<0.85:raise SystemExit(f"Similarity too low: {score}")
mapped=migrate(source_text,text,source_data)
merged=merge(cur,mapped)
before,after=count(cur),count(merged)
if after<=before:raise SystemExit(f"No chord improvement: {before}->{after}")
backup=requests.post(BASE+"/api/backups",json={"action":"create"},timeout=30);backup.raise_for_status()
storage[f"quintoElemento.chords.v2.{IDX}"]=json.dumps(merged,ensure_ascii=False,separators=(",",":"))
storage[f"quintoElemento.artist.v1.{IDX}"]="Radio Futura"
put=requests.put(BASE+"/api/sync",json={"data":storage},timeout=60);put.raise_for_status()
print(json.dumps({"id":IDX,"title":"LA NEGRA FLOR","similarity":score,"before":before,"after":after,"backupId":backup.json().get("id"),"updatedAt":put.json().get("updatedAt")},ensure_ascii=False))
