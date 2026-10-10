const {chromium}=require('playwright');
const fs=require('node:fs');
(async()=>{
  fs.mkdirSync('ui-review',{recursive:true});
  const browser=await chromium.launch({headless:true});
  const context=await browser.newContext({
    viewport:{width:390,height:844},serviceWorkers:'allow',isMobile:true,hasTouch:true
  });
  const page=await context.newPage();
  const errors=[];
  page.on('pageerror',e=>errors.push(String(e)));
  await page.goto('http://127.0.0.1:4173/',{waitUntil:'load'});
  await page.waitForFunction(async()=>{
    if(!('serviceWorker' in navigator))return false;
    const cacheNames=await caches.keys();
    return cacheNames.some(name=>name==='quinto-elemento-v76');
  },{timeout:20000});
  await page.waitForTimeout(500);
  const online=await page.evaluate(async()=>{
    const c=await caches.open('quinto-elemento-v76');
    const keys=(await c.keys()).map(r=>new URL(r.url).pathname);
    return {
      cache:'quinto-elemento-v76',
      swControlled:!!navigator.serviceWorker.controller,
      keys,
      required:['/index.html','/premium.css','/premium-icons.js',
        '/premium-icon-180.png','/premium-icon-192.png',
        '/premium-icon-512.png','/premium-icon-maskable-512.png'].map(p=>({path:p,present:keys.includes(p)}))
    };
  });
  if(online.required.some(x=>!x.present))throw Error('Precache missing '+JSON.stringify(online.required));
  await context.setOffline(true);
  await page.reload({waitUntil:'domcontentloaded',timeout:12000});
  await page.waitForTimeout(400);
  const offline=await page.evaluate(()=>({
    title:document.title,
    songs:document.querySelectorAll('#grid .songBtn').length,
    premiumIcons:document.querySelectorAll('.premium-svg').length,
    hasPremiumCSS:getComputedStyle(document.querySelector('.directHome')).backgroundImage.includes('gradient'),
    strayNewline:document.body.firstChild?.nodeType===Node.TEXT_NODE&&String(document.body.firstChild.textContent).trim()==='\\n'
  }));
  if(offline.songs<60||offline.premiumIcons<5||!offline.hasPremiumCSS||offline.strayNewline)throw Error('Offline rendering regression '+JSON.stringify(offline));
  fs.writeFileSync('ui-review/offline-validation.json',JSON.stringify({online,offline,pageErrors:errors},null,2));
  console.log('OFFLINE_OK '+JSON.stringify({cachedResources:online.keys.length,songs:offline.songs,premiumIcons:offline.premiumIcons}));
  await browser.close();
})().catch(e=>{console.error(e.stack||String(e));process.exitCode=1});
