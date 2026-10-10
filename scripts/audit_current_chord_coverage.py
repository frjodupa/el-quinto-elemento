#!/usr/bin/env python3
"""Read-only line-level EQE chords/lyrics inventory and pass-integrity audit.
Never writes to the live Worker or stores the song lyrics in reports.
"""
import collections
import hashlib
import json
import pathlib
import re
import unicodedata
from scripts import audit_songbook as audit

OUT=pathlib.Path("eqe-current-audit")
OUT.mkdir(exist_ok=True)
PASS_KEY="quintoElemento.passes.v1"

def norm(s):
    s=unicodedata.normalize("NFKD",str(s or ""))
    s="".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"[^A-Z0-9]+"," ",s.upper()).strip()
def parse(value,default):
    try:
        v=json.loads(value) if isinstance(value,str) else value
        return v if isinstance(v,type(default)) else default
    except Exception:return default
def counts(song):
    lyric= song["texto"].splitlines()
    d=audit.normalize_chord_data(song["letraConAcordes"])
    indexed={}
    orphan=[]
    line_parts={}
    for kind in ("words","lines"):
        for k,v in d.get(kind,{}).items():
            if not str(v).strip():continue
            try:
                li=int(str(k).split(":")[0])
            except Exception:
                orphan.append({"section":kind,"index":str(k)})
                continue
            if 0<=li<len(lyric) and lyric[li].strip():
                indexed.setdefault(li,[]).append(v)
            else:orphan.append({"section":kind,"index":str(k)})
    available=[i for i,s in enumerate(lyric) if s.strip()]
    covered=[i for i in available if i in indexed]
    uncovered=[i for i in available if i not in indexed]
    # A chord on an 'Intro' or 'Instrumental' line should not make the verse appear chord-covered.
    musical=[i for i in available if not re.match(r"^(intro|instrumental|solo|coro|chorus|estrofa|verse|verso|puente|final|coda)\b",norm(lyric[i]),re.I)]
    mus_covered=[i for i in musical if i in indexed]
    return {"lyricLines":len(available),"lyricLinesWithChords":len(covered),
       "lyricLinesWithoutChords":len(uncovered),"lyricCoveragePct":round(100*len(covered)/max(1,len(available)),1),
       "estimatedMusicalCoveragePct":round(100*len(mus_covered)/max(1,len(musical)),1),
       "chordsTotal":audit.count_chords(d),"orphanChordAnchors":len(orphan),
       "orphanChordLocations":orphan[:20], "uncoveredLineIndexes":uncovered[:100],
       "hasIntro":bool(d.get("intro") or d.get("introText")),
       "hasInstrumental":bool(d.get("instrumentals") or d.get("instrumentalsText")),
       "hasReferences":bool(d.get("references")), "lyricChars":len(song["texto"])}
def main():
    storage,src=audit.load_remote_storage()
    songs=audit.build_songbook(storage)
    passes=parse(storage.get(PASS_KEY,"[]"),[])
    stats=[]
    for song in songs:
        record={"id":int(song["id"]),"title":song["titulo"],"artist":song["artista"],**counts(song)}
        record["priority"] = ("SIN_LETRA" if not song["texto"].strip()
            else "SIN_ACORDES" if not record["chordsTotal"]
            else "COBERTURA_MUY_BAJA" if record["estimatedMusicalCoveragePct"]<25
            else "ACORDES_PARCIALES" if record["estimatedMusicalCoveragePct"]<70
            else "REVISAR_FUENTE")
        stats.append(record)
    bytitle=collections.defaultdict(list)
    for r in stats:bytitle[norm(r["title"])].append(r["id"])
    groups=[{"title":stats[x[0]]["title"],"ids":x} for x in bytitle.values() if len(x)>1]
    broken=[]
    passdetails=[]
    for p in passes:
        ids=p.get("songs",[])
        bad=[i for i in ids if not isinstance(i,int) or isinstance(i,bool) or i<0 or i>=len(songs)]
        broken.extend(bad)
        passdetails.append({"name":p.get("name"),"songCount":len(ids),"invalidIDs":bad,"songIDs":ids})
    summary={"songCount":len(songs),"distinctTitles":len(bytitle),"duplicateTitleGroups":len(groups),
       "songsWithoutLyrics":sum(x["priority"]=="SIN_LETRA" for x in stats),
       "songsWithoutChords":sum(x["priority"]=="SIN_ACORDES" for x in stats),
       "songsUnder25PctCoverage":sum(x["estimatedMusicalCoveragePct"]<25 for x in stats),
       "songsUnder70PctCoverage":sum(x["estimatedMusicalCoveragePct"]<70 for x in stats),
       "songsWithOrphanChordAnchors":sum(x["orphanChordAnchors"]>0 for x in stats),
       "passCount":len(passes),"invalidPassReferences":len(broken),
       "pasmaExists":any(norm(x.get("name"))==norm("LA PASMA (NUEVA)") for x in passes),
       "pasmaSongCount":next((len(x.get("songs",[])) for x in passes if norm(x.get("name"))==norm("LA PASMA (NUEVA)")),0),
       "remoteLastModified":src.get("payload",{}).get("updatedAt"),
       "readOnly":True}
    report={"summary":summary,"songs":stats,"duplicates":groups,"passes":passdetails}
    (OUT/"LINE_COVERAGE_FULL.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    content=["# Auditoría de las canciones y acordes actuales (solo lectura)","",f"**{summary['songCount']} entradas** y {summary['distinctTitles']} títulos distintos. Pase La Pasma: {summary['pasmaSongCount']} canciones.","",
      "## Resumen"]+[f"- {k}: **{v}**" for k,v in summary.items()]+["",
      "| ID | Título | Acordes | Líneas | Cobertura | Problema prioritario |",
      "|---:|---|---:|---:|---:|---|"]
    for s in stats:
        content.append(f"| {s['id']} | {s['title'].replace('|','/')} | {s['chordsTotal']} | {s['lyricLines']} | {s['estimatedMusicalCoveragePct']:.1f}% | {s['priority']} |")
    content+=["","## Títulos duplicados"]+[f"- {s['title']}: IDs {', '.join(map(str,s['ids']))}" for s in groups]
    content+=["","## Integridad de los pases"]+[f"- {p['name']}: {p['songCount']} canciones, {len(p['invalidIDs'])} referencias rotas" for p in passdetails]
    (OUT/"AUDITORIA_COBERTURA.md").write_text("\n".join(content)+"\n",encoding="utf-8")
    print("EQE_LIVE_SUMMARY="+json.dumps(summary,ensure_ascii=False),flush=True)
    print("EQE_PRIORITY_CASES="+json.dumps([x for x in stats if x['priority']!='REVISAR_FUENTE'],ensure_ascii=False),flush=True)
    if not 75<=len(songs)<=100:
        raise RuntimeError(f"Censo no esperado: {len(songs)}; revisar antes de actuar")
    if broken:
        raise RuntimeError("Hay índices de canción rotos en los pases. No se han modificado.")
if __name__=="__main__":main()
