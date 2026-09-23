const CACHE='quinto-elemento-v51';
const CORE=[
  './',
  './index.html',
  './manifest.webmanifest?v=51',
  './version.json',
  './pdf-chords-v44.json',
  './icon-192.png',
  './icon-512.png',
  './apple-touch-icon.png'
];

self.addEventListener('install',event=>{
  event.waitUntil(caches.open(CACHE).then(cache=>cache.addAll(CORE)));
  self.skipWaiting();
});

self.addEventListener('activate',event=>{
  event.waitUntil(
    caches.keys()
      .then(keys=>Promise.all(keys.filter(k=>k!==CACHE).map(k=>caches.delete(k))))
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


  if(url.pathname.startsWith('/api/')){
    event.respondWith(fetch(req,{cache:'no-store'}));
    return;
  }

  if(url.pathname.endsWith('version.json')){
    event.respondWith(
      fetchWithTimeout(req,2500)
        .then(resp=>{
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
        const copy=resp.clone();
        caches.open(CACHE).then(cache=>cache.put(req,copy));
        return resp;
      });
    })
  );
});
