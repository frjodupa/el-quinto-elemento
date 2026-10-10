#!/usr/bin/env python3
"""Full, current, metadata-only audit of the 23-song LA PASMA (NUEVA) pass.
No D1 writes; does not export copyrighted song lyrics.
Detects missing chord coverage, orphan indices, exact lyric repetitions, safe
copy-only chord placement opportunities, duplicate setlist titles and bad refs.
"""
import collections
import copy
import json
import re
import unicodedata
from pathlib import Path
import audit_songbook as a
from audit_current_chord_coverage import counts,parse,norm

OUT=Path("pasma-deep-audit")
OUT.mkdir(parents=True,exist_ok=True)
NAME="LA PASMA (NUEVA)"
PASS_KEY="quintoElemento.passes.v1"

def normalize_line(line):
    t="".join(c for c in unicodedata.normalize("NFKD",str(line or "")) if not unicodedata.combining(c))
    return re.sub(r"\s+"," ",re.sub(r"[^a-zA-Z0-9ñÑ]+"," ",t)).casefold().strip()

def is_section(text):
    return bool(re.match(r"^(intro|verso|estrofa|coro|chorus|estribillo|instrumental|solo|puente|bridge|final|outro|riff)\b",normalize_line(text),re.I))

def chords_on_line(d,li):
    words={}
    for key,value in d["words"].items():
        try:
            ln,wi=map(int,key.split(":"))
            if ln==li and str(value).strip():words[wi]=value
        except Exception:continue
    return words

def repetition_proposals(text,d):
    lines=text.splitlines()
    groups=collections.defaultdict(list)
    for i,line in enumerate(lines):
        normed=normalize_line(line)
        if len(normed)<12 or is_section(normed):continue
        groups[normed].append(i)
    proposals={}
    conflict=[]
    for literal,indices in groups.items():
        if len(indices)<2:continue
        scored=[(idx,chords_on_line(d,idx)) for idx in indices]
        sources=[(idx,c) for idx,c in scored if c]
        blanks=[idx for idx,c in scored if not c and str(d["lines"].get(str(idx),"")).strip()==""]
        if not sources or not blanks:continue
        unique={}
        for source,cs in sources:
            frozen=tuple(sorted((int(w),str(v)) for w,v in cs.items()))
            unique.setdefault(frozen,[]).append(source)
        if len(unique)>1:
            conflict.append({"indices":indices,"reason":"conflicting_chord_versions"})
            continue
        positions=next(iter(unique))
        for idx in blanks:
            target_word_count=len(lines[idx].split())
            if not all(0<=wi<target_word_count for wi,_ in positions):
                conflict.append({"indices":indices,"reason":"different_word_positions"})
                continue
            proposals[idx]={"sourceLine":sources[0][0],"newWords":{str(wi):v for wi,v in positions}}
    return proposals,conflict

def main():
    storage,meta=a.load_remote_storage()
    songs=a.build_songbook(storage)
    passes=parse(storage.get(PASS_KEY,"[]"),[])
    matching=[p for p in passes if norm(p.get("name"))==norm(NAME)]
    if len(matching)!=1:raise RuntimeError("El pase LA PASMA (NUEVA) no es único/no existe; no hacer cambios")
    ids=matching[0].get("songs",[])
    if len(ids)!=23:raise RuntimeError("El pase tiene "+str(len(ids))+" entradas, esperaba 23")
    if len(set(ids))!=23:raise RuntimeError("El pase repite identificadores: comprobar antes de actuar")
    bad=[x for x in ids if isinstance(x,bool) or not isinstance(x,int) or x<0 or x>=len(songs)]
    if bad:raise RuntimeError("Índices de pase inexistentes: "+str(bad))
    allrows=[]
    for position,idx in enumerate(ids,1):
        s=songs[idx]
        m=counts(s)
        d=a.normalize_chord_data(s["letraConAcordes"])
        prop,conf=repetition_proposals(s["texto"],d)
        zero=m["chordsTotal"]==0
        missing=m["lyricLinesWithoutChords"]
        coverage=m["estimatedMusicalCoveragePct"]
        classification=("SIN_ACORDES" if zero else "MUY_INCOMPLETA" if coverage<25 else "PARCIAL" if coverage<70 else "REVISAR_ALINEACION")
        row={"position":position,"id":idx,"title":s["titulo"],"artist":s["artista"],
          "chordCount":m["chordsTotal"],"lyricLines":m["lyricLines"],
          "linesWithChords":m["lyricLinesWithChords"],
          "linesWithoutChords":missing,"coveragePct":coverage,
          "orphanAnchors":m["orphanChordAnchors"],
          "repeatLinesWithIdenticalKnownChords":len(prop),
          "repeatSafeNewAnchors":sum(len(x["newWords"]) for x in prop.values()),
          "repeatConflicts":len(conf),
          "missingArtist":not bool(s["artista"]),
          "priority":classification}
        allrows.append(row)
    summary={"currentInventory":len(songs),"pasmaLength":23,
      "distinctPassSongs":len(set(ids)),
      "withoutChords":sum(r["chordCount"]==0 for r in allrows),
      "veryLowCoverage":sum(r["coveragePct"]<25 for r in allrows),
      "under70Coverage":sum(r["coveragePct"]<70 for r in allrows),
      "lyricLinesMissingChords":sum(r["linesWithoutChords"] for r in allrows),
      "knownChordSymbols":sum(r["chordCount"] for r in allrows),
      "orphanChordAnchors":sum(r["orphanAnchors"] for r in allrows),
      "missingArtistFields":sum(r["missingArtist"] for r in allrows),
      "exactRepeatLineCandidates":sum(r["repeatLinesWithIdenticalKnownChords"] for r in allrows),
      "repeatNewWordAnchors":sum(r["repeatSafeNewAnchors"] for r in allrows),
      "repeatConflicts":sum(r["repeatConflicts"] for r in allrows),
      "readOnly":True}
    result={"summary":summary,"songs":allrows}
    (OUT/"LA_PASMA_DEEP_AUDIT.json").write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    report=["# Auditoría profunda — LA PASMA (NUEVA)","",
      "Solo lectura: no se han modificado acordes, letras ni pases.","",
      f"Inventario activo: {len(songs)} canciones. Pase: 23 entradas.","",
      "## Resumen"]+[f"- **{key}:** {val}" for key,val in summary.items()]+["",
      "| Nº | ID | Canción | Acordes | Líneas sin acordes | Cobertura | Copias exactas posibles | Diagnóstico |",
      "|---:|---:|---|---:|---:|---:|---:|---|"]
    for row in allrows:
        report.append(f"| {row['position']} | {row['id']} | {row['title'].replace('|','/')} | {row['chordCount']} | {row['linesWithoutChords']} | {row['coveragePct']}% | {row['repeatSafeNewAnchors']} | {row['priority']} |")
    report+=["","### Reglas de seguridad",
      "La cobertura no demuestra que todas las líneas necesiten un cambio armónico. Solo señala las que no tienen posiciones de acordes.",
      "Una copia de acordes de una estrofa a otra solo es candidata si el texto normalizado coincide exactamente y ningún acorde existente difiere.",
      "No se importan letras completas de terceros. Contrastar título, artista, orden de estrofas, acordes y tonalidad antes de aplicar fuentes externas.",
      "No aplicar ni borrar canciones con esta ejecución: es solo el inventario de prioridades.",
      ""]
    (OUT/"LA_PASMA_DEEP_AUDIT.md").write_text("\n".join(report),encoding="utf-8")
    print("PASMA_DEEP_SUMMARY="+json.dumps(summary,ensure_ascii=False),flush=True)
    for row in allrows:
        print("PASMA_SONG="+json.dumps(row,ensure_ascii=False),flush=True)
    print("PASMA_DEEP_AUDIT_COMPLETE=YES",flush=True)

if __name__=="__main__":main()
