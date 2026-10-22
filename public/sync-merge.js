/* Shared by the PWA and Node regression tests. No network or storage effects. */
(function(root,factory){
  if(typeof module==='object'&&module.exports)module.exports=factory();
  else root.EQESyncMerge=factory();
})(typeof globalThis!=='undefined'?globalThis:this,function(){
  'use strict';
  var PREFIX='quintoElemento.', CUSTOM=PREFIX+'customSongs.v1', PASSES=PREFIX+'passes.v1';
  function parse(v){try{return JSON.parse(v)}catch(e){return v}}
  function stable(v){
    if(v===undefined)return 'undefined';
    if(Array.isArray(v))return '['+v.map(stable).join(',')+']';
    if(v&&typeof v==='object')return '{'+Object.keys(v).sort().map(function(k){return JSON.stringify(k)+':'+stable(v[k])}).join(',')+'}';
    return JSON.stringify(v);
  }
  function equal(a,b){return stable(a)===stable(b)}
  function split(state,baseCount){
    var units={};
    Object.keys(state||{}).forEach(function(k){
      if(k.indexOf(PREFIX)!==0)return;
      var v=state[k];
      if(typeof v!=='string')throw new Error('Valor de sincronización no válido: '+k);
      if(k===CUSTOM||k===PASSES)return;
      var m=/^quintoElemento\.(?:lyrics\.v1|chords\.v2|title\.v1|artist\.v1|transpose\.v1|fontSize\.song|autoScrollSpeed\.song)\.(\d+)$/.exec(k);
      var id=m?'song:'+m[1]:'key:'+k;
      // Only structured storage records are JSON. A lyric can itself be a
      // quoted phrase, "null" or a number; never reinterpret that text.
      (units[id]||(units[id]={}))[k]=(k.indexOf(PREFIX+'chords.')===0||k.indexOf(PREFIX+'internetImportBackup.')===0)?parse(v):v;
    });
    if(Object.prototype.hasOwnProperty.call(state||{},CUSTOM)){
      var custom=parse(state[CUSTOM]);
      if(!Array.isArray(custom)||custom.some(function(s){return !s||typeof s.title!=='string'||typeof s.text!=='string'}))throw new Error('Catálogo no válido');
      custom.forEach(function(s,i){(units['song:'+(baseCount+i)]||(units['song:'+(baseCount+i)]={})).custom=s});
    }
    if(Object.prototype.hasOwnProperty.call(state||{},PASSES)){
      var passes=parse(state[PASSES]),seen={};
      if(!Array.isArray(passes))throw new Error('Pases no válidos');
      passes.forEach(function(p,i){
        if(!p||typeof p.id!=='string'||seen[p.id]||!Array.isArray(p.songs))throw new Error('Identidad de pase no válida');
        seen[p.id]=true;units['pass:'+p.id]={pass:p,order:i};
      });
    }
    return units;
  }
  function join(units,baseCount){
    var state={},custom=[],passes=[];
    Object.keys(units).forEach(function(id){
      var u=units[id];if(!u)return;
      if(id.indexOf('pass:')===0){passes.push(u);return;}
      Object.keys(u).forEach(function(k){
        if(k==='custom'){custom[Number(id.slice(5))-baseCount]=u[k];return;}
        var v=u[k];state[k]=typeof v==='string'?v:JSON.stringify(v);
      });
    });
    for(var i=0;i<custom.length;i++)if(!custom[i])throw new Error('No se puede desplazar el identificador de una canción');
    if(custom.length)state[CUSTOM]=JSON.stringify(custom);
    if(passes.length){passes.sort(function(a,b){return a.order-b.order||a.pass.id.localeCompare(b.pass.id)});state[PASSES]=JSON.stringify(passes.map(function(p){return p.pass}));}
    return state;
  }
  function merge(base,local,remote,baseCount,choices){
    var b=base===null?null:split(base,baseCount),l=split(local,baseCount),r=split(remote,baseCount),out={},conflicts=[];
    var collision=Object.keys(l).some(function(id){
      return id.indexOf('song:')===0&&l[id].custom&&r[id]&&r[id].custom&&
        (!b||!b[id]||!b[id].custom)&&l[id].custom.title!==r[id].custom.title;
    });
    if(collision){
      // New songs created offline can claim the same legacy numeric id.
      // Never attach one side's pass references to the other side's song.
      var selected=choices&&choices.catalogue;
      if(selected==='local'||selected==='remote')return {data:join(selected==='local'?l:r,baseCount),conflicts:[]};
      return {data:null,conflicts:[{id:'catalogue',base:base,local:local,remote:remote}]};
    }
    var ids=new Set(Object.keys(l).concat(Object.keys(r),Object.keys(b||{})));
    ids.forEach(function(id){
      var bv=b&&b[id],lv=l[id],rv=r[id],chosen;
      if(equal(lv,rv))chosen=lv;
      else if(b!==null&&equal(lv,bv))chosen=rv;
      else if(b!==null&&equal(rv,bv))chosen=lv;
      else if(b===null&&lv===undefined)chosen=rv;
      else if(b===null&&rv===undefined)chosen=lv;
      else {
        var choice=choices&&choices[id];
        if(choice==='local')chosen=lv;
        else if(choice==='remote')chosen=rv;
        else {conflicts.push({id:id,base:bv,local:lv,remote:rv});chosen=lv;}
      }
      if(chosen!==undefined)out[id]=chosen;
    });
    // A simultaneous catalogue append can assign the same numeric song id to
    // different songs. Treat the complete song as one conflict, including its
    // lyric/chord coordinates. No chord-by-chord or line-by-line auto merge.
    var data=conflicts.length?null:join(out,baseCount);
    if(data){
      var count=baseCount+(parse(data[CUSTOM])||[]).length;
      (parse(data[PASSES])||[]).forEach(function(p){p.songs.forEach(function(i){if(!Number.isInteger(i)||i<0||i>=count)throw new Error('Pase con referencia de canción no válida')})});
    }
    return {data:data,conflicts:conflicts};
  }
  function sameState(a,b){return equal(split(a,0),split(b,0))}
  return {merge:merge,split:split,stable:stable,equal:equal,sameState:sameState};
});
