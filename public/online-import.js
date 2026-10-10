(function(){
  'use strict';

  var modal=document.getElementById('qeImportModal');
  if(!modal)return;

  var titleInput=document.getElementById('qeImportTitle');
  var artistInput=document.getElementById('qeImportArtist');
  var searchBtn=document.getElementById('qeImportSearch');
  var resultsEl=document.getElementById('qeImportResults');
  var statusEl=document.getElementById('qeImportStatus');
  var preview=document.getElementById('qeImportPreview');
  var previewHead=document.getElementById('qeImportPreviewHead');
  var previewText=document.getElementById('qeImportPreviewText');
  var applyBtn=document.getElementById('qeImportApply');
  var restoreBtn=document.getElementById('qeImportRestore');
  var closeBtn=document.getElementById('qeImportClose');
  var cancelBtn=document.getElementById('qeImportCancel');

  var state={target:-1,results:[],selected:null,song:null,busy:false};
  var ROOTS={C:'DO','C#':'DO#',Db:'DO#',D:'RE','D#':'RE#',Eb:'RE#',E:'MI',F:'FA','F#':'FA#',Gb:'FA#',G:'SOL','G#':'SOL#',Ab:'SOL#',A:'LA','A#':'LA#',Bb:'LA#',B:'SI'};

  function setStatus(text){statusEl.textContent=text||''}
  function fold(s){
    s=String(s||'').toLowerCase();
    try{s=s.normalize('NFD').replace(/[\u0300-\u036f]/g,'')}catch(e){}
    return s.replace(/\s+/g,' ').trim();
  }
  function safeJson(v,fallback){try{return JSON.parse(v)}catch(e){return fallback}}
  function stripToken(token){return String(token||'').replace(/^[|:;,.-]+|[|:;,.-]+$/g,'')}

  function chordParts(token){
    var clean=stripToken(token);
    if(!clean)return null;
    var bass='';
    var bassMatch=clean.match(/\/([A-G](?:#|b)?)$/);
    if(bassMatch){bass=bassMatch[1];clean=clean.slice(0,-bassMatch[0].length)}
    var m=clean.match(/^([A-G](?:#|b)?)(.*)$/);
    if(!m)return null;
    var suffix=m[2]||'';
    if(suffix && !/^(?:(?:maj|min|dim|aug|sus|add|omit|no|m|M)|[0-9]|[#b()+\-º°\/])*$/.test(suffix))return null;
    var root=ROOTS[m[1]];
    if(!root)return null;
    var out=root+suffix;
    if(bass){
      var b=ROOTS[bass];
      if(!b)return null;
      out+='/'+b;
    }
    return out;
  }

  function chordLine(raw){
    var entries=[],total=0,recognized=0;
    var re=/\S+/g,m;
    while((m=re.exec(String(raw||'')))){
      var original=m[0],clean=stripToken(original);
      if(!clean)continue;
      total++;
      var chord=chordParts(clean);
      if(chord){recognized++;entries.push({chord:chord,col:m.index})}
      else if(/^[-|:;,.()xX0-9]+$/.test(clean)){recognized++}
    }
    if(!entries.length||!total)return null;
    if(recognized/total<0.72)return null;
    return entries;
  }

  function sectionLabel(raw){
    var n=fold(raw).replace(/[\[\](){}:.-]/g,' ').replace(/\s+/g,' ').trim();
    if(!n||n.length>44)return '';
    if(/^intro(?:ducao|duccion)?(?: \d+| x\d+| \d+x)?$/.test(n))return 'INTRO';
    if(/^(?:verso|estrofa|primeira parte|segunda parte|terceira parte)(?: \d+)?$/.test(n))return 'ESTROFA';
    if(/^(?:pre refrao|pre refrão|pre estribillo|pre chorus)(?: \d+)?$/.test(n))return 'PRE-ESTRIBILLO';
    if(/^(?:refrao|refrão|estribillo|chorus)(?: \d+)?$/.test(n))return 'ESTRIBILLO';
    if(/^(?:ponte|puente|bridge)(?: \d+)?$/.test(n))return 'PUENTE';
    if(/^(?:solo|instrumental)(?: \d+)?$/.test(n))return n.indexOf('solo')===0?'SOLO':'INSTRUMENTAL';
    if(/^(?:final|outro|coda)(?: \d+)?$/.test(n))return 'FINAL';
    return '';
  }

  function blankPush(out){
    if(out.length && out[out.length-1]!=='')out.push('');
  }

  function wordStarts(line){
    var arr=[],re=/\S+/g,m;
    while((m=re.exec(String(line||''))))arr.push({index:m.index,word:arr.length});
    return arr;
  }

  function nearestWord(starts,col){
    if(!starts.length)return -1;
    var best=0,dist=Math.abs(starts[0].index-col);
    for(var i=1;i<starts.length;i++){
      var d=Math.abs(starts[i].index-col);
      if(d<dist){dist=d;best=i}
    }
    return starts[best].word;
  }

  function seq(entries){
    return entries.map(function(x){return x.chord}).filter(function(x,i,a){return i===0||x!==a[i-1]}).join(' · ');
  }

  function parseTranscription(text){
    var source=String(text||'').replace(/\r/g,'').split('\n');
    var out=[],data={lines:{},words:{},intro:'',introText:'',instrumentals:{},instrumentalsText:{},references:[]};
    var pending=null,section='',lyricSeen=false;

    function flushPending(){
      if(!pending||!pending.length)return;
      var progression=seq(pending);
      if(!progression){pending=null;return}
      if(!lyricSeen||section==='INTRO'){
        if(!data.intro)data.intro=progression;
      }else{
        var boundary=out.length;
        if(!data.instrumentals[String(boundary)]){
          data.instrumentals[String(boundary)]=progression;
          data.instrumentalsText[String(boundary)]=section==='SOLO'?'SOLO':'Importado';
        }
      }
      pending=null;
    }

    source.forEach(function(raw){
      var trimmed=String(raw||'').trim();
      if(!trimmed){
        if(pending && section==='INTRO')flushPending();
        blankPush(out);
        return;
      }

      if(/^(?:tom|key|capo|capotraste|afinacao|afinação|tuning)\s*:/i.test(trimmed))return;
      if(/^(?:[EADGBe][|:].*)$/.test(trimmed))return;
      if(/^[|:\-=_~\s]+$/.test(trimmed))return;

      var label=sectionLabel(trimmed);
      if(label){
        flushPending();
        section=label;
        blankPush(out);
        out.push('['+label+']');
        return;
      }

      var chords=chordLine(raw);
      if(chords){
        pending=(pending||[]).concat(chords);
        return;
      }

      var lineIndex=out.length;
      out.push(trimmed);
      lyricSeen=true;

      if(pending&&pending.length){
        var starts=wordStarts(raw);
        var used={},collision=false;
        pending.forEach(function(c){
          var wi=nearestWord(starts,c.col);
          if(wi<0){collision=true;return}
          if(used[wi]){collision=true;return}
          used[wi]=c.chord;
        });
        if(collision){
          data.lines[String(lineIndex)]=seq(pending);
        }else{
          Object.keys(used).forEach(function(wi){data.words[lineIndex+':'+wi]=used[wi]});
        }
        pending=null;
      }
    });

    flushPending();
    while(out.length&&out[out.length-1]==='')out.pop();
    while(out.length&&out[0]==='')out.shift();
    var lyrics=out.join('\n').replace(/\n{3,}/g,'\n\n').trim();
    return {lyrics:lyrics,chords:data};
  }

  function mergeChordData(existing,imported){
    existing=existing||{lines:{},words:{},intro:'',introText:'',instrumentals:{},instrumentalsText:{},references:[]};
    imported=imported||{lines:{},words:{},intro:'',introText:'',instrumentals:{},instrumentalsText:{},references:[]};
    existing.lines=existing.lines||{};existing.words=existing.words||{};existing.instrumentals=existing.instrumentals||{};existing.instrumentalsText=existing.instrumentalsText||{};
    Object.keys(imported.lines||{}).forEach(function(k){if(!existing.lines[k])existing.lines[k]=imported.lines[k]});
    Object.keys(imported.words||{}).forEach(function(k){if(!existing.words[k])existing.words[k]=imported.words[k]});
    if(!existing.intro&&imported.intro)existing.intro=imported.intro;
    Object.keys(imported.instrumentals||{}).forEach(function(k){
      if(!existing.instrumentals[k]){
        existing.instrumentals[k]=imported.instrumentals[k];
        if(imported.instrumentalsText&&imported.instrumentalsText[k])existing.instrumentalsText[k]=imported.instrumentalsText[k];
      }
    });
    return existing;
  }

  function historyKey(i){return 'quintoElemento.onlineImportHistory.v1.'+i}
  function loadHistory(i){
    var a=safeJson(localStorage.getItem(historyKey(i))||'[]',[]);
    return Array.isArray(a)?a:[];
  }
  function pushHistory(i){
    var a=loadHistory(i);
    var meta=safeJson(localStorage.getItem('quintoElemento.songMeta.v1.'+i)||'{}',{});
    a.push({at:Date.now(),title:getSongTitle(i),text:getSongText(i),chords:getChordData(i),meta:meta});
    if(a.length>5)a=a.slice(a.length-5);
    localStorage.setItem(historyKey(i),JSON.stringify(a));
  }
  function updateRestore(){
    restoreBtn.style.display=state.target>=0?'inline-flex':'none';
    restoreBtn.disabled=state.target<0||!loadHistory(state.target).length;
  }

  function resetPreview(){
    state.selected=null;state.song=null;state.results=[];
    resultsEl.innerHTML='';preview.classList.remove('on');previewText.textContent='';previewHead.textContent='';
    applyBtn.disabled=true;
  }

  function openImporter(target){
    state.target=typeof target==='number'?target:-1;
    resetPreview();
    if(state.target>=0){
      titleInput.value=getSongTitle(state.target);
      setStatus('Buscará una versión con letra y acordes. Nada se cambia hasta pulsar “Aplicar”.');
    }else{
      titleInput.value=(document.getElementById('q')&&document.getElementById('q').value)||'';
      setStatus('Escribe título y, si lo sabes, artista.');
    }
    artistInput.value='';
    updateRestore();
    modal.classList.add('on');modal.setAttribute('aria-hidden','false');
    setTimeout(function(){(titleInput.value?artistInput:titleInput).focus()},60);
  }
  function closeImporter(){modal.classList.remove('on');modal.setAttribute('aria-hidden','true')}

  function renderResults(){
    resultsEl.innerHTML='';
    state.results.forEach(function(item,idx){
      var b=document.createElement('button');b.type='button';b.className='qeImportResult';
      var t=document.createElement('strong');t.textContent=item.title||'Sin título';
      var a=document.createElement('span');a.textContent=(item.artist||'Artista desconocido')+' · '+(item.source||'Fuente');
      b.appendChild(t);b.appendChild(a);
      b.onclick=function(){selectResult(idx,b)};
      resultsEl.appendChild(b);
    });
  }

  async function doSearch(){
    var title=titleInput.value.trim(),artist=artistInput.value.trim();
    if(!title){setStatus('Escribe el título de la canción.');titleInput.focus();return}
    state.busy=true;searchBtn.disabled=true;applyBtn.disabled=true;preview.classList.remove('on');
    resultsEl.innerHTML='';setStatus('Buscando letra y acordes…');
    try{
      var q=[title,artist].filter(Boolean).join(' ');
      var r=await fetch('/api/song-search?q='+encodeURIComponent(q),{cache:'no-store'});
      var d=await r.json();
      if(!r.ok||!d.ok)throw new Error(d.error||'No se pudo buscar');
      state.results=Array.isArray(d.results)?d.results:[];
      renderResults();
      setStatus(state.results.length?state.results.length+' resultados. Elige la versión correcta.':'No se encontraron resultados.');
    }catch(e){
      setStatus('No se pudo consultar la fuente. Comprueba la conexión e inténtalo de nuevo.');
    }finally{state.busy=false;searchBtn.disabled=false}
  }

  async function selectResult(idx,button){
    var item=state.results[idx];if(!item)return;
    Array.prototype.forEach.call(resultsEl.children,function(x){x.classList.remove('selected')});
    button.classList.add('selected');
    state.selected=item;state.song=null;applyBtn.disabled=true;preview.classList.remove('on');
    setStatus('Extrayendo la versión seleccionada…');
    try{
      var r=await fetch('/api/song-fetch?url='+encodeURIComponent(item.url),{cache:'no-store'});
      var d=await r.json();
      if(!r.ok||!d.ok||!d.song)throw new Error(d.error||'No se pudo extraer');
      state.song=d.song;
      previewHead.textContent=(d.song.title||item.title)+' · '+(d.song.artist||item.artist)+(d.song.key?' · Tono '+d.song.key:'');
      previewText.textContent=d.song.transcription||'';
      preview.classList.add('on');
      applyBtn.disabled=!d.song.transcription;
      setStatus('Vista previa lista. Revisa que sea la canción correcta antes de aplicar.');
    }catch(e){
      setStatus('No se pudo leer esta versión. Prueba otro resultado.');
    }
  }

  function markForReview(i){
    var key='quintoElemento.songMeta.v1.'+i;
    var m=safeJson(localStorage.getItem(key)||'{}',{});
    m.lyricsOk=false;m.chordsOk=false;m.ready=false;
    localStorage.setItem(key,JSON.stringify(m));
  }

  function sourceRecord(item,song){
    return {source:(song&&song.source)||item.source||'Cifra Club',url:(song&&song.sourceUrl)||item.url||'',importedAt:new Date().toISOString(),title:(song&&song.title)||item.title||'',artist:(song&&song.artist)||item.artist||''};
  }

  function applyToExisting(i,parsed){
    pushHistory(i);
    var oldText=getSongText(i);
    var newText=normalizeMasterText(parsed.lyrics);
    var existing=getChordData(i);
    var migrated=migrateChordData(oldText,newText,existing);
    var merged=mergeChordData(migrated,parsed.chords);
    merged.importSource=sourceRecord(state.selected,state.song);
    saveSongText(i,newText);
    saveChordData(i,merged);
    markForReview(i);
    if(typeof st!=='undefined'&&st&&typeof current!=='undefined'&&current===i)st.textContent=getSongTitle(i);
    if(typeof renderLyrics==='function'&&typeof current!=='undefined'&&current===i)renderLyrics();
    if(typeof render==='function')render((document.getElementById('q')||{}).value||'');
  }

  function applyAsNew(parsed){
    var title=normalizeMasterTitle((state.song&&state.song.title)||(state.selected&&state.selected.title)||titleInput.value);
    var text=normalizeMasterText(parsed.lyrics);
    if(!title||!text)throw new Error('Faltan título o letra');
    for(var i=0;i<songs.length;i++)if(getSongTitle(i)===title)throw new Error('Ya existe una canción con ese título.');
    var obj={title:title,text:text};
    customSongs.push(obj);saveCustomSongs(customSongs);songs.push(obj);
    var idx=songs.length-1;saveSongTitle(idx,title);
    parsed.chords.importSource=sourceRecord(state.selected,state.song);
    saveChordData(idx,parsed.chords);markForReview(idx);
    var count=document.getElementById('count');if(count)count.textContent=songs.length+' canciones';
    if(typeof render==='function')render('');
    return idx;
  }

  async function applySelected(){
    if(!state.song||!state.song.transcription)return;
    var parsed=parseTranscription(state.song.transcription);
    if(!parsed.lyrics||parsed.lyrics.length<20){setStatus('La versión no contiene suficiente letra para importarla.');return}
    applyBtn.disabled=true;
    try{
      var idx;
      if(state.target>=0){
        idx=state.target;
        applyToExisting(idx,parsed);
      }else{
        idx=applyAsNew(parsed);
      }
      closeImporter();
      if(typeof openSong==='function')openSong(idx);
      if(typeof showSavedToast==='function')showSavedToast();
      alert('Importación aplicada. Se ha conservado una copia anterior y los acordes que ya existían tienen prioridad.');
    }catch(e){
      setStatus(e&&e.message?e.message:'No se pudo aplicar la importación.');
      applyBtn.disabled=false;
    }
  }

  function restoreLast(){
    if(state.target<0)return;
    var a=loadHistory(state.target);
    if(!a.length)return;
    var last=a[a.length-1];
    if(!confirm('¿Restaurar la versión anterior de esta canción?'))return;
    a.pop();localStorage.setItem(historyKey(state.target),JSON.stringify(a));
    saveSongTitle(state.target,last.title||getSongTitle(state.target));
    saveSongText(state.target,last.text||'');
    saveChordData(state.target,last.chords||{lines:{},words:{},intro:'',introText:'',instrumentals:{},instrumentalsText:{},references:[]});
    localStorage.setItem('quintoElemento.songMeta.v1.'+state.target,JSON.stringify(last.meta||{}));
    if(typeof current!=='undefined'&&current===state.target){st.textContent=getSongTitle(state.target);renderLyrics()}
    if(typeof render==='function')render((document.getElementById('q')||{}).value||'');
    updateRestore();
    setStatus('Versión anterior restaurada.');
  }

  var oldMigrate=typeof migrateChordData==='function'?migrateChordData:null;
  if(oldMigrate){
    migrateChordData=function(oldText,newText,data){
      var next=oldMigrate(oldText,newText,data);
      if(data&&data.importSource)next.importSource=data.importSource;
      return next;
    };
  }

  var indexBtn=document.getElementById('onlineImportIndexBtn');
  if(indexBtn)indexBtn.addEventListener('click',function(){openImporter(-1)});
  var settingsBtn=document.getElementById('settingsOnlineImport');
  if(settingsBtn)settingsBtn.addEventListener('click',function(){
    if(typeof current==='undefined'||current<0){alert('Abre primero una canción para actualizarla, o usa “Internet” desde el índice para añadir una nueva.');return}
    var sm=document.getElementById('settingsModal');if(sm){sm.classList.remove('on');sm.setAttribute('aria-hidden','true')}
    openImporter(current);
  });
  var passesNew=document.getElementById('passesNewBtn');
  if(passesNew)passesNew.addEventListener('click',function(){
    var pm=document.getElementById('passesModal');if(pm)pm.classList.remove('on');
    var create=document.getElementById('createPassBtn');if(create)create.click();
  });

  searchBtn.addEventListener('click',doSearch);
  titleInput.addEventListener('keydown',function(e){if(e.key==='Enter'){e.preventDefault();doSearch()}});
  artistInput.addEventListener('keydown',function(e){if(e.key==='Enter'){e.preventDefault();doSearch()}});
  applyBtn.addEventListener('click',applySelected);
  restoreBtn.addEventListener('click',restoreLast);
  closeBtn.addEventListener('click',closeImporter);
  cancelBtn.addEventListener('click',closeImporter);
  modal.addEventListener('click',function(e){if(e.target===modal)closeImporter()});

  window.qeOpenOnlineImporter=openImporter;
})();
