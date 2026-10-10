#!/usr/bin/env python3
import copy
import json
import os
import sys
import time
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
import audit_songbook as audit

LIVE_BASE = os.environ.get("LIVE_BASE", audit.LIVE_BASE).rstrip("/")
OUT = Path(os.environ.get("CORRECTION_OUT", "final_correction"))
BACKUP_SOURCE = Path(os.environ.get("RUN3_BACKUP_DIR", "/tmp/run3/backup"))

TARGETS = {
    "4": {
        "title": "ÁNGEL PARA UN FINAL",
        "artist": "Silvio Rodríguez",
        "url": "https://www.cifraclub.com/silvio-rodriguez/angel-para-un-final/pwtpwh.html",
        "reason": "La fuente anterior era Los Bunkers; se exige la grabación original de Silvio Rodríguez.",
    },
    "6": {
        "title": "AUNQUE TU NO LO SEPAS",
        "artist": "Enrique Urquijo y Los Problemas",
        "url": "https://www.cifraclub.com/enrique-urquijo/aunque-tu-no-lo-sepas/tjwsgj.html",
        "reason": "La fuente anterior era Quique González; la primera publicación fue Enrique Urquijo y Los Problemas (1998).",
    },
    "73": {
        "title": "HACE CALOR",
        "artist": "Los Rodríguez",
        "url": "https://www.cifraclub.com/los-rodriguez/hace-calor/",
        "reason": "La fuente anterior era Andrés Calamaro en solitario; se corrige a Los Rodríguez.",
    },
    "87": {
        "title": "HACE CALOR",
        "artist": "Los Rodríguez",
        "url": "https://www.cifraclub.com/los-rodriguez/hace-calor/",
        "reason": "Duplicado sincronizado: se corrige a la fuente original de Los Rodríguez.",
    },
    "78": {
        "title": "LA CHICA DE AYER",
        "artist": "Nacha Pop",
        "url": "https://www.cifraclub.com/nacha-pop/la-chica-de-ayer-solo/",
        "reason": "La fuente anterior era Antonio Vega en solitario; la grabación original es de Nacha Pop.",
    },
    "92": {
        "title": "LA CHICA DE AYER",
        "artist": "Nacha Pop",
        "url": "https://www.cifraclub.com/nacha-pop/la-chica-de-ayer-solo/",
        "reason": "Duplicado sincronizado: se corrige a la fuente original de Nacha Pop.",
    },
}


def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def fetch_exact_cifra(url):
    audit.limiter.wait()
    text = audit.SETLIVE.fetch_cifra_text(url) if audit.SETLIVE else None
    if audit.SETLIVE is None:
        audit.SETLIVE = audit.load_setlive()
        audit.limiter.wait()
        text = audit.SETLIVE.fetch_cifra_text(url)
    raw = audit.clean_source_content(text or "")
    if not raw.strip() and url.endswith("/"):
        audit.limiter.wait()
        raw = audit.clean_source_content(audit.SETLIVE.fetch_cifra_text(url.rstrip("/") + "/imprimir.html"))
    if not raw.strip():
        raise RuntimeError("CifraClub no devolvió contenido utilizable")
    return raw


def load_backup(song_id):
    p = BACKUP_SOURCE / f"{song_id}_v62.json"
    if not p.exists():
        raise FileNotFoundError(f"Falta backup previo {p}")
    return json.loads(p.read_text(encoding="utf-8"))


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    storage, remote_info = audit.load_remote_storage()
    songs = {s["id"]: s for s in audit.build_songbook(storage)}

    rows = []
    changed_ids = []
    restored_ids = []

    for sid, spec in TARGETS.items():
        if sid not in songs:
            rows.append({"id": sid, "title": spec["title"], "action": "missing_live_song", "reason": spec["reason"]})
            continue

        song = songs[sid]
        live_data = audit.normalize_chord_data(song["letraConAcordes"])
        backup = load_backup(sid)
        base_data = audit.normalize_chord_data(backup.get("letraConAcordes"))
        text = str(backup.get("texto") or song["texto"] or "")

        action = "restored_pre_audit"
        detail = ""
        source_meta = {
            "artist": spec["artist"],
            "url": spec["url"],
            "similarity": 0.0,
            "coverage": 0.0,
            "sourceChords": 0,
            "baseChords": audit.count_chords(base_data),
            "finalChords": audit.count_chords(base_data),
            "transpose": 0,
            "transposeConfidence": 0.0,
        }
        final_data = copy.deepcopy(base_data)

        try:
            raw = fetch_exact_cifra(spec["url"])
            chordpro = audit.convert_to_chordpro(raw, spec["title"], spec["artist"])
            model = audit.chordpro_to_model(chordpro)
            sim = audit.similarity(text, model["lyrics"]) if model.get("lyrics") else 0.0
            mapped, coverage = audit.map_placements(model, text) if model.get("lyrics") else ([], 0.0)
            shift, shift_conf = audit.choose_shift(mapped, base_data["words"]) if mapped else (0, 0.0)
            candidate, additions, conflicts = audit.apply_mapped_chords(base_data, mapped, shift) if mapped else (base_data, 0, 0)
            source_count = audit.source_chord_count(model)
            base_count = audit.count_chords(base_data)
            final_count = audit.count_chords(candidate)

            source_meta.update({
                "similarity": round(sim, 6),
                "coverage": round(coverage, 6),
                "sourceChords": source_count,
                "baseChords": base_count,
                "candidateChords": final_count,
                "transpose": shift,
                "transposeConfidence": round(shift_conf, 6),
                "additions": additions,
                "conflictsPreserved": conflicts,
                "sourceSha256": audit.hashlib.sha256(raw.encode("utf-8")).hexdigest(),
            })

            if sim > 0.85 and source_count >= base_count and coverage >= 0.60 and additions > 0 and final_count >= base_count:
                final_data = candidate
                action = "replaced_with_original_source"
                detail = f"Fuente original validada: similitud {sim*100:.1f}%, cobertura {coverage*100:.1f}%."
            else:
                detail = (
                    f"Fuente original no superó todos los filtros: similitud {sim*100:.1f}%, "
                    f"cobertura {coverage*100:.1f}%, acordes fuente/base {source_count}/{base_count}. "
                    "Se restaura el estado anterior a la auditoría."
                )
        except Exception as exc:
            detail = f"No se pudo validar la fuente original ({exc}). Se restaura el estado anterior a la auditoría."

        current_serialized = storage.get(f"quintoElemento.chords.v2.{sid}")
        final_serialized = json.dumps(final_data, ensure_ascii=False, separators=(",", ":"))
        if current_serialized != final_serialized:
            storage[f"quintoElemento.chords.v2.{sid}"] = final_serialized
            changed_ids.append(sid)

        if action == "restored_pre_audit":
            restored_ids.append(sid)

        source_meta["finalChords"] = audit.count_chords(final_data)
        rows.append({
            "id": sid,
            "title": song["titulo"],
            "requiredOriginalArtist": spec["artist"],
            "sourceUrl": spec["url"],
            "action": action,
            "reason": spec["reason"],
            "detail": detail,
            **source_meta,
        })

    live = {"attempted": False}
    if changed_ids:
        live["attempted"] = True
        backup_response = requests.post(
            LIVE_BASE + "/api/backups",
            headers={**audit.HEADERS, "Content-Type": "application/json"},
            json={"action": "create"},
            timeout=30,
        )
        live["backup"] = {"status": backup_response.status_code, "body": backup_response.text[:500]}
        backup_response.raise_for_status()

        sync_response = requests.put(
            LIVE_BASE + "/api/sync",
            headers={**audit.HEADERS, "Content-Type": "application/json"},
            json={"data": storage},
            timeout=60,
        )
        live["sync"] = {"status": sync_response.status_code, "body": sync_response.text[:500]}
        sync_response.raise_for_status()

    final_songs = audit.build_songbook(storage)
    inventory = {
        "format": "quinto-elemento-audited-original-sources",
        "version": 64,
        "technicalVersion": 67,
        "createdAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "correctedIds": changed_ids,
        "restoredIds": restored_ids,
        "cancionero": [
            {
                "id": s["id"],
                "titulo": s["titulo"],
                "artista": s["artista"],
                "letraConAcordes": {"texto": s["texto"], **s["letraConAcordes"]},
            }
            for s in final_songs
        ],
        "storage": storage,
    }
    dump(OUT / "inventario_v64_original_corregido.json", inventory)
    dump(OUT / "workers-sync-v64-original.json", {"data": storage})
    dump(OUT / "RUN_STATUS.json", {
        "ok": True,
        "targets": len(TARGETS),
        "changedIds": changed_ids,
        "restoredIds": restored_ids,
        "remoteEndpoint": remote_info["endpoint"],
        "liveUpdate": live,
    })

    report = [
        "# Corrección final de fuentes originales — Cancionero El Quinto Elemento",
        "",
        f"- Entradas revisadas por fuente no original: **{len(TARGETS)}**",
        f"- Entradas cuyo estado D1 cambió: **{len(changed_ids)}**",
        f"- Entradas restauradas al estado pre-auditoría: **{len(restored_ids)}**",
        "- La letra existente, Intro, Instrumental y referencias se conservan.",
        "",
        "| ID | Canción | Fuente original exigida | Similitud | Cobertura | Acordes base → final | Acción |",
        "|---:|---|---|---:|---:|---:|---|",
    ]
    for row in rows:
        report.append(
            f"| {row['id']} | {row['title']} | [{row['requiredOriginalArtist']}]({row['sourceUrl']}) | "
            f"{float(row.get('similarity',0))*100:.1f}% | {float(row.get('coverage',0))*100:.1f}% | "
            f"{row.get('baseChords',0)} → {row.get('finalChords',0)} | {row['action']} |"
        )
    (OUT / "CORRECCION_ORIGINALES_REPORT.md").write_text("\n".join(report) + "\n", encoding="utf-8")
    print(json.dumps({"changedIds": changed_ids, "restoredIds": restored_ids, "live": live}, ensure_ascii=False))


if __name__ == "__main__":
    main()
