/* EQE premium navigation icons; local inline SVG, no CDN or runtime network. */
(function(){
  "use strict";
  var shapes={
    "sliders":'<path d="M4 7h9m4 0h3M4 17h3m4 0h9"/><circle cx="15" cy="7" r="2"/><circle cx="9" cy="17" r="2"/>',
    "list-music":'<path d="M3 6h12M3 12h9M3 18h9M17 14V5l4-1v10"/><circle cx="15.5" cy="17.5" r="2.5"/>',
    "arrow-left":'<path d="m12 19-7-7 7-7M5 12h14"/>',
    "chevron-left":'<path d="m15 18-6-6 6-6"/>',
    "chevron-right":'<path d="m9 18 6-6-6-6"/>',
    "plus":'<path d="M12 5v14M5 12h14"/>',
    "pencil":'<path d="m16 5 3 3M4 20l4.3-1 11-11a2 2 0 0 0-3-3l-11 11L4 20Z"/>',
    "music":'<path d="M9 18V5l12-2v13"/><circle cx="6" cy="18" r="3"/><circle cx="18" cy="16" r="3"/>',
    "download":'<path d="M12 3v12m-5-5 5 5 5-5M4 17v3h16v-3"/>',
    "archive":'<path d="M3 4h18v5H3zM5 9v11h14V9M10 13h4"/>',
    "refresh":'<path d="M20 7a8 8 0 0 0-14-2L4 7m0-4v4h4M4 17a8 8 0 0 0 14 2l2-2m0 4v-4h-4"/>',
    "cloud":'<path d="M8 18H6a4 4 0 1 1 1-7.9A6 6 0 0 1 19 12a3 3 0 0 1 0 6h-4"/>',
    "share":'<circle cx="18" cy="5" r="2"/><circle cx="6" cy="12" r="2"/><circle cx="18" cy="19" r="2"/><path d="m8 11 8-5m-8 8 8 4"/>',
    "shield":'<path d="M12 22s8-4 8-11V5l-8-3-8 3v6c0 7 8 11 8 11Z"/><path d="m9 12 2 2 4-4"/>',
    "check":'<path d="m4 12 5 5L20 6"/>',
    "x":'<path d="M18 6 6 18M6 6l12 12"/>',
    "sun":'<circle cx="12" cy="12" r="4"/><path d="M12 2v2m0 16v2M4.93 4.93l1.42 1.42m11.3 11.3 1.42 1.42M2 12h2m16 0h2M4.93 19.07l1.42-1.42m11.3-11.3 1.42-1.42"/>',
    "book":'<path d="M12 7c-3-2-6-2-9-1v13c3-1 6-1 9 1m0-13c3-2 6-2 9-1v13c-3-1-6-1-9 1M12 7v13"/>',
    "users":'<circle cx="9" cy="8" r="3"/><path d="M2 20v-2a7 7 0 0 1 14 0v2M16 5a3 3 0 0 1 0 6m2 3a5 5 0 0 1 4 5v1"/>',
    "play":'<path d="m8 5 11 7-11 7V5Z"/>',
    "search":'<circle cx="11" cy="11" r="7"/><path d="m20 20-4-4"/>',
    "trash":'<path d="M3 6h18M8 6V4h8v2m-9 0 1 14h8l1-14M10 10v7m4-7v7"/>'
  };
  function svg(name){
    if(!shapes[name])return null;
    var wrap=document.createElement("span");
    wrap.innerHTML='<svg aria-hidden="true" class="premium-svg" viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" xmlns="http://www.w3.org/2000/svg">'+shapes[name]+'</svg>';
    return wrap.firstElementChild;
  }
  function icon(id,name,label,only){
    var btn=document.getElementById(id);
    if(!btn||btn.querySelector(".premium-svg"))return;
    var vector=svg(name);
    if(!vector)return;
    btn.classList.add("premium-icon-button");
    if(only){
      btn.classList.add("icon-only");
      btn.replaceChildren(vector);
      btn.setAttribute("aria-label",label||btn.getAttribute("aria-label")||"Abrir");
      btn.title=label||btn.title||"";
      return;
    }
    btn.replaceChildren(vector,document.createTextNode(label||btn.textContent.trim()));
  }
  function attach(){
    [
      ["settingsIndexBtn","sliders","Ajustes",true],
      ["managePassesBtn","list-music","Pases",false],
      ["back","arrow-left","Índice",false],
      ["prev","chevron-left","Canción anterior",true],
      ["next","chevron-right","Canción siguiente",true],
      ["settingsBtn","sliders","Ajustes",true],
      ["newPassFromManager","plus","Nuevo pase",false],
      ["passesClose","x","Cerrar pases",true],
      ["passDetailClose","x","Cerrar pase",true],
      ["settingsClose","x","Cerrar ajustes",true],
      ["settingsAdvancedToggle","sliders","Avanzado",false],
      ["settingsChordMode","music","Acordes",false],
      ["settingsEditLyrics","pencil","Editar canción",false],
      ["settingsIntro","plus","Intro",false],
      ["settingsInstrumental","music","Instrumental",false],
      ["settingsTheme","sun","Cambiar tema",false],
      ["settingsNewSong","plus","Nueva canción",false],
      ["settingsQuickExport","download","Exportar JSON",false],
      ["settingsBackup","archive","Copias e importar",false],
      ["settingsUpdate","refresh","Actualizar aplicación",false],
      ["settingsShareAccess","users","Compartir acceso",false],
      ["createCloudBackup","shield","Crear copia",false]
    ].forEach(function(spec){icon.apply(null,spec)});
    // Safari does not need a third-party icon font; direct action icons stay accessible offline.
    var search=document.getElementById("q");
    if(search){search.setAttribute("aria-label","Buscar canción en el cancionero");search.setAttribute("enterkeyhint","search");}
    var panel=document.getElementById("settingsModal");
    if(panel)panel.setAttribute("aria-label","Ajustes del cancionero");
    var passes=document.getElementById("passesModal");
    if(passes)passes.setAttribute("aria-label","Pases musicales");
  }
  if(document.readyState==="loading"){
    document.addEventListener("DOMContentLoaded",attach,{once:true});
  }else attach();
})();
