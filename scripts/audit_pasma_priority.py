#!/usr/bin/env python3
"""Read-only LA PASMA (NUEVA) coverage and structural audit. No lyrics exported."""
import json
import unicodedata
from pathlib import Path
import audit_songbook as a
import audit_current_chord_coverage as coverage

OUT=Path("eqe-priority-latest")
OUT.mkdir(exist_ok=True)
PASS_KEY="quintoElemento.passes.v1"
EXPECTED_PASS_NAME="LA PASMA (NUEVA)"

def plain(s):
    return "".join(ch for ch in unicodedata.normalize("NFKD", str(s or "")).casefold() if not unicodedata.combining(ch)).strip()

def main():
    storage,src=a.load_remote_storage()
    songs=a.build_songbook(storage)
    passes=coverage.parse(storage.get(PASS_KEY,"[]"),[])
    pass_items=[p for p in passes if plain(p.get("name"))==plain(EXPECTED_PASS_NAME)]
    if len(pass_items)!=1:
        raise RuntimeError("LA PASMA (NUEVA) is missing or ambiguous. Read-only audit aborted.")
    entries=pass_items[0].get("songs",[])
    if not isinstance(entries,list) or len(entries)!=23:
        raise RuntimeError("LA PASMA (NUEVA) has unexpectedly changed size")
    if not 80<=len(songs)<=120:
        raise RuntimeError("Unexpected inventory size")
    rows=[]
    for order,i in enumerate(entries,1):
        if isinstance(i,bool) or not isinstance(i,int) or not 0<=i<len(songs):
            raise RuntimeError(f"Invalid pass index {i}")
        s=songs[i]; metrics=coverage.counts(s)
        rows.append({"order":order,"id":i,"title":s["titulo"],
                     "lyricLines":metrics["lyricLines"],
                     "linesWithChords":metrics["lyricLinesWithChords"],
                     "linesWithoutChords":metrics["lyricLinesWithoutChords"],
                     "coveragePct":metrics["estimatedMusicalCoveragePct"],
                     "totalChordSymbols":metrics["chordsTotal"],
                     "orphanChordAnchors":metrics["orphanChordAnchors"],
                     "priority":"CRITICA" if metrics["estimatedMusicalCoveragePct"]<25
                        else "ALTA" if metrics["estimatedMusicalCoveragePct"]<70
                        else "REVISION"})
    summary={"total":len(songs),"uniqueTitles":len(set(plain(s["titulo"]) for s in songs)),
        "passLength":len(rows),"passDistinctSongIds":len(set(x["id"] for x in rows)),
        "passZeroChords":sum(not x["totalChordSymbols"] for x in rows),
        "passUnder25Pct":sum(x["coveragePct"]<25 for x in rows),
        "passUnder70Pct":sum(x["coveragePct"]<70 for x in rows),
        "passOrphanAnchors":sum(x["orphanChordAnchors"] for x in rows),
        "otherPassCount":len(passes)-1,"liveUpdatedAt":src.get("payload",{}).get("updatedAt")}
    data={"readOnly":True,"summary":summary,"songs":rows}
    (OUT/"LA_PASMA_23_CURRENT.json").write_text(json.dumps(data,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    markdown=["# LA PASMA (NUEVA): auditoría de acordes del pase",
    "",f"Estado: {summary['total']} canciones en cancionero, {summary['passLength']} en el pase.",
    f"Canciones con cobertura inferior al 70%: **{summary['passUnder70Pct']}**.",
    "", "| # | ID | Título | Líneas con acordes | Total | Cobertura | Prioridad |",
    "|---:|---:|---|---:|---:|---:|---|"]
    for s in rows:
        markdown.append(f"| {s['order']} | {s['id']} | {s['title'].replace('|','/')} | {s['linesWithChords']} | {s['lyricLines']} | {s['coveragePct']}% | {s['priority']} |")
    (OUT/"LA_PASMA_23_CURRENT.md").write_text("\n".join(markdown)+"\n",encoding="utf-8")
    print("LA_PASMA_NOW="+json.dumps(summary,ensure_ascii=False),flush=True)
    print("LA_PASMA_LOW_COVERAGE="+json.dumps([r for r in rows if r["priority"]!="REVISION"],ensure_ascii=False),flush=True)

if __name__=="__main__":
    main()
