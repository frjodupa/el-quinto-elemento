const BASE = "https://www.cifraclub.com.br";
const SEARCH_ENDPOINT = "https://solr.sscdn.co/cc/c7/";
const USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36";

function clean(value) {
  return String(value || "").replace(/\s+/g, " ").trim();
}

function decodeEntities(value) {
  return String(value || "")
    .replace(/&nbsp;/gi, " ")
    .replace(/&amp;/gi, "&")
    .replace(/&quot;/gi, '"')
    .replace(/&#39;|&apos;/gi, "'")
    .replace(/&lt;/gi, "<")
    .replace(/&gt;/gi, ">")
    .replace(/&#(\d+);/g, (_, n) => String.fromCodePoint(Number(n)))
    .replace(/&#x([0-9a-f]+);/gi, (_, n) => String.fromCodePoint(parseInt(n, 16)));
}

function textFromHtml(value) {
  return decodeEntities(
    String(value || "")
      .replace(/<br\s*\/?>/gi, "\n")
      .replace(/<\/(?:p|div|li|section|article|h[1-6])>/gi, "\n")
      .replace(/<[^>]+>/g, "")
  )
    .replace(/\r/g, "")
    .replace(/[\t\f\v]/g, " ")
    .replace(/\n{3,}/g, "\n\n")
    .trim();
}

function tagText(html, pattern) {
  const match = String(html || "").match(pattern);
  return match ? clean(textFromHtml(match[1])) : "";
}

async function fetchWithTimeout(url, options = {}, timeoutMs = 10000) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    return await fetch(url, { ...options, signal: controller.signal });
  } finally {
    clearTimeout(timer);
  }
}

export async function searchCifraClub(query, limit = 8) {
  const q = clean(query);
  if (q.length < 2) return [];

  const safeLimit = Math.max(1, Math.min(12, Number(limit) || 8));
  const url = new URL(SEARCH_ENDPOINT);
  url.searchParams.set("q", q);
  url.searchParams.set("limit", String(Math.max(safeLimit * 3, 18)));

  const response = await fetchWithTimeout(url.toString(), {
    headers: {
      "user-agent": USER_AGENT,
      "accept": "application/json,text/plain,*/*",
      "accept-language": "es-ES,es;q=0.9,pt-BR;q=0.8,en;q=0.7"
    }
  });

  if (!response.ok) {
    throw new Error("Cifra Club search returned " + response.status);
  }

  const data = await response.json();
  const docs = Array.isArray(data?.response?.docs) ? data.response.docs : [];
  const results = [];
  const seen = new Set();

  for (const doc of docs) {
    if (String(doc?.tipo ?? "") !== "2") continue;
    const title = clean(doc?.txt);
    const artist = clean(doc?.art);
    const artistSlug = clean(doc?.dns);
    const songSlug = clean(doc?.url);
    if (!title || !artist || !artistSlug || !songSlug) continue;

    const sourceUrl = BASE + "/" + artistSlug.replace(/^\/+|\/+$/g, "") + "/" + songSlug.replace(/^\/+|\/+$/g, "") + "/";
    const key = (artist + "::" + title).toLowerCase();
    if (seen.has(key)) continue;
    seen.add(key);

    results.push({
      title,
      artist,
      url: sourceUrl,
      source: "Cifra Club"
    });

    if (results.length >= safeLimit) break;
  }

  return results;
}

function validateCifraUrl(value) {
  const url = new URL(String(value || ""));
  const host = url.hostname.toLowerCase();
  if (url.protocol !== "https:" || (host !== "www.cifraclub.com.br" && host !== "cifraclub.com.br")) {
    throw new Error("Fuente no permitida");
  }
  return url;
}

export async function fetchCifraClubSong(value) {
  const url = validateCifraUrl(value);

  const response = await fetchWithTimeout(url.toString(), {
    redirect: "follow",
    headers: {
      "user-agent": USER_AGENT,
      "accept": "text/html,application/xhtml+xml",
      "accept-language": "es-ES,es;q=0.9,pt-BR;q=0.8,en;q=0.7"
    }
  });

  if (!response.ok) {
    throw new Error("Cifra Club returned " + response.status);
  }

  const html = await response.text();
  if (!html || html.length < 200) throw new Error("Respuesta vacía");

  const preMatches = [...html.matchAll(/<pre\b[^>]*>([\s\S]*?)<\/pre>/gi)]
    .map((m) => ({ html: m[1], text: textFromHtml(m[1]) }))
    .filter((x) => x.text.length > 20)
    .sort((a, b) => b.text.length - a.text.length);

  if (!preMatches.length) {
    throw new Error("No se encontró una cifra legible");
  }

  const title =
    tagText(html, /<h1\b[^>]*class=["'][^"']*\bt1\b[^"']*["'][^>]*>([\s\S]*?)<\/h1>/i) ||
    tagText(html, /<meta\b[^>]*property=["']og:title["'][^>]*content=["']([^"']+)["'][^>]*>/i);

  const artist =
    tagText(html, /<h2\b[^>]*class=["'][^"']*\bt3\b[^"']*["'][^>]*>([\s\S]*?)<\/h2>/i);

  const key =
    tagText(html, /id=["']cifra_tom["'][^>]*>[\s\S]*?<a\b[^>]*>([\s\S]*?)<\/a>/i);

  return {
    title,
    artist,
    key,
    transcription: preMatches[0].text,
    source: "Cifra Club",
    sourceUrl: response.url || url.toString()
  };
}
