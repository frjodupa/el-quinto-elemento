/* EQE — Revisión local de conflictos. Nunca sube, restaura ni reemplaza datos. */
(function(root){
  'use strict';
  var pending=null,holder=null;
  function describe(c){
    if(c&&c.type==='cross-field')return 'Letra y acordes de la misma canción';
    var key=String(c&&c.key||'');
    if(key==='quintoElemento.customSongs.v1')return 'Canciones nuevas o personalizadas';
    if(key==='quintoElemento.passes.v1')return 'Pases y orden de canciones';
    var match=/^quintoElemento[.]([^.]+)[.]v[0-9]+[.](\d+)$/.exec(key);
    var labels={chords:'Acordes',lyrics:'Letra',title:'Título',transpose:'Transposición'};
    if(match)return (labels[match[1]]||match[1])+' · canción '+match[2];
    return key.replace(/^quintoElemento[.]/,'Ajuste: ');
  }
  function makeDownload(which){
    if(!pending)return false;
    var payload={format:'eqe-conflict-safety-v1',origin:which,
      exportedAt:new Date().toISOString(),cloudRevision:pending.revision,
      data:which==='ipad-local'?pending.local:pending.remote};
    var blob=new Blob([JSON.stringify(payload,null,2)],{type:'application/json;charset=utf-8'});
    var url=URL.createObjectURL(blob);
    try{
      var a=document.createElement('a');
      a.href=url;a.download='EQE-'+which+'-'+Date.now()+'.json';
      document.body.appendChild(a);a.click();a.remove();
      return true;
    }finally{setTimeout(function(){URL.revokeObjectURL(url)},60000)}
  }
  function show(data){
    if(!data||!Array.isArray(data.conflicts)||!data.conflicts.length){hide();return}
    pending={conflicts:data.conflicts.slice(),local:data.local,remote:data.remote,revision:data.revision};
    if(!holder){
      holder=document.createElement('div');
      holder.id='qeSyncConflictReview';
      holder.setAttribute('role','region');
      holder.setAttribute('aria-label','Revisión de conflictos sin sobrescribir datos');
      holder.style.cssText='border:2px solid #b88b23;border-radius:12px;padding:14px;margin-top:12px;display:grid;gap:10px;';
      var target=document.getElementById('cloudSyncNow');
      if(target&&target.parentNode&&target.parentNode.parentNode){
        target.parentNode.parentNode.insertAdjacentElement('afterend',holder);
      }else document.body.appendChild(holder);
    }
    holder.replaceChildren();
    var title=document.createElement('strong');
    title.textContent='Revisión necesaria: '+pending.conflicts.length+' diferencias';
    holder.appendChild(title);
    var note=document.createElement('p');
    note.style.margin='0';
    note.textContent='No se ha sustituido ningún arreglo. Guarda las dos versiones antes de decidir qué conservar. Estas copias se generan únicamente en este dispositivo.';
    holder.appendChild(note);
    var list=document.createElement('ul');
    list.style.cssText='margin:0;padding-left:20px;max-height:180px;overflow:auto;';
    pending.conflicts.slice(0,25).forEach(function(c){
      var li=document.createElement('li');li.textContent=describe(c);list.appendChild(li);
    });
    holder.appendChild(list);
    if(pending.conflicts.length>25){
      var more=document.createElement('small');
      more.textContent='Y '+(pending.conflicts.length-25)+' diferencias adicionales';
      holder.appendChild(more);
    }
    var controls=document.createElement('div');
    controls.style.cssText='display:flex;gap:8px;flex-wrap:wrap;';
    [['Guardar ajustes de este dispositivo','ipad-local'],['Guardar copia de la nube','cloud-remote']].forEach(function(x){
      var btn=document.createElement('button');btn.type='button';btn.textContent=x[0];
      btn.addEventListener('click',function(){makeDownload(x[1])});
      controls.appendChild(btn);
    });
    holder.appendChild(controls);
    var limit=document.createElement('small');
    limit.textContent='Las diferencias no se fusionarán automáticamente. La resolución guiada se habilitará cuando se verifique el acceso protegido a Cloudflare.';
    holder.appendChild(limit);
  }
  function hide(){pending=null;if(holder){holder.remove();holder=null}}
  root.QESyncReview={show:show,hide:hide,describe:describe};
})(typeof window!=='undefined'?window:globalThis);
