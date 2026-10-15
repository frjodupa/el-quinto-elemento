// Entorno aislado: no contiene bindings de producción ni acceso a D1.
export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    if (url.pathname.startsWith('/api/') || url.pathname === '/export') {
      return Response.json({error:'Entorno de pruebas sin sincronización en la nube'}, {status: 403, headers:{'Cache-Control':'no-store'}});
    }
    return env.ASSETS.fetch(request);
  }
};
