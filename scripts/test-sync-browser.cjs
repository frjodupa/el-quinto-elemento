const {chromium,webkit}=require('playwright');
const http=require('node:http'),fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const root=path.resolve('public'),P='quintoElemento.',key=i=>P+'lyrics.v1.'+i;
const state={data:{[key(0)]:'BASE A',[key(1)]:'BASE B',[key(2)]:'BASE C'},ts:100,puts:0};
const server=http.createServer(async(req,res)=>{
 const url=new URL(req.url,'http://localhost');res.setHeader('Cache-Control','no-store');
 if(url.pathname==='/api/sync'){
  res.setHeader('Content-Type','application/json');
  if(req.method==='GET')return res.end(JSON.stringify({data:state.data,updatedAt:state.ts}));
  let raw='';for await(const c of req)raw+=c;const body=JSON.parse(raw);
  if(body.expectedUpdatedAt!==state.ts){res.statusCode=409;return res.end(JSON.stringify({error:'STALE_SNAPSHOT'}))}
  state.data=body.data;state.ts++;state.puts++;return res.end(JSON.stringify({updatedAt:state.ts}));
 }
 if(url.pathname.startsWith('/api/')){res.setHeader('Content-Type','application/json');return res.end('{"backups":[]}')}
 const target=path.resolve(root,'.'+(url.pathname==='/'?'/index.html':url.pathname));
 if(!target.startsWith(root+path.sep)){res.statusCode=403;return res.end()}
 if(!fs.existsSync(target)){res.statusCode=404;return res.end()}
 const mime={'.html':'text/html','.js':'application/javascript','.css':'text/css','.json':'application/json','.webmanifest':'application/manifest+json'};res.setHeader('Content-Type',mime[path.extname(target)]||'application/octet-stream');res.end(fs.readFileSync(target));
});
(async()=>{
 await new Promise(r=>server.listen(0,'127.0.0.1',r));const origin='http://127.0.0.1:'+server.address().port;
 const browser=await (process.env.EQE_BROWSER==='webkit'?webkit:chromium).launch({headless:true});
 try{
 const contexts=[],pages=[],errors=[];
 for(let i=0;i<3;i++){
  const context=await browser.newContext({serviceWorkers:'block',viewport:{width:i===1?1280:820,height:1100}});
  const page=await context.newPage();page.on('pageerror',e=>errors.push(e.message));
  await page.route('**/*',route=>new URL(route.request().url()).origin===origin?route.continue():route.abort());
  // Known shared baseline; isolate migration conflicts from this convergence test.
  await page.addInitScript(({data,ts})=>{Object.entries(data).forEach(([k,v])=>localStorage.setItem(k,v));localStorage.setItem('qeSync.base.v2',JSON.stringify({data,updatedAt:ts}))},{data:state.data,ts:state.ts});
  await page.goto(origin);await page.waitForFunction(()=>typeof window.eqeSyncNow==='function');
  contexts.push(context);pages.push(page);
 }
 assert.equal(await pages[0].locator('.uiVersion').textContent(),'v98');
 for(let i=0;i<3;i++){await pages[i].evaluate(({key,text})=>localStorage.setItem(key,text),{key:key(i),text:['IPAD','MAC','IPHONE'][i]})}
 for(const p of pages)await p.evaluate(()=>window.eqeSyncNow());
 for(const p of pages)await p.evaluate(()=>window.eqeSyncNow());
 for(const p of pages){const actual=await p.evaluate(keys=>keys.map(k=>localStorage.getItem(k)),[key(0),key(1),key(2)]);assert.deepEqual(actual,['IPAD','MAC','IPHONE'])}
 console.log('PASS browser: three isolated devices converge; visible v98');
 await pages[0].evaluate(()=>localStorage.setItem('quintoElemento.lyrics.v1.0','LEFT'));
 await pages[1].evaluate(()=>localStorage.setItem('quintoElemento.lyrics.v1.0','RIGHT'));
 await pages[0].evaluate(()=>window.eqeSyncNow());await pages[1].evaluate(()=>window.eqeSyncNow());
 assert.equal(await pages[1].locator('#eqeSyncConflicts details').count(),1);
 assert.equal(await pages[1].evaluate(()=>localStorage.getItem('quintoElemento.lyrics.v1.0')),'RIGHT');
 await pages[1].locator('#settingsIndexBtn').click();
 const details=pages[1].locator('#eqeSyncConflicts details');await details.locator('summary').click();
 await pages[1].getByRole('button',{name:'Conservar este dispositivo',exact:true}).click();
 await pages[1].getByRole('button',{name:'Aplicar selección y sincronizar',exact:true}).click();
 await pages[1].waitForFunction(()=>!document.querySelector('#eqeSyncConflicts'));
 assert.equal(state.data[key(0)],'RIGHT');console.log('PASS browser: conflict UI retains both variants and applies explicit selection');
 await contexts[2].setOffline(true);await pages[2].evaluate(()=>localStorage.setItem('quintoElemento.lyrics.v1.2','OFFLINE IPHONE'));
 await contexts[2].setOffline(false);await pages[2].evaluate(()=>window.eqeSyncNow());
 await pages[0].evaluate(()=>window.eqeSyncNow());assert.equal(await pages[0].evaluate(()=>localStorage.getItem('quintoElemento.lyrics.v1.2')),'OFFLINE IPHONE');
 console.log('PASS browser: offline edits survive reconnection');
 assert.deepEqual(errors,[]);console.log('PASS browser: no uncaught page errors');
 }finally{await browser.close();server.close()}
})().catch(e=>{console.error(e);server.close();process.exitCode=1});
