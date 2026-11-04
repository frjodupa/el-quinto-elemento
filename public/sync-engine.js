/* GITOP EQE v2: pure, conservative three-way reconciliation.
   Does not perform network writes or modify localStorage. */
(function(root){
  'use strict';
  var PREFIX='quintoElemento.';
  var SPECIAL=['quintoElemento.customSongs.v1','quintoElemento.passes.v1'];
  function own(o,k){return Object.prototype.hasOwnProperty.call(o,k)}
  function clean(s){var out={};if(!s||typeof s!=='object'||Array.isArray(s))return out;
    Object.keys(s).forEach(function(k){if(k.indexOf(PREFIX)===0&&typeof s[k]==='string')out[k]=s[k]});
    return out;
  }
  function eql(a,b){return a.exists===b.exists && (!a.exists||a.value===b.value)}
  function val(obj,key){return {exists:own(obj,key),value:obj[key]}}
  function jsonArray(raw){try{var v=JSON.parse(raw);return Array.isArray(v)?v:null}catch(e){return null}}
  function prefixArray(a,b){
    return a.length<=b.length&&a.every(function(v,i){return JSON.stringify(v)===JSON.stringify(b[i])});
  }
  function isRecord(x){return x!==null&&typeof x==='object'&&!Array.isArray(x)}
  function same(a,b){return JSON.stringify(a)===JSON.stringify(b)}
  function mergeRecord(base,local,remote){
    if(!isRecord(base)||!isRecord(local)||!isRecord(remote))return null;
    var out={},conflict=false;
    var keys=new Set(Object.keys(base).concat(Object.keys(local),Object.keys(remote)));
    keys.forEach(function(k){
      var b=val(base,k),l=val(local,k),r=val(remote,k),selected=null;
      if(eql(l,r)||l.exists&&r.exists&&same(l.value,r.value))selected=l;
      else if(eql(l,b)||l.exists&&b.exists&&same(l.value,b.value))selected=r;
      else if(eql(r,b)||r.exists&&b.exists&&same(r.value,b.value))selected=l;
      else if(b.exists&&l.exists&&r.exists&&isRecord(b.value)&&isRecord(l.value)&&isRecord(r.value)){
        var nested=mergeRecord(b.value,l.value,r.value);
        if(nested!==null)selected={exists:true,value:nested};
      }
      if(selected===null){conflict=true;return}
      if(selected.exists)out[k]=selected.value;
    });
    return conflict?null:out;
  }
  function special(k,b,l,r){
    if(/^quintoElemento\\.chords\\.v2\\.\\d+$/.test(k)&&b.exists&&l.exists&&r.exists){
      var bc=safeJson(b.value),lc=safeJson(l.value),rc=safeJson(r.value);
      var merged=mergeRecord(bc,lc,rc);
      return merged===null?null:{exists:true,value:JSON.stringify(merged)};
    }

    // Only combine append-only lists when existing indices are guaranteed stable.
    if(k==='quintoElemento.customSongs.v1'){
      var la=jsonArray(l.value),ra=jsonArray(r.value);
      if(!la||!ra)return null;
      if(prefixArray(la,ra))return r;
      if(prefixArray(ra,la))return l;
      return null;
    }
    if(k==='quintoElemento.passes.v1'){
      var lp=jsonArray(l.value),rp=jsonArray(r.value);
      if(!lp||!rp)return null;
      var byId=new Map(),out=[];
      for(var i=0;i<lp.length;i++){
        if(!lp[i]||typeof lp[i].id!=='string'||byId.has(lp[i].id))return null;
        byId.set(lp[i].id,lp[i]);out.push(lp[i]);
      }
      for(var j=0;j<rp.length;j++){
        var pass=rp[j];if(!pass||typeof pass.id!=='string')return null;
        if(byId.has(pass.id)){
          if(JSON.stringify(byId.get(pass.id))!==JSON.stringify(pass))return null;
        }else{byId.set(pass.id,pass);out.push(pass)}
      }
      return {exists:true,value:JSON.stringify(out)};
    }
    return null;
  }
  function merge(base,local,remote){
    var known=base!==null && base!==undefined;
    base=clean(base);local=clean(local);remote=clean(remote);
    var result={},conflicts=[],keys=new Set(Object.keys(base).concat(Object.keys(local),Object.keys(remote)));
    keys.forEach(function(k){
      var b=val(base,k),l=val(local,k),r=val(remote,k),chosen=null;
      if(eql(l,r))chosen=l;
      else if(known){
        if(eql(l,b))chosen=r;
        else if(eql(r,b))chosen=l;
      } else if(!l.exists)chosen=r;
      else if(!r.exists)chosen=l;
      if(chosen===null&&l.exists&&r.exists)chosen=special(k,b,l,r);
      if(chosen===null){conflicts.push({key:k,base:b.exists?b.value:null,local:l.exists?l.value:null,remote:r.exists?r.value:null});return}
      if(chosen.exists)result[k]=chosen.value;
    });
    return {merged:result,conflicts:conflicts,hasConflicts:conflicts.length>0};
  }
  function safeJson(value){try{var x=JSON.parse(value);return x&&typeof x==='object'&&!Array.isArray(x)?x:null}catch(e){return null}}
  root.QESyncEngine={merge:merge,clean:clean,safeJson:safeJson};
})(typeof window!=='undefined'?window:globalThis);
