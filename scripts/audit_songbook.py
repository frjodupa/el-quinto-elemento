#!/usr/bin/env python3
import copy
import difflib
import hashlib
import importlib.util
import json
import os
import re
import subprocess
import sys
import time
import unicodedata
from pathlib import Path
from urllib.parse import quote, urljoin

import requests
from bs4 import BeautifulSoup

LIVE_BASE = os.environ.get("LIVE_BASE", "https://crimson-rice-1fe1.joseduqueparedes.workers.dev").rstrip("/")
OUT = Path(os.environ.get("AUDIT_OUT", "audit_output"))
RAW_DIR = OUT / "raw"
BACKUP_DIR = OUT / "backup"
DIFF_DIR = OUT / "diff"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
HEADERS = {"User-Agent": UA, "Accept-Language": "es-ES,es;q=0.9,en;q=0.7"}
SETLIVE_PATH = os.environ.get("SETLIVE_SCRAPER_PATH", "/tmp/setlive/backend/apps/repertoire/cifra_scraper.py")
UG_HELPER = os.environ.get("UG_HELPER", "/tmp/ug-audit")
CHORDPRO_CONVERTER = os.environ.get("CHORDPRO_CONVERTER", "scripts/chordpro_convert.cjs")
REQUEST_DELAY = float(os.environ.get("REQUEST_DELAY", "2.0"))
APPLY_TO_LIVE = os.environ.get("APPLY_TO_LIVE", "1") == "1"

ROOT_RE = re.compile(r"^(?:[A-G](?:#|b)?|DO(?:#|b)?|RE(?:#|b)?|MI(?:#|b)?|FA(?:#|b)?|SOL(?:#|b)?|LA(?:#|b)?|SI(?:#|b)?)(?:m|maj|min|dim|aug|sus|add|M)?(?:2|4|5|6|7|9|11|13|maj7|m7|7sus4|add9|M7)*(?:/[A-G](?:#|b)?)?$", re.I)
SECTIONS_RE = re.compile(r"^(intro|verse|verso|estrofa|chorus|coro|estribillo|bridge|puente|solo|instrumental|final|coda|pre[- ]?(?:chorus|coro|estribillo))\b", re.I)
SPANISH_ROOTS = {"DO":"C","RE":"D","MI":"E","FA":"F","SOL":"G","LA":"A","SI":"B"}
CHROMATIC = ["C","C#","D","D#","E","F","F#","G","G#","A","A#","B"]
ENHARMONIC = {"Db":"C#","Eb":"D#","Gb":"F#","Ab":"G#","Bb":"A#"}

class RateLimiter:
    def __init__(self, delay):
        self.delay = delay
        self.last = 0.0
    def wait(self):
        delta = time.monotonic() - self.last
        if delta < self.delay:
            time.sleep(self.delay - delta)
        self.last = time.monotonic()

limiter = RateLimiter(REQUEST_DELAY)

def mkdirs():
    for p in (OUT, RAW_DIR, BACKUP_DIR, DIFF_DIR):
        p.mkdir(parents=True, exist_ok=True)

def jdump(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")

def safe_json(value, default):
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(value)
    except Exception:
        return copy.deepcopy(default)

def deaccent(s):
    return "".join(c for c in unicodedata.normalize("NFD", str(s or "")) if unicodedata.category(c) != "Mn")

def slugify(s):
    s = deaccent(s).lower().replace("&", " y ")
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s

def split_chords(s):
    if not s:
        return []
    parts = re.split(r"\s*(?:·|,|\||\s+-\s+)\s*|\s+", str(s).strip())
    return [p for p in parts if p and is_chord(p)]

def is_chord(token):
    t = str(token or "").strip().strip("()[]{}.,;:")
    return bool(ROOT_RE.match(t))

def chord_line(line):
    s = str(line or "").strip()
    if not s:
        return False
    if re.match(r"^[eBGDAE]\|[-0-9hpsbrx()/\\~.]+", s, re.I):
        return True
    if re.match(r"^[x0-9]{4,8}(?:\s+O\s+[x0-9]{4,8})?$", s, re.I):
        return True
    tokens = [x.strip("()[]{}.,;:") for x in re.split(r"\s+", s.replace("·"," ")) if x.strip()]
    if not tokens:
        return False
    good = sum(1 for x in tokens if is_chord(x))
    return good >= 1 and good / max(1, len(tokens)) >= 0.65

def clean_source_content(text):
    out = []
    for line in str(text or "").replace("\r\n","\n").replace("\r","\n").split("\n"):
        if re.match(r"^\s*[eBGDAE]\|[-0-9hpsbrx()/\\~.]+", line, re.I):
            continue
        if re.match(r"^\s*(?:e|B|G|D|A|E)\s*[-:|].*$", line, re.I):
            continue
        if re.match(r"^\s*[x0-9]{4,8}\s*$", line, re.I):
            continue
        out.append(line.rstrip())
    return "\n".join(out)

def normalized_lyrics(text):
    lines = []
    for line in str(text or "").replace("\r\n","\n").replace("\r","\n").split("\n"):
        s = line.strip()
        if not s:
            continue
        if chord_line(s):
            continue
        if SECTIONS_RE.match(deaccent(s)):
            continue
        if re.fullmatch(r"[A-G]{6}", s, re.I):
            continue
        s = deaccent(s).lower()
        s = re.sub(r"[^a-z0-9ñ]+", " ", s)
        s = re.sub(r"\s+", " ", s).strip()
        if s:
            lines.append(s)
    return "\n".join(lines)

def similarity(a, b):
    aa, bb = normalized_lyrics(a), normalized_lyrics(b)
    if not aa or not bb:
        return 0.0
    return difflib.SequenceMatcher(None, aa, bb).ratio()

def empty_chords():
    return {"lines":{}, "words":{}, "intro":"", "introText":"", "instrumentals":{}, "instrumentalsText":{}, "references":[]}

def normalize_chord_data(d):
    x = copy.deepcopy(d) if isinstance(d, dict) else empty_chords()
    for k in ("lines","words","instrumentals","instrumentalsText"):
        if not isinstance(x.get(k), dict):
            x[k] = {}
    if not isinstance(x.get("references"), list):
        x["references"] = []
    x["intro"] = str(x.get("intro") or "")
    x["introText"] = str(x.get("introText") or "")
    return x

def count_chords(d):
    d = normalize_chord_data(d)
    n = 0
    for v in d["words"].values():
        n += max(1, len(split_chords(v))) if str(v).strip() else 0
    for v in d["lines"].values():
        n += len(split_chords(v))
    n += len(split_chords(d["intro"]))
    for v in d["instrumentals"].values():
        n += len(split_chords(v))
    return n

def extract_json_array_after(text, marker):
    pos = text.index(marker) + len(marker)
    while pos < len(text) and text[pos].isspace():
        pos += 1
    if text[pos] != "[":
        raise ValueError("No array after marker")
    start = pos
    depth = 0
    quote_char = None
    esc = False
    for i in range(start, len(text)):
        ch = text[i]
        if quote_char:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == quote_char:
                quote_char = None
            continue
        if ch in ('"', "'"):
            quote_char = ch
        elif ch == "[":
            depth += 1
        elif ch == "]":
            depth -= 1
            if depth == 0:
                return json.loads(text[start:i+1])
    raise ValueError("Unclosed songs array")

def load_setlive():
    spec = importlib.util.spec_from_file_location("setlive_cifra_scraper", SETLIVE_PATH)
    if not spec or not spec.loader:
        raise RuntimeError("No se pudo cargar cifra_scraper.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

SETLIVE = None

def live_get_json(path):
    r = requests.get(LIVE_BASE + path, headers=HEADERS, timeout=30)
    r.raise_for_status()
    return r.json()

def load_remote_storage():
    errors = []
    try:
        payload = live_get_json("/export?ts=" + str(int(time.time()*1000)))
        storage = payload.get("storage")
        if isinstance(storage, dict):
            return storage, {"endpoint":"/export", "payload":payload}
    except Exception as e:
        errors.append("/export: " + str(e))
    try:
        payload = live_get_json("/api/sync?ts=" + str(int(time.time()*1000)))
        storage = payload.get("data")
        if isinstance(storage, dict):
            return storage, {"endpoint":"/api/sync", "payload":payload, "fallbackErrors":errors}
    except Exception as e:
        errors.append("/api/sync: " + str(e))
    raise RuntimeError("No se pudo exportar el estado vivo: " + " | ".join(errors))

def build_songbook(storage):
    html = Path("public/index.html").read_text(encoding="utf-8")
    base = extract_json_array_after(html, "let songs=")
    custom = safe_json(storage.get("quintoElemento.customSongs.v1", "[]"), [])
    if not isinstance(custom, list):
        custom = []
    all_songs = list(base) + [x for x in custom if isinstance(x, dict)]
    result = []
    for i, s in enumerate(all_songs):
        title = str(storage.get(f"quintoElemento.title.v1.{i}", s.get("title","")) or "").strip()
        text = str(storage.get(f"quintoElemento.lyrics.v1.{i}", s.get("text","")) or "")
        data = normalize_chord_data(safe_json(storage.get(f"quintoElemento.chords.v2.{i}", "{}"), empty_chords()))
        artist = str(s.get("artista") or s.get("artist") or "").strip()
        result.append({"id":str(i), "titulo":title, "artista":artist, "texto":text, "letraConAcordes":data})
    return result

def search_cifraclub(title, artist=""):
    q = (artist + " " + title).strip()
    limiter.wait()
    r = requests.get("https://www.cifraclub.com/busca/?q=" + quote(q), headers=HEADERS, timeout=20)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    bad = {"busca","explorar","listas","artistas","login","usuario","academy"}
    for a in soup.find_all("a", href=True):
        href = a.get("href","")
        m = re.match(r"^/([^/?#]+)/([^/?#]+)/?$", href)
        if not m or m.group(1).lower() in bad:
            continue
        return urljoin("https://www.cifraclub.com", href)
    return None

def cifra_fetch_text(url):
    global SETLIVE
    if SETLIVE is None:
        SETLIVE = load_setlive()
    limiter.wait()
    return SETLIVE.fetch_cifra_text(url)

def convert_to_chordpro(content, title, artist):
    env = dict(os.environ)
    p = subprocess.run(
        ["node", CHORDPRO_CONVERTER],
        input=json.dumps({"content":content, "title":title, "artist":artist}, ensure_ascii=False),
        text=True, capture_output=True, env=env, timeout=30
    )
    if p.returncode != 0:
        raise RuntimeError(p.stderr.strip() or "ChordPro converter failed")
    return p.stdout

def chordpro_to_model(chordpro):
    lyric_lines = []
    placements = []
    intro = []
    section = ""
    for raw in str(chordpro or "").splitlines():
        line = raw.rstrip()
        dm = re.match(r"^\{([^:}]+):?\s*([^}]*)\}$", line.strip())
        if dm:
            section = (dm.group(2) or dm.group(1) or "").strip().lower()
            continue
        if not line.strip():
            continue
        # Convert [C]lyric into a lyric line plus chord anchors.
        out = ""
        anchors = []
        pos = 0
        for m in re.finditer(r"\[([^\]]+)\]", line):
            out += line[pos:m.start()]
            c = m.group(1).strip()
            if is_chord(c):
                anchors.append((len(out), c))
            pos = m.end()
        out += line[pos:]
        lyric = re.sub(r"\s+", " ", out).strip()
        if not lyric:
            if "intro" in section:
                intro.extend(c for _, c in anchors)
            continue
        if SECTIONS_RE.match(deaccent(lyric)):
            section = deaccent(lyric).lower()
            continue
        li = len(lyric_lines)
        lyric_lines.append(lyric)
        starts = [m.start() for m in re.finditer(r"\S+", lyric)]
        for charpos, chord in anchors:
            if starts:
                wi = min(range(len(starts)), key=lambda j: abs(starts[j]-charpos))
                placements.append({"line":li, "word":wi, "chord":chord})
    return {"lyrics":"\n".join(lyric_lines), "lines":lyric_lines, "placements":placements, "intro":intro}

def ug_run(args):
    p = subprocess.run([UG_HELPER] + args, text=True, capture_output=True, timeout=35)
    if p.returncode != 0:
        raise RuntimeError(p.stderr.strip() or "UG helper failed")
    return json.loads(p.stdout)

def score_ug(tab, title, artist):
    st = difflib.SequenceMatcher(None, deaccent(str(tab.get("song_name",""))).lower(), deaccent(title).lower()).ratio()
    sa = 0.0
    if artist:
        sa = difflib.SequenceMatcher(None, deaccent(str(tab.get("artist_name",""))).lower(), deaccent(artist).lower()).ratio()
    rating = float(tab.get("rating") or 0)
    votes = min(float(tab.get("votes") or 0), 10000.0) / 10000.0
    return st*5 + sa*2 + rating/5 + votes

def ug_fetch(title, artist=""):
    limiter.wait()
    result = ug_run(["-mode","search","-query", (artist+" "+title).strip()])
    tabs = result.get("tabs") or []
    if not tabs and artist:
        limiter.wait()
        result = ug_run(["-mode","search","-query", title])
        tabs = result.get("tabs") or []
    if not tabs:
        return None
    tab = max(tabs, key=lambda x: score_ug(x, title, artist))
    tab_id = int(tab.get("id") or 0)
    if not tab_id:
        return None
    limiter.wait()
    full = ug_run(["-mode","fetch","-id",str(tab_id)])
    content = str(full.get("content") or "")
    if not content:
        return None
    return {
        "content":content,
        "title":str(full.get("song_name") or tab.get("song_name") or title),
        "artist":str(full.get("artist_name") or tab.get("artist_name") or artist),
        "key":str(full.get("tonality_name") or ""),
        "url":str(full.get("urlWeb") or f"https://tabs.ultimate-guitar.com/tab/{tab_id}"),
        "id":tab_id
    }

def ug_to_model(content):
    text = str(content or "").replace("[tab]","").replace("[/tab]","")
    lyric_lines, placements = [], []
    pending_anchors = []

    for raw in text.splitlines():
        line = raw.rstrip()
        if not line.strip():
            pending_anchors = []
            continue
        if re.fullmatch(r"\s*\[[^\]]+\]\s*", line) and "[ch]" not in line:
            continue

        out = ""
        anchors = []
        pos = 0
        for m in re.finditer(r"\[ch\](.*?)\[/ch\]", line, flags=re.I):
            out += line[pos:m.start()]
            chord = m.group(1).strip()
            if is_chord(chord):
                anchors.append((len(out), chord))
            pos = m.end()
        out += line[pos:]
        out = re.sub(r"\[/?(?:tab|ch)\]", "", out, flags=re.I)
        lyric = re.sub(r"\s+", " ", out).strip()

        # UG often stores chords on a separate line immediately above lyrics.
        if anchors and (not lyric or chord_line(lyric)):
            pending_anchors = anchors
            continue
        if not lyric or SECTIONS_RE.match(deaccent(lyric)):
            continue

        li = len(lyric_lines)
        lyric_lines.append(lyric)
        starts = [m.start() for m in re.finditer(r"\S+", lyric)]
        use_anchors = anchors if anchors else pending_anchors
        pending_anchors = []

        if starts and use_anchors:
            if anchors:
                for charpos, chord in use_anchors:
                    wi = min(range(len(starts)), key=lambda j: abs(starts[j]-charpos))
                    placements.append({"line":li, "word":wi, "chord":chord})
            else:
                # Chord-only rows retain approximate horizontal positions.
                maxpos = max((p for p,_ in use_anchors), default=0)
                for charpos, chord in use_anchors:
                    if maxpos <= 0 or len(starts) == 1:
                        wi = 0
                    else:
                        wi = round((charpos / maxpos) * (len(starts)-1))
                    placements.append({"line":li, "word":max(0,min(wi,len(starts)-1)), "chord":chord})

    return {"lyrics":"\n".join(lyric_lines), "lines":lyric_lines, "placements":placements, "intro":[]}

def try_cifra_direct(song, artist_hint, errors):
    title = song["titulo"]
    if not artist_hint:
        return None
    for host in ("www.cifraclub.com", "www.cifraclub.com.br"):
        base_url = f"https://{host}/{slugify(artist_hint)}/{slugify(title)}/"
        try:
            print_url = base_url.rstrip("/") + "/imprimir.html"
            raw = clean_source_content(cifra_fetch_text(print_url))
            if not raw.strip():
                raw = clean_source_content(cifra_fetch_text(base_url))
            if not raw.strip():
                continue
            chordpro = convert_to_chordpro(raw, title, artist_hint)
            model = chordpro_to_model(chordpro)
            if model["lyrics"]:
                return {
                    "provider":"CifraClub",
                    "url":base_url,
                    "key":"",
                    "title":title,
                    "artist":artist_hint,
                    "model":model,
                    "content_hash":hashlib.sha256(raw.encode("utf-8")).hexdigest(),
                    "content_chars":len(raw),
                    "errors":errors,
                }
        except Exception as e:
            errors.append(f"Cifra direct {host}: " + str(e))
    return None

def try_source(song):
    title = song["titulo"]
    artist = song.get("artista","")
    errors = []

    # 1) Mandatory direct CifraClub slug first whenever an artist is known.
    if artist:
        direct = try_cifra_direct(song, artist, errors)
        if direct:
            return direct

    # 2) Capo search architecture when we cannot form a reliable slug.
    if not artist:
        try:
            found = search_cifraclub(title, "")
            if found:
                try:
                    print_url = found.rstrip("/") + "/imprimir.html"
                    raw = clean_source_content(cifra_fetch_text(print_url))
                    if not raw.strip():
                        raw = clean_source_content(cifra_fetch_text(found))
                    if raw.strip():
                        parts = [x for x in found.strip("/").split("/") if x]
                        src_artist = parts[-2].replace("-"," ").title() if len(parts)>=2 else ""
                        chordpro = convert_to_chordpro(raw, title, src_artist)
                        model = chordpro_to_model(chordpro)
                        if model["lyrics"]:
                            return {
                                "provider":"CifraClub",
                                "url":found,
                                "key":"",
                                "title":title,
                                "artist":src_artist,
                                "model":model,
                                "content_hash":hashlib.sha256(raw.encode("utf-8")).hexdigest(),
                                "content_chars":len(raw),
                                "errors":errors,
                            }
                except Exception as e:
                    errors.append("Cifra result fetch: " + str(e))
        except Exception as e:
            errors.append("Cifra search: " + str(e))

    # 3) Ultimate Guitar fallback using Pilfer's real API package.
    # For missing artists, UG metadata is used only to build a Cifra direct slug;
    # Cifra is accepted only when its lyrics agree strongly with the current song.
    try:
        ug = ug_fetch(title, artist)
        if ug:
            ug_model = ug_to_model(ug["content"])
            inferred_artist = artist or ug.get("artist","")
            ug_sim = similarity(song["texto"], ug_model["lyrics"]) if ug_model["lyrics"] else 0.0

            if not artist and inferred_artist and ug_sim >= 0.85:
                direct = try_cifra_direct(song, inferred_artist, errors)
                if direct:
                    cifra_sim = similarity(song["texto"], direct["model"]["lyrics"])
                    if cifra_sim >= 0.85 and cifra_sim >= ug_sim - 0.03:
                        direct["key"] = ug.get("key","")
                        direct["errors"] = errors + ["Artist inferred from UG metadata; Cifra direct source independently lyric-validated."]
                        return direct

            if ug_model["lyrics"]:
                return {
                    "provider":"Ultimate Guitar",
                    "url":ug["url"],
                    "key":ug["key"],
                    "title":ug["title"],
                    "artist":ug["artist"],
                    "model":ug_model,
                    "content_hash":hashlib.sha256(ug["content"].encode("utf-8")).hexdigest(),
                    "content_chars":len(ug["content"]),
                    "errors":errors,
                }
    except Exception as e:
        errors.append("UG: " + str(e))

    return {"provider":"", "url":"", "key":"", "title":title, "artist":artist, "model":None, "content_hash":"", "content_chars":0, "errors":errors}

def align_lines(source_lines, current_text):
    current_lines = str(current_text or "").splitlines()
    norm_current = [normalized_lyrics(x).replace("\n"," ") for x in current_lines]
    mapping = {}
    used = set()
    for si, sline in enumerate(source_lines):
        sn = normalized_lyrics(sline).replace("\n"," ")
        if not sn:
            continue
        best = (-1, 0.0)
        for ci, cn in enumerate(norm_current):
            if ci in used or not cn:
                continue
            sc = difflib.SequenceMatcher(None, sn, cn).ratio()
            if sc > best[1]:
                best = (ci, sc)
        if best[0] >= 0 and best[1] >= 0.58:
            mapping[si] = best[0]
            used.add(best[0])
    return mapping, current_lines

def map_placements(model, current_text):
    line_map, current_lines = align_lines(model["lines"], current_text)
    mapped = []
    for p in model["placements"]:
        si = int(p["line"])
        if si not in line_map:
            continue
        ci = line_map[si]
        sw = re.findall(r"\S+", model["lines"][si])
        cw = re.findall(r"\S+", current_lines[ci])
        if not cw:
            continue
        wi = int(p["word"])
        if len(sw) <= 1 or len(cw) <= 1:
            target = min(wi, len(cw)-1)
        else:
            target = round(wi * (len(cw)-1) / (len(sw)-1))
        mapped.append({"line":ci, "word":max(0,min(target,len(cw)-1)), "chord":p["chord"]})
    coverage = len(mapped) / max(1, len(model["placements"]))
    return mapped, coverage

def chord_root(ch):
    s = str(ch or "").strip()
    s = re.split(r"[·,\s]", s)[0]
    m = re.match(r"^(DO|RE|MI|FA|SOL|LA|SI|[A-G])([#b]?)(.*)$", s, re.I)
    if not m:
        return None
    root = m.group(1).upper()
    root = SPANISH_ROOTS.get(root, root)
    note = root + m.group(2)
    return ENHARMONIC.get(note, note)

def transpose_chord(ch, shift):
    if shift % 12 == 0:
        return ch
    m = re.match(r"^(DO|RE|MI|FA|SOL|LA|SI|[A-G])([#b]?)(.*)$", str(ch or "").strip(), re.I)
    if not m:
        return ch
    root = SPANISH_ROOTS.get(m.group(1).upper(), m.group(1).upper()) + m.group(2)
    root = ENHARMONIC.get(root, root)
    if root not in CHROMATIC:
        return ch
    nr = CHROMATIC[(CHROMATIC.index(root)+shift)%12]
    suffix = m.group(3)
    # transpose slash bass when present
    sm = re.search(r"/([A-G])([#b]?)", suffix, re.I)
    if sm:
        bass = ENHARMONIC.get(sm.group(1).upper()+sm.group(2), sm.group(1).upper()+sm.group(2))
        if bass in CHROMATIC:
            nb = CHROMATIC[(CHROMATIC.index(bass)+shift)%12]
            suffix = suffix[:sm.start()] + "/" + nb + suffix[sm.end():]
    return nr + suffix

def choose_shift(mapped, current_words):
    pairs = []
    for p in mapped:
        key = f"{p['line']}:{p['word']}"
        cur = str(current_words.get(key) or "").strip()
        if cur:
            sr, cr = chord_root(p["chord"]), chord_root(cur)
            if sr and cr:
                pairs.append((sr,cr))
    if len(pairs) < 2:
        return 0, 0.0
    best_shift, best_score = 0, -1
    for sh in range(12):
        score = 0
        for sr, cr in pairs:
            shifted = CHROMATIC[(CHROMATIC.index(sr)+sh)%12] if sr in CHROMATIC else sr
            if shifted == cr:
                score += 1
        if score > best_score:
            best_shift, best_score = sh, score
    return best_shift, best_score / len(pairs)

def apply_mapped_chords(current, mapped, shift):
    new = normalize_chord_data(current)
    words = dict(new["words"])
    additions = conflicts = 0
    for p in mapped:
        key = f"{p['line']}:{p['word']}"
        chord = transpose_chord(p["chord"], shift)
        existing = str(words.get(key) or "").strip()
        if not existing:
            words[key] = chord
            additions += 1
        elif chord_root(existing) != chord_root(chord):
            conflicts += 1
    new["words"] = words
    return new, additions, conflicts

def source_chord_count(model):
    return len(model.get("placements") or []) + len(model.get("intro") or [])

def md_escape(s):
    return str(s or "").replace("|","\\|").replace("\n"," ")

def make_diff(song, sim, before, after, source, action, coverage, additions, conflicts, shift, shift_conf):
    return f"""# {song['titulo']}

- ID: {song['id']}
- Artista: {source.get('artist') or song.get('artista') or '—'}
- Fuente: {source.get('provider') or '—'}
- URL: {source.get('url') or '—'}
- Similitud de letra: {sim*100:.1f}%
- Acordes antes: {before}
- Acordes después: {after}
- Cobertura de mapeo: {coverage*100:.1f}%
- Acordes añadidos: {additions}
- Conflictos conservados sin sobrescribir: {conflicts}
- Transposición aplicada: {shift:+d} semitonos (confianza {shift_conf*100:.1f}%)
- Acción: **{action}**

La letra existente del cancionero se conserva. La fuente externa se usa únicamente para validación y colocación de acordes; Intro, Instrumental y referencias existentes no se eliminan.
"""

def main():
    mkdirs()
    storage, remote_info = load_remote_storage()
    songs = build_songbook(storage)

    export_payload = {
        "format":"quinto-elemento-v62-export",
        "version":63,
        "technicalVersion":66,
        "createdAt":time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "source":LIVE_BASE + remote_info["endpoint"],
        "cancionero":[
            {"id":s["id"],"titulo":s["titulo"],"artista":s["artista"],"letraConAcordes":{"texto":s["texto"], **s["letraConAcordes"]}}
            for s in songs
        ],
        "storage":storage
    }
    jdump(OUT/"cancionero-v62-export.json", export_payload)

    rows = []
    source_urls = []
    changed = 0
    corrected = []

    for idx, song in enumerate(songs, start=1):
        sid = song["id"]
        print(f"[{idx}/{len(songs)}] {song['titulo']}", flush=True)
        current = normalize_chord_data(song["letraConAcordes"])
        before = count_chords(current)
        source = try_source(song)
        model = source.get("model")
        sim = similarity(song["texto"], model["lyrics"]) if model else 0.0
        src_count = source_chord_count(model) if model else 0
        mapped, coverage = map_placements(model, song["texto"]) if model else ([],0.0)
        shift, shift_conf = choose_shift(mapped, current["words"]) if mapped else (0,0.0)
        candidate, additions, conflicts = apply_mapped_chords(current, mapped, shift) if mapped else (current,0,0)
        after_candidate = count_chords(candidate)

        if not model:
            action = "fuente_no_encontrada"
            final = current
        elif sim < 0.70:
            action = "revision_manual"
            final = current
        elif sim <= 0.85:
            action = "revision_manual"
            final = current
        elif src_count < before:
            action = "sin_cambios_fuente_con_menos_acordes"
            final = current
        elif coverage < 0.60:
            action = "revision_manual_mapeo_insuficiente"
            final = current
        elif additions > 0 and after_candidate >= before:
            action = "acordes_enriquecidos"
            jdump(BACKUP_DIR/f"{sid}_v62.json", {
                "id":sid,"titulo":song["titulo"],"artista":song["artista"],
                "texto":song["texto"],"letraConAcordes":current
            })
            final = candidate
            storage[f"quintoElemento.chords.v2.{sid}"] = json.dumps(final, ensure_ascii=False, separators=(",",":"))
            changed += 1
        else:
            action = "sin_cambios"
            final = current

        artist = song["artista"] or source.get("artist") or ""
        corrected.append({
            "id":sid,
            "titulo":song["titulo"],
            "artista":artist,
            "letraConAcordes":{"texto":song["texto"], **final}
        })
        after = count_chords(final)

        raw_meta = {
            "id":sid,
            "titulo":song["titulo"],
            "artista":artist,
            "provider":source.get("provider",""),
            "source_url":source.get("url",""),
            "key":source.get("key",""),
            "source_content_sha256":source.get("content_hash",""),
            "source_content_chars":source.get("content_chars",0),
            "source_chord_count":src_count,
            "source_lyric_similarity":round(sim,6),
            "errors":source.get("errors",[])
        }
        jdump(RAW_DIR/f"{sid}.json", raw_meta)
        (DIFF_DIR/f"{sid}.md").write_text(
            make_diff(song,sim,before,after,source,action,coverage,additions,conflicts,shift,shift_conf),
            encoding="utf-8"
        )
        if source.get("url"):
            source_urls.append(source["url"])
        rows.append({
            "id":sid,"title":song["titulo"],"artist":artist,"similarity":sim,
            "before":before,"after":after,"source":source.get("provider",""),
            "url":source.get("url",""),"action":action
        })

    inventory = {
        "format":"quinto-elemento-audited",
        "version":64,
        "technicalVersion":66,
        "createdAt":time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "changedSongs":changed,
        "cancionero":corrected,
        "storage":storage
    }
    jdump(OUT/"inventario_v64_corregido.json", inventory)
    jdump(OUT/"workers-sync-v64.json", {"data":storage})
    (OUT/"SOURCE_URLS.txt").write_text("\n".join(dict.fromkeys(source_urls))+"\n", encoding="utf-8")

    report = [
        "# AUDITORÍA CANCIONERO EL QUINTO ELEMENTO — v63 → inventario v64",
        "",
        f"- Canciones auditadas: **{len(rows)}**",
        f"- Canciones con acordes enriquecidos: **{changed}**",
        "- Versión técnica PWA conservada: **66**",
        "- Política: similitud <70% = revisión manual; >85% + igual/mayor cobertura de acordes + mapeo suficiente = candidato.",
        "- Las letras externas no se guardan ni se publican; la letra existente del cancionero se conserva.",
        "",
        "| Canción | Similitud | Acordes antes/después | Fuente | Acción |",
        "|---|---:|---:|---|---|",
    ]
    for r in rows:
        src = f"[{r['source']}]({r['url']})" if r["url"] else "—"
        report.append(f"| {md_escape(r['title'])} | {r['similarity']*100:.1f}% | {r['before']} → {r['after']} | {src} | {r['action']} |")
    (OUT/"AUDITORIA_REPORT.md").write_text("\n".join(report)+"\n", encoding="utf-8")

    live_status = {"attempted":False,"backup":None,"sync":None}
    if APPLY_TO_LIVE and changed > 0:
        live_status["attempted"] = True
        try:
            b = requests.post(LIVE_BASE+"/api/backups", headers={**HEADERS,"Content-Type":"application/json"},
                              json={"action":"create"}, timeout=30)
            live_status["backup"] = {"status":b.status_code,"body":b.text[:500]}
            b.raise_for_status()
            u = requests.put(LIVE_BASE+"/api/sync", headers={**HEADERS,"Content-Type":"application/json"},
                             json={"data":storage}, timeout=60)
            live_status["sync"] = {"status":u.status_code,"body":u.text[:500]}
            u.raise_for_status()
        except Exception as e:
            live_status["error"] = str(e)

    jdump(OUT/"RUN_STATUS.json", {
        "ok":True,
        "songs":len(rows),
        "changed":changed,
        "remoteEndpoint":remote_info["endpoint"],
        "liveUpdate":live_status
    })
    print(json.dumps({"songs":len(rows),"changed":changed,"live":live_status}, ensure_ascii=False))

if __name__ == "__main__":
    main()


# trigger: autonomous audit v63 second pass (UG chord-row parser + direct Cifra retry)

# optimization: Cifra direct corroboration limited to >=85% UG lyric matches
