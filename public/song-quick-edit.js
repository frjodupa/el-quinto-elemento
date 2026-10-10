/* EQE v79 · editor completo por canción; reutiliza los editores existentes. */
(function(){
  "use strict";
  function init(){
    var view=document.getElementById("view");
    var launcher=document.getElementById("quickEditSongBtn");
    var menu=document.getElementById("quickEditMenu");
    var lyricsBtn=document.getElementById("quickEditLyricsBtn");
    var titleBtn=document.getElementById("quickEditTitleBtn");
    var chordsBtn=document.getElementById("quickEditChordsBtn");
    var introBtn=document.getElementById("quickEditIntroBtn");
    var instrumentalBtn=document.getElementById("quickEditInstrumentalBtn");
    var editBar=document.getElementById("quickChordBar");
    var done=document.getElementById("quickChordSave");
    var undo=document.getElementById("quickChordUndo");
    var intro=document.getElementById("quickChordIntro");
    var instrumental=document.getElementById("quickChordInstrumental");
    if(!view||!launcher||!menu||!lyricsBtn||!titleBtn||!chordsBtn||!introBtn||!instrumentalBtn||!editBar||!done)return;

    var nativeChord=document.getElementById("chordMode");
    var nativeSave=document.getElementById("saveChordEdit");
    var nativeLyrics=document.getElementById("editLyrics");
    var nativeUndo=document.getElementById("undoChordBtn");
    var nativeIntro=document.getElementById("introTool");
    var nativeInstrumental=document.getElementById("instrumentTool");
    if(!nativeChord||!nativeSave||!nativeLyrics||!nativeUndo||!nativeIntro||!nativeInstrumental)return;

    function isActive(){
      return view.classList.contains("on")&&view.classList.contains("editing");
    }
    function closeMenu(){
      menu.hidden=true;
      launcher.setAttribute("aria-expanded","false");
    }
    function sync(){
      var active=isActive();
      editBar.hidden=!active;
      launcher.classList.toggle("quickEditingActive",active);
      launcher.setAttribute("aria-pressed",active?"true":"false");
      launcher.setAttribute("aria-label",active?"Editar canción (edición de acordes activa)":"Editar letra y acordes");
      chordsBtn.textContent=active?"✓ Guardar y salir de acordes":"♫ Editar acordes sobre las palabras";
      undo.disabled=nativeUndo.disabled;
      intro.disabled=!active;
      instrumental.disabled=!active;
      if(!view.classList.contains("on"))closeMenu();
    }
    function saveAndExit(){
      if(isActive())nativeSave.click();
      closeMenu();
      sync();
    }
    function selectLyrics(){
      closeMenu();
      if(isActive())saveAndExit();
      nativeLyrics.click();
      sync();
    }
    function selectTitle(){
      selectLyrics();
      var title=document.getElementById("lyricEditorSongTitle");
      if(title){
        title.focus();
        title.select();
      }
    }
    function selectChords(){
      closeMenu();
      if(isActive()){saveAndExit();return;}
      nativeChord.click();
      sync();
    }
    function selectIntro(){
      closeMenu();
      if(!isActive())nativeChord.click();
      sync();
      nativeIntro.click();
    }
    function selectInstrumental(){
      closeMenu();
      if(!isActive())nativeChord.click();
      sync();
      nativeInstrumental.click();
    }
    function trigger(native){
      if(!isActive())return;
      native.click();
      sync();
    }

    launcher.addEventListener("click",function(e){
      e.stopPropagation();
      if(!view.classList.contains("on"))return;
      menu.hidden=!menu.hidden;
      launcher.setAttribute("aria-expanded",String(!menu.hidden));
      if(!menu.hidden)lyricsBtn.focus();
    });
    lyricsBtn.addEventListener("click",selectLyrics);
    titleBtn.addEventListener("click",selectTitle);
    chordsBtn.addEventListener("click",selectChords);
    introBtn.addEventListener("click",selectIntro);
    instrumentalBtn.addEventListener("click",selectInstrumental);
    done.addEventListener("click",saveAndExit);
    undo.addEventListener("click",function(){trigger(nativeUndo);});
    intro.addEventListener("click",function(){trigger(nativeIntro);});
    instrumental.addEventListener("click",function(){trigger(nativeInstrumental);});

    document.addEventListener("click",function(event){
      if(!menu.hidden&&!event.target.closest(".directSongQuickActions"))closeMenu();
    });
    // Capture prevents the legacy Escape shortcut from closing the song when
    // the quick menu is the thing being dismissed.
    document.addEventListener("keydown",function(event){
      if(event.key==="Escape"&&!menu.hidden){
        event.preventDefault();event.stopImmediatePropagation();closeMenu();
        launcher.focus();
      }
    },true);

    var viewObserver=new MutationObserver(sync);
    viewObserver.observe(view,{attributes:true,attributeFilter:["class"]});
    var undoObserver=new MutationObserver(sync);
    undoObserver.observe(nativeUndo,{attributes:true,attributeFilter:["disabled"]});
    sync();
  }
  if(document.readyState==="loading")document.addEventListener("DOMContentLoaded",init,{once:true});
  else init();
})();
