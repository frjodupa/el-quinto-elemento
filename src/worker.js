async function ensureSchema(env) {
  await env.DB.prepare(`
    CREATE TABLE IF NOT EXISTS app_state (
      id TEXT PRIMARY KEY,
      data TEXT NOT NULL,
      updated_at INTEGER NOT NULL
    )
  `).run();

  await env.DB.prepare(`
    CREATE TABLE IF NOT EXISTS app_backups (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      data TEXT NOT NULL,
      created_at INTEGER NOT NULL,
      source TEXT NOT NULL DEFAULT 'auto'
    )
  `).run();

  await env.DB.prepare(`
    CREATE INDEX IF NOT EXISTS idx_app_backups_created_at
    ON app_backups(created_at DESC)
  `).run();
}

function withNoStore(response) {
  const headers = new Headers(response.headers);
  headers.set("cache-control", "no-store, no-cache, must-revalidate");
  headers.set("pragma", "no-cache");
  headers.set("expires", "0");
  return new Response(response.body, {
    status: response.status,
    statusText: response.statusText,
    headers
  });
}

function json(data, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: {
      "content-type": "application/json; charset=utf-8",
      "cache-control": "no-store"
    }
  });
}

async function addBackup(env, data, source = "auto") {
  if (!data) return null;

  const latest = await env.DB.prepare(
    "SELECT id, data FROM app_backups ORDER BY created_at DESC, id DESC LIMIT 1"
  ).first();

  if (latest && latest.data === data) {
    return Number(latest.id || 0);
  }

  const createdAt = Date.now();
  const result = await env.DB.prepare(
    "INSERT INTO app_backups (data, created_at, source) VALUES (?, ?, ?)"
  ).bind(data, createdAt, source).run();

  await env.DB.prepare(`
    DELETE FROM app_backups
    WHERE id NOT IN (
      SELECT id FROM app_backups
      ORDER BY created_at DESC, id DESC
      LIMIT 10
    )
  `).run();

  return Number(result?.meta?.last_row_id || 0);
}

async function currentState(env) {
  return await env.DB.prepare(
    "SELECT data, updated_at FROM app_state WHERE id = ?"
  ).bind("main").first();
}


const SONG_SOURCE_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36";

function decodeEntities(value) {
  return String(value || "")
    .replace(/<br\s*\/?>/gi, "\n")
    .replace(/&nbsp;/gi, " ")
    .replace(/&amp;/gi, "&")
    .replace(/&quot;/gi, '"')
    .replace(/&#39;|&apos;/gi, "'")
    .replace(/&lt;/gi, "<")
    .replace(/&gt;/gi, ">")
    .replace(/&#(\d+);/g, (_, n) => String.fromCharCode(Number(n)))
    .replace(/&#x([0-9a-f]+);/gi, (_, n) => String.fromCharCode(parseInt(n, 16)));
}

function stripHtml(value) {
  return decodeEntities(String(value || "")
    .replace(/<script\b[^>]*>[\s\S]*?<\/script>/gi, "")
    .replace(/<style\b[^>]*>[\s\S]*?<\/style>/gi, "")
    .replace(/<[^>]+>/g, ""));
}

function compactText(value) {
  return String(value || "")
    .replace(/\r\n?/g, "\n")
    .replace(/[ \t]+\n/g, "\n")
    .replace(/\n{3,}/g, "\n\n")
    .trim();
}

function slugWords(value) {
  return String(value || "")
    .normalize("NFD").replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .replace(/&/g, " y ")
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
}

function displaySlug(value) {
  return String(value || "").replace(/-/g, " ").replace(/\b\w/g, c => c.toUpperCase());
}

function add32(a, b) {
  return (a + b) & 0xFFFFFFFF;
}
function md5cmn(q, a, b, x, s, t) {
  a = add32(add32(a, q), add32(x, t));
  return add32((a << s) | (a >>> (32 - s)), b);
}
function md5ff(a, b, c, d, x, s, t) { return md5cmn((b & c) | ((~b) & d), a, b, x, s, t); }
function md5gg(a, b, c, d, x, s, t) { return md5cmn((b & d) | (c & (~d)), a, b, x, s, t); }
function md5hh(a, b, c, d, x, s, t) { return md5cmn(b ^ c ^ d, a, b, x, s, t); }
function md5ii(a, b, c, d, x, s, t) { return md5cmn(c ^ (b | (~d)), a, b, x, s, t); }
function md5cycle(x, k) {
  let [a,b,c,d] = x;
  a=md5ff(a,b,c,d,k[0],7,-680876936); d=md5ff(d,a,b,c,k[1],12,-389564586); c=md5ff(c,d,a,b,k[2],17,606105819); b=md5ff(b,c,d,a,k[3],22,-1044525330);
  a=md5ff(a,b,c,d,k[4],7,-176418897); d=md5ff(d,a,b,c,k[5],12,1200080426); c=md5ff(c,d,a,b,k[6],17,-1473231341); b=md5ff(b,c,d,a,k[7],22,-45705983);
  a=md5ff(a,b,c,d,k[8],7,1770035416); d=md5ff(d,a,b,c,k[9],12,-1958414417); c=md5ff(c,d,a,b,k[10],17,-42063); b=md5ff(b,c,d,a,k[11],22,-1990404162);
  a=md5ff(a,b,c,d,k[12],7,1804603682); d=md5ff(d,a,b,c,k[13],12,-40341101); c=md5ff(c,d,a,b,k[14],17,-1502002290); b=md5ff(b,c,d,a,k[15],22,1236535329);

  a=md5gg(a,b,c,d,k[1],5,-165796510); d=md5gg(d,a,b,c,k[6],9,-1069501632); c=md5gg(c,d,a,b,k[11],14,643717713); b=md5gg(b,c,d,a,k[0],20,-373897302);
  a=md5gg(a,b,c,d,k[5],5,-701558691); d=md5gg(d,a,b,c,k[10],9,38016083); c=md5gg(c,d,a,b,k[15],14,-660478335); b=md5gg(b,c,d,a,k[4],20,-405537848);
  a=md5gg(a,b,c,d,k[9],5,568446438); d=md5gg(d,a,b,c,k[14],9,-1019803690); c=md5gg(c,d,a,b,k[3],14,-187363961); b=md5gg(b,c,d,a,k[8],20,1163531501);
  a=md5gg(a,b,c,d,k[13],5,-1444681467); d=md5gg(d,a,b,c,k[2],9,-51403784); c=md5gg(c,d,a,b,k[7],14,1735328473); b=md5gg(b,c,d,a,k[12],20,-1926607734);

  a=md5hh(a,b,c,d,k[5],4,-378558); d=md5hh(d,a,b,c,k[8],11,-2022574463); c=md5hh(c,d,a,b,k[11],16,1839030562); b=md5hh(b,c,d,a,k[14],23,-35309556);
  a=md5hh(a,b,c,d,k[1],4,-1530992060); d=md5hh(d,a,b,c,k[4],11,1272893353); c=md5hh(c,d,a,b,k[7],16,-155497632); b=md5hh(b,c,d,a,k[10],23,-1094730640);
  a=md5hh(a,b,c,d,k[13],4,681279174); d=md5hh(d,a,b,c,k[0],11,-358537222); c=md5hh(c,d,a,b,k[3],16,-722521979); b=md5hh(b,c,d,a,k[6],23,76029189);
  a=md5hh(a,b,c,d,k[9],4,-640364487); d=md5hh(d,a,b,c,k[12],11,-421815835); c=md5hh(c,d,a,b,k[15],16,530742520); b=md5hh(b,c,d,a,k[2],23,-995338651);

  a=md5ii(a,b,c,d,k[0],6,-198630844); d=md5ii(d,a,b,c,k[7],10,1126891415); c=md5ii(c,d,a,b,k[14],15,-1416354905); b=md5ii(b,c,d,a,k[5],21,-57434055);
  a=md5ii(a,b,c,d,k[12],6,1700485571); d=md5ii(d,a,b,c,k[3],10,-1894986606); c=md5ii(c,d,a,b,k[10],15,-1051523); b=md5ii(b,c,d,a,k[1],21,-2054922799);
  a=md5ii(a,b,c,d,k[8],6,1873313359); d=md5ii(d,a,b,c,k[15],10,-30611744); c=md5ii(c,d,a,b,k[6],15,-1560198380); b=md5ii(b,c,d,a,k[13],21,1309151649);
  a=md5ii(a,b,c,d,k[4],6,-145523070); d=md5ii(d,a,b,c,k[11],10,-1120210379); c=md5ii(c,d,a,b,k[2],15,718787259); b=md5ii(b,c,d,a,k[9],21,-343485551);

  x[0]=add32(a,x[0]); x[1]=add32(b,x[1]); x[2]=add32(c,x[2]); x[3]=add32(d,x[3]);
}
function md5blk(s) {
  const out=[];
  for(let i=0;i<64;i+=4) out[i>>2]=s.charCodeAt(i)+(s.charCodeAt(i+1)<<8)+(s.charCodeAt(i+2)<<16)+(s.charCodeAt(i+3)<<24);
  return out;
}
function md5hex(x) {
  const hex="0123456789abcdef";
  return x.map(n => {
    let s="";
    for(let j=0;j<4;j++) s += hex[(n >> (j*8+4)) & 15] + hex[(n >> (j*8)) & 15];
    return s;
  }).join("");
}
function md5(value) {
  let s=String(value || "");
  let n=s.length, state=[1732584193,-271733879,-1732584194,271733878], i;
  for(i=64;i<=n;i+=64) md5cycle(state,md5blk(s.substring(i-64,i)));
  s=s.substring(i-64);
  const tail=new Array(16).fill(0);
  for(i=0;i<s.length;i++) tail[i>>2] |= s.charCodeAt(i) << ((i%4)<<3);
  tail[i>>2] |= 0x80 << ((i%4)<<3);
  if(i>55){ md5cycle(state,tail); tail.fill(0); }
  tail[14]=n*8;
  md5cycle(state,tail);
  return md5hex(state);
}

function randomHex16() {
  const bytes=new Uint8Array(8);
  crypto.getRandomValues(bytes);
  return Array.from(bytes,b=>b.toString(16).padStart(2,"0")).join("");
}

function ugHeaders(deviceId) {
  const now=new Date();
  const date=now.toISOString().slice(0,10);
  const key=md5(deviceId + date + ":" + now.getUTCHours() + "createLog()");
  return {
    "Accept-Charset":"utf-8",
    "Accept":"application/json",
    "User-Agent":"UGT_ANDROID/4.11.1 (Pixel; 8.1.0)",
    "Connection":"close",
    "X-UG-CLIENT-ID":deviceId,
    "X-UG-API-KEY":key
  };
}

async function ugSearch(query) {
  const device=randomHex16();
  const u=new URL("https://api.ultimate-guitar.com/api/v1/tab/search");
  u.searchParams.set("title",query);
  u.searchParams.set("type","300");
  u.searchParams.set("page","1");
  const r=await fetch(u,{headers:ugHeaders(device)});
  if(!r.ok) throw new Error("Ultimate Guitar HTTP "+r.status);
  const d=await r.json();
  return (Array.isArray(d?.tabs)?d.tabs:[]).slice(0,10).map(t=>({
    source:"ultimate-guitar",
    id:Number(t.id||0),
    title:String(t.song_name||""),
    artist:String(t.artist_name||""),
    key:String(t.tonality_name||""),
    rating:Number(t.rating||0),
    votes:Number(t.votes||0),
    url:"https://tabs.ultimate-guitar.com/tab/"+Number(t.id||0)
  }));
}

async function ugFetchTab(id) {
  const device=randomHex16();
  const u=new URL("https://api.ultimate-guitar.com/api/v1/tab/info");
  u.searchParams.set("tab_id",String(id));
  u.searchParams.set("tab_access_type","private");
  const r=await fetch(u,{headers:ugHeaders(device)});
  if(!r.ok) throw new Error("Ultimate Guitar HTTP "+r.status);
  const d=await r.json();
  if(!d || !d.content) throw new Error("Ultimate Guitar no devolvió contenido");
  return {
    source:"ultimate-guitar",
    title:String(d.song_name||""),
    artist:String(d.artist_name||""),
    key:String(d.tonality_name||d?.recording?.tonality_name||""),
    url:String(d.urlWeb||("https://tabs.ultimate-guitar.com/tab/"+id)),
    content:String(d.content||"")
  };
}

async function cifraSearch(query) {
  const u="https://www.cifraclub.com/busca/?q="+encodeURIComponent(query);
  const r=await fetch(u,{headers:{"User-Agent":SONG_SOURCE_UA,"Accept-Language":"es-ES,es;q=0.9,en;q=0.7"}});
  if(!r.ok) throw new Error("CifraClub HTTP "+r.status);
  const html=await r.text();
  const out=[];
  const seen=new Set();
  const re=/href=["'](\/([^"'/?#]+)\/([^"'/?#]+)\/)["'][^>]*>([\s\S]*?)<\/a>/gi;
  const blocked=new Set(["busca","explorar","listas","artistas","login","usuario","academy","noticias"]);
  let m;
  while((m=re.exec(html)) && out.length<10){
    const artistSlug=m[2], songSlug=m[3];
    if(blocked.has(artistSlug.toLowerCase())) continue;
    const href=m[1];
    if(seen.has(href)) continue;
    seen.add(href);
    let label=stripHtml(m[4]).replace(/\s+/g," ").trim();
    out.push({
      source:"cifraclub",
      id:href,
      title:label || displaySlug(songSlug),
      artist:displaySlug(artistSlug),
      key:"",
      rating:0,
      votes:0,
      url:"https://www.cifraclub.com"+href
    });
  }
  return out;
}

function extractCifraContent(html) {
  let m=String(html||"").match(/<pre\b[^>]*>([\s\S]*?)<\/pre>/i);
  if(m) return compactText(stripHtml(m[1]));
  m=String(html||"").match(/<div\b[^>]*class=["'][^"']*\bcifra_cnt\b[^"']*["'][^>]*>([\s\S]*?)<\/div>/i);
  if(m) return compactText(stripHtml(m[1]));
  m=String(html||"").match(/<div\b[^>]*class=["'][^"']*\bcifra\b[^"']*["'][^>]*>([\s\S]*?)<\/div>/i);
  if(m) return compactText(stripHtml(m[1]));
  return "";
}

function cifraTitleArtist(html,url) {
  const titleTag=String(html||"").match(/<title[^>]*>([\s\S]*?)<\/title>/i);
  let title="",artist="";
  if(titleTag){
    const parts=stripHtml(titleTag[1]).split(/\s+-\s+/).map(x=>x.trim()).filter(Boolean);
    if(parts.length>=2){ title=parts[0]; artist=parts[1]; }
  }
  if(!title || !artist){
    try{
      const parts=new URL(url).pathname.split("/").filter(Boolean);
      artist=artist||displaySlug(parts[0]||"");
      title=title||displaySlug(parts[1]||"");
    }catch{}
  }
  return {title,artist};
}

async function cifraFetchSheet(url) {
  let target=String(url||"");
  if(!/^https:\/\/(www\.)?cifraclub\.com\//i.test(target)) throw new Error("URL CifraClub no válida");
  const printUrl=target.replace(/\/?$/,"/")+"imprimir.html";
  let r=await fetch(printUrl,{headers:{"User-Agent":SONG_SOURCE_UA,"Accept-Language":"es-ES,es;q=0.9,en;q=0.7"}});
  let html=r.ok?await r.text():"";
  let content=extractCifraContent(html);
  if(!content){
    r=await fetch(target,{headers:{"User-Agent":SONG_SOURCE_UA,"Accept-Language":"es-ES,es;q=0.9,en;q=0.7"}});
    if(!r.ok) throw new Error("CifraClub HTTP "+r.status);
    html=await r.text();
    content=extractCifraContent(html);
  }
  if(!content) throw new Error("CifraClub no devolvió cifra utilizable");
  const meta=cifraTitleArtist(html,target);
  return {source:"cifraclub",title:meta.title,artist:meta.artist,key:"",url:target,content};
}

const ROOT_MAP={C:"DO",D:"RE",E:"MI",F:"FA",G:"SOL",A:"LA",B:"SI"};

function cleanChordToken(value) {
  return String(value||"").trim().replace(/^[\[(]+|[\])},;:.]+$/g,"");
}

function isChordToken(value) {
  const t=cleanChordToken(value);
  return /^[A-G](?:#|b)?(?:m|maj|min|dim|aug|sus|add|M)?(?:2|4|5|6|7|9|11|13|maj7|m7|7sus4|add9|M7)*(?:\/[A-G](?:#|b)?)?$/i.test(t);
}

function chordToSpanish(value) {
  const t=cleanChordToken(value);
  const m=t.match(/^([A-G])([#b]?)(.*)$/i);
  if(!m) return t;
  let suffix=m[3]||"";
  suffix=suffix.replace(/\/([A-G])([#b]?)/gi,(_,r,a)=>"/"+ROOT_MAP[r.toUpperCase()]+a);
  return ROOT_MAP[m[1].toUpperCase()]+m[2]+suffix;
}

function chordTokensWithColumns(line) {
  const out=[];
  const re=/\S+/g;
  let m;
  while((m=re.exec(String(line||"")))){
    const tok=cleanChordToken(m[0]);
    if(isChordToken(tok)) out.push({column:m.index,chord:chordToSpanish(tok)});
  }
  return out;
}

function looksChordLine(line) {
  const words=String(line||"").trim().split(/\s+/).filter(Boolean);
  if(!words.length) return false;
  const chords=words.filter(isChordToken);
  return chords.length>0 && chords.length/words.length>=0.6;
}

function isTabLine(line) {
  const s=String(line||"").trim();
  return /^[eBGDAE]\s*\|[-0-9hpsbrx()\/\\~.]+/i.test(s) ||
         /^[eBGDAE]\s*[-:|].*[-0-9].*$/i.test(s) ||
         /^[x0-9]{4,8}$/i.test(s);
}

function sectionName(line) {
  const s=String(line||"").trim().replace(/^\[|\]$/g,"").replace(/:$/,"").trim();
  if(/^(intro|verse|verso|estrofa|chorus|coro|estribillo|bridge|puente|solo|instrumental|final|coda|pre[- ]?(?:chorus|coro|estribillo))\b/i.test(s)) return s.toLowerCase();
  return "";
}

function wordStarts(line) {
  const out=[], re=/\S+/g;
  let m; while((m=re.exec(line))) out.push(m.index);
  return out;
}

function nearestWordIndex(line,column) {
  const starts=wordStarts(line);
  if(!starts.length) return -1;
  let best=0,dist=Infinity;
  starts.forEach((p,i)=>{ const d=Math.abs(p-column); if(d<dist){dist=d;best=i;} });
  return best;
}

function parseInlineUg(line) {
  let plain="", anchors=[], pos=0;
  const re=/\[ch\](.*?)\[\/ch\]/gi;
  let m;
  while((m=re.exec(line))){
    plain += line.slice(pos,m.index);
    const chord=cleanChordToken(m[1]);
    if(isChordToken(chord)) anchors.push({column:plain.length,chord:chordToSpanish(chord)});
    pos=re.lastIndex;
  }
  plain += line.slice(pos);
  plain=plain.replace(/\[\/?(?:tab|ch)\]/gi,"").replace(/\[[^\]]+\]/g,"");
  plain=plain.replace(/\s+/g," ").trim();
  return {plain,anchors};
}

function parseSongContent(content,provider) {
  const chordData={lines:{},words:{},intro:"",introText:"",instrumentals:{},instrumentalsText:{},references:[]};
  const lyrics=[];
  let pending=null, section="", introChords=[], instrumentalChords=[];
  const lines=String(content||"").replace(/\r\n?/g,"\n").split("\n");

  function flushPendingAsSection(){
    if(!pending) return;
    const seq=pending.tokens.map(x=>x.chord);
    if(/intro/i.test(section)) introChords.push(...seq);
    else if(/solo|instrumental/i.test(section)) instrumentalChords.push(...seq);
    pending=null;
  }

  for(let raw of lines){
    if(isTabLine(raw)) continue;
    let trimmed=String(raw||"").trim();
    if(!trimmed){
      flushPendingAsSection();
      continue;
    }

    const sec=sectionName(trimmed);
    if(sec){
      flushPendingAsSection();
      section=sec;
      continue;
    }

    if(provider==="ultimate-guitar" && /\[ch\]/i.test(raw)){
      flushPendingAsSection();
      const parsed=parseInlineUg(raw);
      if(!parsed.plain) continue;
      const li=lyrics.length;
      lyrics.push(parsed.plain);
      parsed.anchors.forEach(a=>{
        const wi=nearestWordIndex(parsed.plain,a.column);
        if(wi>=0) chordData.words[li+":"+wi]=a.chord;
      });
      continue;
    }

    if(looksChordLine(trimmed)){
      flushPendingAsSection();
      pending={raw:String(raw),tokens:chordTokensWithColumns(raw)};
      continue;
    }

    let lyric=stripHtml(trimmed)
      .replace(/\[\/?(?:tab|ch)\]/gi,"")
      .replace(/\[[^\]]+\]/g,"")
      .replace(/\s+/g," ")
      .trim();
    if(!lyric || looksChordLine(lyric) || isTabLine(lyric)) continue;

    const li=lyrics.length;
    lyrics.push(lyric);
    if(pending){
      pending.tokens.forEach(a=>{
        const wi=nearestWordIndex(lyric,a.column);
        if(wi>=0) chordData.words[li+":"+wi]=a.chord;
      });
      pending=null;
    }
  }
  flushPendingAsSection();

  if(introChords.length) chordData.intro=Array.from(new Set(introChords)).join(" · ");
  if(instrumentalChords.length) chordData.instrumentals[String(Math.max(0,lyrics.length-1))]=instrumentalChords.join(" · ");

  const text=compactText(lyrics.join("\n"));
  const chordCount=Object.keys(chordData.words).length+
    Object.keys(chordData.lines).length+
    (chordData.intro?chordData.intro.split("·").length:0)+
    Object.values(chordData.instrumentals).reduce((n,v)=>n+String(v||"").split("·").filter(Boolean).length,0);

  return {text,chordData,chordCount,lineCount:lyrics.length};
}

async function searchInternetSongs(query) {
  const tasks=[
    cifraSearch(query).catch(error=>({error:String(error?.message||error),source:"cifraclub"})),
    ugSearch(query).catch(error=>({error:String(error?.message||error),source:"ultimate-guitar"}))
  ];
  const [cifra,ug]=await Promise.all(tasks);
  const results=[];
  const errors=[];
  for(const part of [cifra,ug]){
    if(Array.isArray(part)) results.push(...part);
    else if(part?.error) errors.push({source:part.source,error:part.error});
  }
  const seen=new Set();
  const unique=results.filter(r=>{
    const key=[r.source,String(r.title).toLowerCase(),String(r.artist).toLowerCase(),String(r.id)].join("|");
    if(seen.has(key)) return false;
    seen.add(key); return true;
  });
  unique.sort((a,b)=>{
    if(a.source!==b.source) return a.source==="cifraclub"?-1:1;
    return (Number(b.rating||0)-Number(a.rating||0)) || (Number(b.votes||0)-Number(a.votes||0));
  });
  return {results:unique.slice(0,16),errors};
}

async function fetchInternetSong(source,id,url) {
  let raw;
  if(source==="ultimate-guitar") raw=await ugFetchTab(Number(id));
  else if(source==="cifraclub") raw=await cifraFetchSheet(String(url||id||""));
  else throw new Error("Fuente no válida");
  const parsed=parseSongContent(raw.content,raw.source);
  if(!parsed.text) throw new Error("La fuente no devolvió una letra utilizable");
  return {
    source:raw.source,
    title:raw.title,
    artist:raw.artist,
    key:raw.key,
    url:raw.url,
    text:parsed.text,
    chordData:parsed.chordData,
    chordCount:parsed.chordCount,
    lineCount:parsed.lineCount
  };
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);

    if (url.pathname === "/api/song-search") {
      if (request.method !== "GET") return new Response("Method Not Allowed", { status: 405 });
      const q=String(url.searchParams.get("q")||"").trim();
      if(q.length<2) return json({results:[],errors:[]});
      try{
        const data=await searchInternetSongs(q.slice(0,120));
        return json({ok:true,query:q,...data});
      }catch(error){
        return json({ok:false,error:String(error?.message||error),results:[]},502);
      }
    }

    if (url.pathname === "/api/song-fetch") {
      if (request.method !== "POST") return new Response("Method Not Allowed", { status: 405 });
      let body={};
      try{ body=await request.json(); }catch{ return json({error:"JSON inválido"},400); }
      try{
        const song=await fetchInternetSong(String(body.source||""),body.id,body.url);
        return json({ok:true,song});
      }catch(error){
        return json({ok:false,error:String(error?.message||error)},502);
      }
    }


    if (url.pathname === "/export") {
      if (request.method !== "GET") {
        return new Response("Method Not Allowed", { status: 405 });
      }

      await ensureSchema(env);
      const row = await currentState(env);
      if (!row?.data) {
        return json({ error: "Todavía no hay datos para exportar" }, 404);
      }

      let storage = {};
      try {
        storage = JSON.parse(row.data || "{}");
      } catch {
        storage = { raw: String(row.data || "") };
      }

      const payload = {
        format: "quinto-elemento-cloud-export",
        version: 69,
        buildVersion: 73,
        createdAt: new Date().toISOString(),
        updatedAt: Number(row.updated_at || 0),
        storage
      };

      return new Response(JSON.stringify(payload, null, 2), {
        status: 200,
        headers: {
          "content-type": "application/json; charset=utf-8",
          "content-disposition": 'attachment; filename="cancionero-v62-export.json"',
          "cache-control": "no-store, no-cache, must-revalidate",
          "pragma": "no-cache",
          "expires": "0"
        }
      });
    }

    if (url.pathname === "/api/health") {
      try {
        await ensureSchema(env);
        return json({ ok: true, d1: true, backups: true });
      } catch (error) {
        return json({ ok: false, error: String(error?.message || error) }, 500);
      }
    }

    if (url.pathname === "/api/backups") {
      await ensureSchema(env);

      if (request.method === "GET") {
        const rows = await env.DB.prepare(
          "SELECT id, created_at, source FROM app_backups ORDER BY created_at DESC, id DESC LIMIT 10"
        ).all();

        return json({
          backups: (rows?.results || []).map((r) => ({
            id: Number(r.id),
            createdAt: Number(r.created_at || 0),
            source: String(r.source || "auto")
          }))
        });
      }

      if (request.method === "POST") {
        let body = {};
        try {
          body = await request.json();
        } catch {}

        if (body?.action === "create") {
          const row = await currentState(env);
          if (!row?.data) return json({ error: "Todavía no hay datos para guardar" }, 400);
          const id = await addBackup(env, row.data, "manual");
          return json({ ok: true, id });
        }

        if (body?.action === "restore") {
          const id = Number(body.id || 0);
          if (!id) return json({ error: "Copia no válida" }, 400);

          const backup = await env.DB.prepare(
            "SELECT data FROM app_backups WHERE id = ?"
          ).bind(id).first();

          if (!backup?.data) return json({ error: "Copia no encontrada" }, 404);

          const current = await currentState(env);
          if (current?.data) await addBackup(env, current.data, "before_restore");

          const updatedAt = Date.now();
          await env.DB.prepare(`
            INSERT INTO app_state (id, data, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
              data = excluded.data,
              updated_at = excluded.updated_at
          `).bind("main", backup.data, updatedAt).run();

          await addBackup(env, backup.data, "restored");
          return json({ ok: true, updatedAt });
        }

        return json({ error: "Acción no válida" }, 400);
      }

      return new Response("Method Not Allowed", { status: 405 });
    }

    if (url.pathname === "/api/sync") {
      await ensureSchema(env);

      if (request.method === "GET") {
        const row = await currentState(env);

        if (!row) {
          return json({ data: null, updatedAt: 0 });
        }

        let data = {};
        try {
          data = JSON.parse(row.data || "{}");
        } catch {
          data = {};
        }
        return json({ data, updatedAt: Number(row.updated_at || 0) });
      }

      if (request.method === "PUT") {
        let body;
        try {
          body = await request.json();
        } catch {
          return json({ error: "JSON inválido" }, 400);
        }

        if (!body || typeof body.data !== "object" || Array.isArray(body.data)) {
          return json({ error: "Formato de datos no válido" }, 400);
        }

        const updatedAt = Date.now();
        const data = JSON.stringify(body.data);

        await env.DB.prepare(`
          INSERT INTO app_state (id, data, updated_at)
          VALUES (?, ?, ?)
          ON CONFLICT(id) DO UPDATE SET
            data = excluded.data,
            updated_at = excluded.updated_at
        `).bind("main", data, updatedAt).run();

        await addBackup(env, data, "auto");

        return json({ ok: true, updatedAt });
      }

      return new Response("Method Not Allowed", { status: 405 });
    }

    const assetResponse = await env.ASSETS.fetch(request);

    if (
      request.method === "GET" &&
      (
        request.mode === "navigate" ||
        url.pathname === "/" ||
        url.pathname.endsWith("/index.html") ||
        url.pathname.endsWith("/version.json") ||
        url.pathname.endsWith("/sw.js")
      )
    ) {
      return withNoStore(assetResponse);
    }

    return assetResponse;
  }
};
