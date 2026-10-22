import assert from 'node:assert/strict';
import worker from '../src/worker.js';
let access=0;
const env={DB:{prepare(){access++;throw new Error('Production DB must not be touched')}},ASSETS:{fetch(){return new Response('asset')}}};
for(const hostname of ['8c49a00c-crimson-rice-1fe1.joseduqueparedes.workers.dev','fix-eqe-sync-version-20261022-crimson-rice-1fe1.joseduqueparedes.workers.dev']){
 for(const [method,path] of [['GET','/api/sync'],['PUT','/api/sync'],['GET','/api/backups'],['POST','/api/backups'],['POST','/api/recover-la-pasma']]){
  const response=await worker.fetch(new Request('https://'+hostname+path,{method}),env);
  assert.equal(response.status,403);assert.equal((await response.json()).code,'PREVIEW_ISOLATED');
 }
}
assert.equal(access,0);
assert.equal((await worker.fetch(new Request('https://crimson-rice-1fe1.joseduqueparedes.workers.dev/style.css'),env)).status,200);
console.log('PASS preview guard: 10 API calls blocked before D1; production assets still served');
