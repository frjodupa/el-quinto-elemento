/* EQE: per-device three-way sync, using the existing server CAS revision. */
(function(){
  'use strict';
  var M=window.EQESyncMerge,P='quintoElemento.',BASE='qeSync.base.v2',JOURNAL='qeSync.journal.v2';
  var rawSet=Storage.prototype.setItem,rawRemove=Storage.prototype.removeItem;
  var busy=false,applying=false,timer=0,pending=null;
  var baseCount=typeof baseSongCount==='number'?baseSongCount:71;
  function get(k){return localStorage.getItem(k)}
  function put(k,v){rawSet.call(localStorage,k,String(v))}
  function read(k){var v=get(k);return v===null?null:JSON.parse(v)}
  function collect(){var s={};for(var i=0;i<localStorage.length;i++){var k=localStorage.key(i);if(k&&k.indexOf(P)===0)s[k]=get(k)}return s}
  function status(label,detail){
    var a=document.getElementById('cloudSyncStatus'),b=document.getElementById('cloudSyncDetail');
    if(a)a.textContent=label;if(b)b.textContent=detail||'';
  }
  function editing(){
    return !!document.querySelector('#view.editing,.lyricEditorModal.on,.chordModal.on,.newSongModal.on')||
      !!(document.activeElement&&/^(INPUT|TEXTAREA|SELECT)$/.test(document.activeElement.tagName));
  }
  function replaceState(s){
    applying=true;
    try{
      Object.keys(collect()).forEach(function(k){if(!(k in s))rawRemove.call(localStorage,k)});
      Object.keys(s).forEach(function(k){if(k.indexOf(P)===0)put(k,s[k])});
    }finally{applying=false}
  }
  function recover(){
    var j=read(JOURNAL);if(!j)return;
    replaceState(j.state);
    if(j.base===null)rawRemove.call(localStorage,BASE);else put(BASE,JSON.stringify(j.base));
    put('qeSync.dirty','1');rawRemove.call(localStorage,JOURNAL);
  }
  function commitLocal(state,baseline){
    // Journal first. A quota error leaves the previous state recoverable; a
    // crash on the next launch rolls back before starting synchronization.
    var old={state:collect(),base:read(BASE)};
    put(JOURNAL,JSON.stringify(old));
    try{
      replaceState(state);put(BASE,JSON.stringify(baseline));
      put('qeSync.remoteTs',baseline.updatedAt);put('qeSync.dirty',M.sameState(state,baseline.data)?'0':'1');
      rawRemove.call(localStorage,JOURNAL);
    }catch(e){
      try{replaceState(old.state);if(old.base===null)rawRemove.call(localStorage,BASE);else put(BASE,JSON.stringify(old.base));rawRemove.call(localStorage,JOURNAL)}catch(rollbackError){}
      throw e;
    }
  }
  function refresh(){
    if(typeof songs!=='undefined'&&typeof loadCustomSongs==='function'){
      customSongs=loadCustomSongs();songs.splice(baseCount);
      customSongs.forEach(function(s){songs.push({title:normalizeMasterTitle(s.title),text:normalizeMasterText(s.text)})});
      var counter=document.getElementById('count');if(counter)counter.textContent=songs.length+' canciones';
    }
    if(typeof render==='function')render();
    if(typeof current!=='undefined'&&current>=0&&songs[current]){
      if(typeof st!=='undefined'&&st)st.textContent=getSongTitle(current);
      if(typeof renderLyrics==='function')renderLyrics();
    }
    if(window.updateTransposeUI)window.updateTransposeUI();
    window.dispatchEvent(new CustomEvent('eqe:sync-applied'));
  }
  async function request(method,body){
    var options={method:method,cache:'no-store'};
    if(body){options.headers={'Content-Type':'application/json'};options.body=JSON.stringify(body)}
    var controller=new AbortController(),timeout=setTimeout(function(){controller.abort()},15000);options.signal=controller.signal;
    try{
      var r=await fetch('/api/sync'+(method==='GET'?'?ts='+Date.now():''),options);
      var d=await r.json();if(!r.ok){var e=new Error(d.error||('HTTP '+r.status));e.status=r.status;throw e}
      return d;
    }finally{clearTimeout(timeout)}
  }
  function download(payload,name){
    var url=URL.createObjectURL(new Blob([JSON.stringify(payload,null,2)],{type:'application/json'})),a=document.createElement('a');
    a.href=url;a.download=name;document.body.appendChild(a);a.click();a.remove();setTimeout(function(){URL.revokeObjectURL(url)},1000);
  }
  function conflictLabel(c){
    if(c.id==='catalogue')return 'Dos canciones nuevas comparten identificador: revisar las copias completas y sus pases';
    if(c.id.indexOf('song:')===0){var id=Number(c.id.slice(5));return 'Canción: '+(typeof getSongTitle==='function'&&songs[id]?getSongTitle(id):('nueva '+(id+1)))}
    if(c.id.indexOf('pass:')===0)return 'Pase: '+((c.local&&c.local.pass||c.remote&&c.remote.pass||{}).name||c.id);
    return 'Ajuste: '+c.id.replace('key:'+P,'');
  }
  function showConflicts(result,remote,local,base){
    pending={result:result,remote:remote,local:local,base:base,choices:{}};
    put('qeSync.conflicts.v2',JSON.stringify({createdAt:new Date().toISOString(),base:base,local:local,remote:remote}));
    var box=document.getElementById('eqeSyncConflicts');
    if(!box){box=document.createElement('section');box.id='eqeSyncConflicts';box.className='eqeSyncConflicts';document.getElementById('cloudSyncDetail').parentNode.appendChild(box)}
    box.replaceChildren();
    var message=document.createElement('p');message.textContent='Hay '+result.conflicts.length+' diferencias. Revisa las dos versiones; ninguna se sustituye hasta que decidas.';box.appendChild(message);
    var backup=document.createElement('button');backup.type='button';backup.textContent='Descargar ambas copias';backup.onclick=function(){download({local:local,cloud:remote},'EQE-copias-en-conflicto.json')};box.appendChild(backup);
    result.conflicts.forEach(function(c){
      var row=document.createElement('details'),title=document.createElement('summary');title.textContent=conflictLabel(c);row.appendChild(title);
      ['local','remote'].forEach(function(side){
        var heading=document.createElement('p');heading.textContent=side==='local'?'Este dispositivo':'Nube';row.appendChild(heading);
        var pre=document.createElement('pre');pre.textContent=JSON.stringify(c[side]||'(eliminado)',null,2);row.appendChild(pre);
        var button=document.createElement('button');button.type='button';button.textContent=side==='local'?'Conservar este dispositivo':'Conservar nube';
        button.onclick=function(){pending.choices[c.id]=side;title.textContent=conflictLabel(c)+' · '+(side==='local'?'dispositivo':'nube');apply.disabled=Object.keys(pending.choices).length!==result.conflicts.length};row.appendChild(button);
      });box.appendChild(row);
    });
    var apply=document.createElement('button');apply.type='button';apply.textContent='Aplicar selección y sincronizar';apply.disabled=true;
    apply.onclick=function(){if(!pending)return;var p=pending;sync(p)};box.appendChild(apply);
    status('⚠ Revisar diferencias','Se conservan las dos copias. Los cambios sin conflicto se combinarán al terminar la revisión.');
  }
  async function sync(resolution){
    if(busy)return;
    if(!navigator.onLine){status('☁ Sin conexión','Los cambios siguen guardados aquí. Se enviarán al recuperar conexión.');return}
    if(editing()){status('☁ Cambios guardados aquí','La sincronización continuará cuando cierres el editor.');return}
    busy=true;
    try{
      recover();
      for(var attempt=0;attempt<3;attempt++){
        var remote=await request('GET');
        if(!remote||!Number.isInteger(remote.updatedAt)||remote.updatedAt<0||!(remote.data===null||remote.data&&typeof remote.data==='object'&&!Array.isArray(remote.data)))throw new Error('Respuesta de nube no válida');
        // An editor may have opened while the request was in flight.
        if(editing())return;
        var local=collect(),baseline=read(BASE),base=baseline?baseline.data:null;
        if(pending&&!resolution&&remote.updatedAt===pending.remote.updatedAt&&M.sameState(local,pending.local))return;
        var choices=null;
        if(resolution){
          if(remote.updatedAt!==resolution.remote.updatedAt||!M.sameState(local,resolution.local))resolution=null;
          else choices=resolution.choices;
        }
        var result=M.merge(base,local,remote.data||{},baseCount,choices);
        if(result.conflicts.length){showConflicts(result,remote,local,base);return}
        var snapshot=result.data,ts=remote.updatedAt;
        if(!M.sameState(snapshot,remote.data||{})){
          status('☁ Sincronizando…','Combinando cambios de los dispositivos.');
          try{var ack=await request('PUT',{data:snapshot,expectedUpdatedAt:ts});ts=ack.updatedAt}
          catch(e){if(e.status===409){resolution=null;continue}throw e}
        }
        if(!Number.isInteger(ts)||ts<0)throw new Error('Revisión de nube no válida');
        // Never acknowledge edits made while the upload was in flight. Merge
        // those against the captured local state, then queue another cycle.
        var live=collect(),late=M.merge(local,live,snapshot,baseCount);
        if(late.conflicts.length){showConflicts(late,{data:snapshot,updatedAt:ts},live,local);return}
        // Keep incoming changes out of an editor opened during an upload.
        if(editing()){put(BASE,JSON.stringify({data:local,updatedAt:remote.updatedAt}));put('qeSync.dirty','1');schedule();return}
        var changed=!M.sameState(local,late.data);
        commitLocal(late.data,{data:snapshot,updatedAt:ts});if(changed)refresh();
        var box=document.getElementById('eqeSyncConflicts');if(box)box.remove();pending=null;
        rawRemove.call(localStorage,'qeSync.conflicts.v2');
        if(get('qeSync.dirty')==='1'){schedule();return}
        status('☁ Sincronizado','Datos compartidos · '+new Date(ts).toLocaleString('es-ES')+' · v'+APP_VERSION);return;
      }
      status('☁ Cambios pendientes','Otro dispositivo está guardando. Se reintentará automáticamente.');schedule();
    }catch(e){
      status(e&&e.status===403?'Vista de pruebas':'⚠ Sincronización pendiente',e&&e.status===403?'Esta vista no tiene acceso a los datos compartidos.':e&&e.name==='QuotaExceededError'?'Falta espacio. Exporta una copia; los cambios pendientes se conservan.':'No se ha completado. Tus cambios locales se conservan y se reintentará.');
      console.error('EQE sync:',e);
    }finally{busy=false}
  }
  function schedule(){if(applying)return;put('qeSync.dirty','1');clearTimeout(timer);timer=setTimeout(function(){sync()},900)}
  Storage.prototype.setItem=function(k,v){rawSet.call(this,k,v);if(this===localStorage&&!applying&&String(k).indexOf(P)===0)schedule()};
  Storage.prototype.removeItem=function(k){rawRemove.call(this,k);if(this===localStorage&&!applying&&String(k).indexOf(P)===0)schedule()};
  window.addEventListener('online',function(){sync()});
  window.addEventListener('offline',function(){status('☁ Sin conexión','Cambios guardados aquí; se enviarán al recuperar conexión.')});
  window.addEventListener('focus',function(){sync()});
  window.addEventListener('storage',function(e){if(e.key&&e.key.indexOf(P)===0)schedule()});
  document.addEventListener('visibilitychange',function(){if(!document.hidden)sync()});
  window.addEventListener('load',function(){
    var b=document.getElementById('cloudSyncNow');if(b)b.addEventListener('click',function(){sync()});
    try{recover()}catch(e){status('⚠ Recuperación pendiente','No se sincronizará hasta recuperar la escritura local.');return}
    sync();setInterval(function(){if(!document.hidden)sync()},15000);
  });
  window.eqeSyncNow=function(){return sync()};
})();
