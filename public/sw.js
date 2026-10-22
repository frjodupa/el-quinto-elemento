const CACHE='quinto-elemento-v98';
const CORE=[
  './',
  './index.html',
  './manifest.webmanifest?v=98',
  './version.json',
  './sync-merge.js?v=98',
  './sync-client.js?v=98',
  './pdf-chords-v44.json',
  './premium.css?v=98',
  './premium-icons.js?v=77',
  './song-quick-edit.js?v=98',
  './premium-icon-192.png?v=77',
  './premium-icon-512.png?v=77',
  './premium-icon-maskable-512.png?v=77',
  './premium-icon-180.png?v=77'
];

self.addEventListener('install',event=>{
  event.waitUntil(caches.open(CACHE).then(cache=>cache.addAll(CORE)));
  self.skipWaiting();
});

self.addEventListener('activate',event=>{
  event.waitUntil(
    caches.keys()
      .then(keys=>Promise.all(keys.filter(k=>k.indexOf('quinto-elemento-v')===0 && k!==CACHE).map(k=>caches.delete(k))))
      .then(()=>self.clients.claim())
  );
});

function fetchWithTimeout(req,ms){
  return new Promise((resolve,reject)=>{
    let done=false;
    const timer=setTimeout(()=>{
      if(done)return;
      done=true;
      reject(new Error('timeout'));
    },ms);
    fetch(req,{cache:'no-store'}).then(resp=>{
      if(done)return;
      done=true;
      clearTimeout(timer);
      resolve(resp);
    }).catch(err=>{
      if(done)return;
      done=true;
      clearTimeout(timer);
      reject(err);
    });
  });
}

self.addEventListener('fetch',event=>{
  if(event.request.method!=='GET')return;
  const req=event.request;
  const url=new URL(req.url);


  if(url.pathname.startsWith('/api/') || url.pathname==='/export'){
    event.respondWith(fetch(req,{cache:'no-store'}));
    return;
  }

  if(url.pathname.endsWith('version.json')){
    event.respondWith(
      fetchWithTimeout(req,2500)
        .then(resp=>{
          if(!resp.ok)throw new Error('Version HTTP '+resp.status);
          const copy=resp.clone();
          caches.open(CACHE).then(cache=>cache.put('./version.json',copy));
          return resp;
        })
        .catch(()=>caches.match('./version.json'))
    );
    return;
  }

  if(req.mode==='navigate'){
    event.respondWith(
      fetchWithTimeout(req,2500)
        .then(resp=>{
          if(!resp.ok)throw new Error('Navigation HTTP '+resp.status);
          const copy=resp.clone();
          caches.open(CACHE).then(cache=>cache.put('./index.html',copy));
          return resp;
        })
        .catch(()=>caches.match('./index.html'))
    );
    return;
  }

  event.respondWith(
    caches.match(req).then(cached=>{
      if(cached)return cached;
      return fetch(req).then(resp=>{
        if(!resp.ok)return resp;
        const copy=resp.clone();
        caches.open(CACHE).then(cache=>cache.put(req,copy));
        return resp;
      });
    })
  );
});

