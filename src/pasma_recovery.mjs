/* LA PASMA (NUEVA): restore only missing titles from an existing D1 backup.
 * Pure function: no network, D1 write, deletion or PWA version change here.
 * Executed server-side with a separately verified, transactional D1 update.
 */
export const LA_PASMA_ORDER = [
  "CIEN GAVIOTAS","CLAVADO EN UN BAR","ESCUELA DE CALOR","HACE CALOR",
  "LOBO-HOMBRE EN PARÍS","MIL CALLES LLEVAN HACIA TI","SABOR DE AMOR","EL LÍMITE",
  "LA CHICA DE AYER","EL RITMO DEL GARAJE","SALTA","NO PUEDO VIVIR SIN TI",
  "ESO QUE TÚ ME DAS","INSURRECCIÓN","QUERIDA MILAGROS","ENAMORADO DE LA MODA JUVENIL",
  "ADIÓS PAPÁ","CADILLAC SOLITARIO","CAROLINA","CUANDO BRILLE EL SOL",
  "DÉJAME","FRÍO","MIÑA TERRA GALEGA"
];

// Base slots 0...70 are immutable and validated in the versioned cancionero.
// Never infer a base index from the old duplicate's numeric ID.
const BASE_INDEX = new Map(Object.entries({
  "CLAVADO EN UN BAR":13,
  "SALTA":54,
  "NO PUEDO VIVIR SIN TI":47,
  "ESO QUE TÚ ME DAS":25,
  "INSURRECCIÓN":30,
  "QUERIDA MILAGROS":52,
  "CADILLAC SOLITARIO":9,
  "DÉJAME":18,
  "FRÍO":28
}));

const PREFIX = "quintoElemento.";
const CUSTOM_KEY = PREFIX+"customSongs.v1";
const PASSES_KEY = PREFIX+"passes.v1";
const FIRST_CUSTOM=71;

function normalizedTitle(s) {
  return String(s||"").normalize("NFD").replace(/[\u0300-\u036f]/g,"")
    .toUpperCase().replace(/[^A-Z0-9]+/g," ").trim();
}
function parse(value,fallback) {
  if (typeof value==="object" && value!==null) return value;
  if(typeof value!=="string")return fallback;
  try {return JSON.parse(value)}catch {return fallback}
}
function textFingerprint(s){
  return String(s||"").replace(/\r\n?/g,"\n").replace(/[ \t]+/g," ")
    .replace(/[\n ]+$/g,"").normalize("NFC");
}
function getCustom(state) {
  const c=parse(state[CUSTOM_KEY],[]);
  if(!Array.isArray(c) || !c.every(x=>x && typeof x==="object" && typeof x.title==="string" && typeof x.text==="string"))
    throw new Error("Datos de canciones personalizadas inválidos");
  return c;
}
function getPasses(state) {
  const p=parse(state[PASSES_KEY],[]);
  if(!Array.isArray(p) || !p.every(x=>x && typeof x==="object" && Array.isArray(x.songs)))
    throw new Error("Los pases no tienen un formato válido");
  return p;
}
function getTitle(state,item,index) {
  return String(state[PREFIX+"title.v1."+index]||item.title||"");
}
function getLyrics(state,item,index) {
  return String(state[PREFIX+"lyrics.v1."+index]||item.text||"");
}
function anchorScore(value) {
  const d=parse(value,{});
  if(!d || typeof d!=="object")return 0;
  const populated=(obj)=>obj && typeof obj==="object" ? Object.values(obj).filter(v=>String(v||"").trim()).length:0;
  return populated(d.words)+populated(d.lines)+populated(d.instrumentals)+
    (String(d.intro||"").trim()?1:0);
}
function deepCopy(x){return JSON.parse(JSON.stringify(x))}
function key(x){return normalizedTitle(x)}
function assertText(x,y,label){
  if(textFingerprint(x)!==textFingerprint(y))throw new Error("Dos versiones de "+label+" tienen letras distintas: revisión manual");
}

export function buildLaPasmaRecovery(current,archived) {
  if(!current||typeof current!=="object"||Array.isArray(current) ||
     !archived||typeof archived!=="object"||Array.isArray(archived))
    throw new Error("Los estados D1 deben ser objetos");

  const currentExtras=getCustom(current);
  const archivedExtras=getCustom(archived);
  const currentPasses=getPasses(current);
  const archivedPasses=getPasses(archived);

  if(archivedExtras.length!==28)throw new Error("La copia origen no contiene las 28 personalizadas de 99 entradas");
  const currentTargets=currentPasses.filter(p=>key(p.name)===key("LA PASMA (NUEVA)"));
  const archivedTargets=archivedPasses.filter(p=>key(p.name)===key("LA PASMA (NUEVA)"));
  if(currentTargets.length!==1||archivedTargets.length!==1)
    throw new Error("Se requiere exactamente un pase LA PASMA (NUEVA) en ambos estados");
  if(currentTargets[0].songs.length!==23 || archivedTargets[0].songs.length!==23)
    throw new Error("Un pase LA PASMA no tiene 23 posiciones");

  const currentNameToId=new Map([...BASE_INDEX.entries()].map(([title,id])=>[key(title),id]));
  currentExtras.forEach((item,i)=>{
    const title=key(getTitle(current,item,FIRST_CUSTOM+i));
    const previous=currentNameToId.get(title);
    if(previous!==undefined)throw new Error("El estado actual ya contiene un título personalizado duplicado: "+title);
    currentNameToId.set(title,FIRST_CUSTOM+i);
  });
  const archivedByName=new Map();
  const sourceIdTitle=new Map();
  archivedExtras.forEach((item,i)=>{
    const oldId=FIRST_CUSTOM+i;
    const title=getTitle(archived,item,oldId);
    const k=key(title);
    sourceIdTitle.set(oldId,k);
    const row={id:oldId,title,item,lyric:getLyrics(archived,item,oldId),
      chords:anchorScore(archived[PREFIX+"chords.v2."+oldId])};
    const entries=archivedByName.get(k)||[];
    entries.push(row);
    archivedByName.set(k,entries);
  });
  // Every song in the archive must have a consistent version across its two duplicates.
  // Preserve the same lyrics that the chord indices refer to.
  for(const [title,entries] of archivedByName) {
    if(entries.length<2)continue;
    for(const e of entries.slice(1))assertText(entries[0].lyric,e.lyric,title);
  }
  const targetKeys=LA_PASMA_ORDER.map(t=>key(t));
  for(const t of targetKeys) {
    if(currentNameToId.has(t))continue;
    if(!archivedByName.has(t))throw new Error("La copia no tiene la canción "+t);
  }

  const next=deepCopy(current);
  const extras=deepCopy(currentExtras);
  const added=[];
  const chosenOldIdToNewId=new Map();

  // D1 was left with chords/lyrics from the old 99-ID layout even though only
  // 72 songs are active. Those keys belong to old song IDs and cannot simply
  // be reused: e.g. old 72 is ESCUELA, but new 72 will be CIEN GAVIOTAS.
  // The Worker preserves ALL these keys in a durable pre-migration archive
  // before committing this planned remapping. Orphan values are read from
  // current state for merging into the matching restored titles.
  const sourcePrefixes=new Set();
  for(const oldKey of Object.keys(archived)) {
    const match=oldKey.match(/^(quintoElemento\..+)\.(\d+)$/);
    if(match && Number(match[2])>=FIRST_CUSTOM &&
       Number(match[2])<FIRST_CUSTOM+archivedExtras.length)
      sourcePrefixes.add(match[1]);
  }
  for(const prefix of [PREFIX+"lyrics.v1",PREFIX+"title.v1",PREFIX+"chords.v2"])
    sourcePrefixes.add(prefix);
  const orphanIndexedKeys=[];
  const lowestOrphanId=FIRST_CUSTOM+currentExtras.length;
  for(const k of Object.keys(next)) {
    const match=k.match(/^(quintoElemento\..+)\.(\d+)$/);
    if(!match || !sourcePrefixes.has(match[1]))continue;
    const id=Number(match[2]);
    if(id>=lowestOrphanId && id<FIRST_CUSTOM+archivedExtras.length){
      orphanIndexedKeys.push(k);
      delete next[k];
    }
  }
  let currentOrphanChordMapsUsed=0;
  let currentOrphanLyricEditsPreserved=0;

  for(const t of targetKeys) {
    if(currentNameToId.has(t))continue;
    const candidates=archivedByName.get(t);
    const chosen=candidates.slice().sort((a,b)=>b.chords-a.chords||a.id-b.id)[0];
    const newId=FIRST_CUSTOM+extras.length;
    const item=deepCopy(chosen.item);
    item.title=chosen.title;
    item.text=chosen.lyric;
    if(!item.text.trim())throw new Error("La letra recuperada está vacía: "+t);

    // Remap all per-song local-storage fields, never touching global settings or other songs.
    const suffix="."+chosen.id;
    for(const [oldKey,val] of Object.entries(archived)) {
      if(!oldKey.startsWith(PREFIX) || !oldKey.endsWith(suffix))continue;
      const dst=oldKey.slice(0,-suffix.length)+"."+newId;
      if(dst in next)throw new Error("El ID nuevo ya tiene datos: "+dst);
      next[dst]=val;
    }

    // A more recent orphan may contain edits not present in backup 371.
    // Compare its original song ID against the archived song identity.
    const currentOrphanTitle=current[PREFIX+"title.v1."+chosen.id];
    if(currentOrphanTitle && key(currentOrphanTitle)!==t)
      throw new Error("El título huérfano no corresponde a la copia: "+t);
    const orphanLyric=current[PREFIX+"lyrics.v1."+chosen.id];
    const differs=typeof orphanLyric==="string" && orphanLyric.trim() &&
       textFingerprint(orphanLyric)!==textFingerprint(chosen.lyric);
    if(differs) {
      // Current editor content is authoritative; do NOT reuse old chord
      // positions when its lyrics have changed.
      item.text=orphanLyric;
      next[PREFIX+"lyrics.v1."+newId]=orphanLyric;
      const orphanChords=current[PREFIX+"chords.v2."+chosen.id];
      if(orphanChords){
        next[PREFIX+"chords.v2."+newId]=orphanChords;
        currentOrphanChordMapsUsed++;
      }else{
        delete next[PREFIX+"chords.v2."+newId];
      }
      currentOrphanLyricEditsPreserved++;
    } else {
      if(!next[PREFIX+"lyrics.v1."+newId] && chosen.lyric!==String(chosen.item.text||""))
        next[PREFIX+"lyrics.v1."+newId]=chosen.lyric;
      // The two lyric layouts match. Preserve newer user-added chord anchors,
      // while retaining source chords for any untouched slots.
      const recent=parse(current[PREFIX+"chords.v2."+chosen.id],null);
      const older=parse(archived[PREFIX+"chords.v2."+chosen.id],null);
      if(recent && typeof recent==="object" && !Array.isArray(recent)){
        const merged=deepCopy(older && typeof older==="object" && !Array.isArray(older)?older:{});
        for(const prop of ["words","lines","instrumentals","instrumentalsText"]) {
          const base=merged[prop] && typeof merged[prop]==="object" ? merged[prop]:{};
          const changed=recent[prop] && typeof recent[prop]==="object" ? recent[prop]:{};
          merged[prop]={...base,...changed};
        }
        for(const prop of ["intro","introText"]) {
          if(String(recent[prop]||"").trim())merged[prop]=recent[prop];
        }
        if(Array.isArray(recent.references) && recent.references.length)
          merged.references=recent.references;
        next[PREFIX+"chords.v2."+newId]=JSON.stringify(merged);
        currentOrphanChordMapsUsed++;
      }
    }
    extras.push(item);
    currentNameToId.set(t,newId);
    chosenOldIdToNewId.set(chosen.id,newId);
    added.push({title:chosen.title,id:newId,sourceId:chosen.id,chords:chosen.chords});
  }
  // Do not add the archived duplicates. Their old IDs are mapped by title only.
  next[CUSTOM_KEY]=JSON.stringify(extras);
  const mapped=targetKeys.map(t=>{
    const id=currentNameToId.get(t);
    if(!Number.isInteger(id)||id<0||id>=FIRST_CUSTOM+extras.length)
      throw new Error("Falta una posición del pase: "+t);
    return id;
  });
  const outPasses=deepCopy(currentPasses);
  const target=outPasses.find(p=>key(p.name)===key("LA PASMA (NUEVA)"));
  target.songs=mapped;

  const otherMapped=[];
  for(const p of outPasses) {
    if(p===target)continue;
    // Only migrate an old pass when its ID and exact song-index array agree
    // with the same pass in the earlier snapshot. Current/new passes remain untouched.
    const old=archivedPasses.find(z=>z.id===p.id);
    if(!old||JSON.stringify(old.songs)!==JSON.stringify(p.songs))continue;
    const changed=[];
    const rebuilt=p.songs.map((id,pos)=>{
      if(!Number.isInteger(id)||id<0)throw new Error("Referencia inválida en pase "+p.name);
      if(id<FIRST_CUSTOM)return id;
      const title=sourceIdTitle.get(id);
      if(!title)throw new Error("Referencia de pase antigua desconocida "+id);
      const dst=currentNameToId.get(title);
      if(dst===undefined)throw new Error("No se recuperó la canción del pase "+title);
      if(dst!==id)changed.push(pos);
      return dst;
    });
    if(changed.length){
      p.songs=rebuilt;
      otherMapped.push({name:p.name,refsChanged:changed.length});
    }
  }
  next[PASSES_KEY]=JSON.stringify(outPasses);

  const allTargetIds=target.songs;
  if(new Set(allTargetIds).size!==23)throw new Error("El pase tiene referencias duplicadas");
  if(allTargetIds.some(id=>id>=FIRST_CUSTOM+extras.length))
    throw new Error("Quedaron índices rotos en LA PASMA");
  const summary={
    originalCount:FIRST_CUSTOM+currentExtras.length,
    afterCount:FIRST_CUSTOM+extras.length,
    sourceCount:FIRST_CUSTOM+archivedExtras.length,
    recoveredCount:added.length,
    skippedArchiveDuplicateCount:14,
    orphanIndexedKeysArchived:orphanIndexedKeys.length,
    currentOrphanChordMapsUsed,
    currentOrphanLyricEditsPreserved,
    restored:added,
    passName:target.name,
    passId:target.id,
    passSongIds:mapped,
    fixedOtherPasses:otherMapped,
    preservedCurrentCustomTitles:currentExtras.map((s,i)=>getTitle(current,s,FIRST_CUSTOM+i)),
    changedKeys:Object.keys(next).filter(k=>next[k]!==current[k]).length,
    action:"MERGE_ONLY_NO_DELETION"
  };
  return {state:next,summary};
}
