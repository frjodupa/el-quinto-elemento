/* EQE v82 · edición directa y simple dentro de la canción. */
(function(){
  "use strict";
  function init(){
    var view=document.getElementById("view");
    var launcher=document.getElementById("quickEditSongBtn");
    var menu=document.getElementById("quickEditMenu");
    var editBar=document.getElementById("quickChordBar");
    var chords=document.getElementById("quickChordChords");
    var lyrics=document.getElementById("quickChordLyrics");
    var copy=document.getElementById("quickChordCopy");
    var paste=document.getElementById("quickChordPaste");
    var duplicate=document.getElementById("quickChordDuplicate");
    var undo=document.getElementById("quickChordUndo");
    var done=document.getElementById("quickChordSave");

    var nativeChord=document.getElementById("chordMode");
    var nativeSave=document.getElementById("saveChordEdit");
    var nativeLyrics=document.getElementById("editLyrics");
    var nativeUndo=document.getElementById("undoChordBtn");

    if(!view||!launcher||!editBar||!chords||!lyrics||!copy||!paste||!undo||!done||
       !nativeChord||!nativeSave||!nativeLyrics||!nativeUndo)return;

    function isActive(){
      return view.classList.contains("on")&&view.classList.contains("editing");
    }
    function enterEdit(){
      if(!view.classList.contains("on"))return;
      if(!isActive())nativeChord.click();
      if(menu)menu.hidden=true;
      launcher.setAttribute("aria-expanded","false");
      sync();
    }
    function resetCopyPaste(){
      try{
        if(typeof cancelBlockDuplicate==="function" && window.blockDuplicateMode)cancelBlockDuplicate();
      }catch(e){}
      paste.disabled=true;
      copy.classList.remove("active");
      paste.classList.remove("active");
    }
    function sync(){
      var active=isActive();
      editBar.hidden=!active;
      launcher.classList.toggle("quickEditingActive",active);
      launcher.setAttribute("aria-pressed",active?"true":"false");
      launcher.setAttribute("aria-expanded","false");
      launcher.querySelector("span").textContent=active?"Editando":"Editar";
      chords.classList.toggle("active",active);
      undo.disabled=nativeUndo.disabled;
      if(typeof blockDuplicateMode!=="undefined"){
        copy.classList.toggle("active",!!blockDuplicateMode&&!blockDuplicateArmedForPaste);
        paste.classList.toggle("active",!!blockDuplicateMode&&!!blockDuplicateArmedForPaste);
        paste.disabled=!(blockDuplicateMode && blockDuplicateStart!==null && !blockDuplicateArmedForPaste);
      }
      if(menu)menu.hidden=true;
    }

    launcher.addEventListener("click",function(e){
      e.preventDefault();
      e.stopImmediatePropagation();
      enterEdit();
    },true);

    chords.addEventListener("click",function(){
      enterEdit();
      try{
        blockDuplicateMode=false;
        blockDuplicateArmedForPaste=false;
        blockDuplicateStart=null;
        blockDuplicateEnd=null;
        if(typeof updateDuplicateChordBanner==="function")updateDuplicateChordBanner();
        if(typeof renderLyrics==="function")renderLyrics();
      }catch(e){}
      sync();
    });

    lyrics.addEventListener("click",function(){
      enterEdit();
      nativeLyrics.click();
      sync();
    });

    if(duplicate)duplicate.addEventListener("click",function(){
      enterEdit();
      if(typeof startBlockDuplicate==="function")startBlockDuplicate();
      sync();
    });
    copy.addEventListener("click",function(){
      enterEdit();
      if(typeof startBlockDuplicate!=="function")return;
      startBlockDuplicate();
      paste.disabled=true;
      copy.classList.add("active");
      paste.classList.remove("active");
      sync();
    });

    paste.addEventListener("click",function(){
      enterEdit();
      if(typeof blockDuplicateMode==="undefined"||!blockDuplicateMode||typeof blockDuplicateStart==="undefined"||blockDuplicateStart===null){
        alert("Primero pulsa Copiar y selecciona la primera y la última línea del bloque.");
        return;
      }
      if(blockDuplicateEnd===null)blockDuplicateEnd=blockDuplicateStart;
      blockDuplicateArmedForPaste=true;
      if(typeof updateDuplicateChordBanner==="function")updateDuplicateChordBanner();
      if(typeof renderLyrics==="function")renderLyrics();
      copy.classList.remove("active");
      paste.classList.add("active");
      paste.disabled=true;
      sync();
    });

    undo.addEventListener("click",function(){
      if(!nativeUndo.disabled)nativeUndo.click();
      sync();
    });

    done.addEventListener("click",function(){
      try{
        blockDuplicateMode=false;
        blockDuplicateArmedForPaste=false;
        blockDuplicateStart=null;
        blockDuplicateEnd=null;
      }catch(e){}
      if(isActive())nativeSave.click();
      if(menu)menu.hidden=true;
      sync();
    });

    var observer=new MutationObserver(sync);
    observer.observe(view,{attributes:true,attributeFilter:["class"]});
    var undoObserver=new MutationObserver(sync);
    undoObserver.observe(nativeUndo,{attributes:true,attributeFilter:["disabled"]});
    view.addEventListener("click",function(){
      if(typeof blockDuplicateMode!=="undefined" && blockDuplicateMode)setTimeout(sync,0);
    },true);
    var settings=document.getElementById("settingsModal");
    if(settings){
      ["settingsDetectRepeats","settingsReferenceText","settingsClearReferences",
       "settingsPdfAllChords","qeRepairAunque","settingsClearChords",
       "].forEach(function(id){
        var item=document.getElementById(id);
        if(item)item.hidden=true;
      });
      var style=document.createElement("style");
      style.textContent="#settingsModal .settingsGrid button[hidden]{display:none!important}";
      document.head.appendChild(style);
    }
    document.addEventListener("click",function(){
      if(menu)menu.hidden=true;
    });
    sync();
  }
  if(document.readyState==="loading")document.addEventListener("DOMContentLoaded",init,{once:true});
  else init();
})();