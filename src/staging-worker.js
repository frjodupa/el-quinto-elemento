// Independent preview: never bind to production D1 or permit cloud writes.
export default {
  async fetch(request,env){
    const url=new URL(request.url);
    if(url.pathname.startsWith('/api/')) return new Response(JSON.stringify({error:'Entorno de pruebas: sincronización remota desactivada'}),{status:503,headers:{'content-type':'application/json','cache-control':'no-store'}});
    return env.ASSETS.fetch(request);
  }
};
