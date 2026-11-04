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
      if(chosen===null){conflicts.push({key:k,base:b.exists?b.value:null,local:l.exists?l.value:null,remote:r.exists?r.value:null});return}
      if(chosen.exists)result[k]=chosen.value;
    });
    // Arrays of custom songs use positional indices in chord/lyric/pass keys.
    // Concurrent independent appends require a separate index migration and
    // must never be auto-concatenated or reordered by a generic JSON merge.
    SPECIAL.forEach(function(k){
      if(!conflicts.some(function(c){return c.key===k}))return;
    });
    return {merged:result,conflicts:conflicts,hasConflicts:conflicts.length>0};
  }
  function safeJson(value){try{var x=JSON.parse(value);return x&&typeof x==='object'&&!Array.isArray(x)?x:null}catch(e){return null}}
  root.QESyncEngine={merge:merge,clean:clean,safeJson:safeJson};
})(typeof window!=='undefined'?window:globalThis);
