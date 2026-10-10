const {chromium}=require('playwright');
const fs=require('node:fs');
(async()=>{
 fs.mkdirSync('ui-review', {recursive:true});
 const browser=await chromium.launch({headless:true});
 for (const [name,width,height] of [
   ['iphone-375',375,812],['iphone-390',390,844],['ipad-820',820,1180],['desktop-1280',1280,800]
 ]){
  const context=await browser.newContext({viewport:{width,height},isMobile:width<900,hasTouch:width<900,serviceWorkers:'block'});
  const page=await context.newPage();
  const errors=[],calls=[];
  page.on('pageerror',e=>errors.push(e.message));
  page.on('console',msg=>{if(msg.type()==='error')errors.push(msg.text())});
  await page.route('**/api/sync**',r=>r.fulfill({status:200,contentType:'application/json',body:JSON.stringify({ok:true,data:{}})}));
  await page.route('**/api/backups**',r=>r.fulfill({status:200,contentType:'application/json',body:JSON.stringify({ok:true,backups:[]})}));
  await page.route('**/api/song-search**',r=>{
    calls.push(new URL(r.request().url()).searchParams.get('q'));
    return r.fulfill({status:200,contentType:'application/json',body:JSON.stringify({ok:true,results:[
      {source:'ultimate-guitar',title:'Prueba Externa',artist:'Artista de prueba',id:123,url:'https://tabs.ultimate-guitar.com/tab/123'}
    ],errors:[]})});
  });
  await page.goto('http://127.0.0.1:4173/?test='+name,{waitUntil:'domcontentloaded'});
  await page.waitForTimeout(350);
  const fail=(x)=>{throw new Error(name+': '+x)};
  const input=page.locator('#q');
  const btn=page.locator('#internetSearchBtn');
  if(!(await input.isVisible()))fail('Local search input hidden');
  if(!(await btn.isVisible()))fail('Internet button must be visible with blank query');
  const position=await page.evaluate(()=>{
    const input=document.querySelector('#q').getBoundingClientRect();
    const button=document.querySelector('#internetSearchBtn').getBoundingClientRect();
    const grid=document.querySelector('#grid').getBoundingClientRect();
    return {input:{bottom:input.bottom},button:{top:button.top,bottom:button.bottom,left:button.left,right:button.right},grid:{top:grid.top},screen:{width:innerWidth}};
  });
  if(position.button.top<position.input.bottom-2 || position.button.bottom>position.grid.top)fail('Internet button not adjacent to local search');
  if(position.button.left<-2||position.button.right>width+2)fail('Internet button horizontally clipped');
  await btn.click();
  const hint=await page.locator('#internetSearchHost').innerText();
  if(!hint.includes('al menos dos caracteres'))fail('Blank query not explained');
  await input.fill('corazon de neon');
  if(!(await btn.isVisible()))fail('Internet button lost after typing');
  await btn.click();
  await page.locator('.internetResult').first().waitFor({timeout:10000});
  if(calls.length!==1||calls[0]!=='corazon de neon')fail('External endpoint not called correctly');
  if((await page.locator('.internetResult').count())!==1)fail('External result not shown');
  if(!(await page.locator('.internetUseBtn').first().isVisible()))fail('Import action invisible');
  const host=await page.locator('#internetSearchHost').boundingBox();
  if(!host||host.x<0||host.x+host.width>width+2)fail('Results overflow');
  await page.screenshot({path:'ui-review/'+name+'-internet-search.png',fullPage:false});
  if(errors.length)fail('JS console errors: '+errors.slice(0,4).join(' | '));
  console.log('PASS',name,JSON.stringify({inputToButton:Math.round(position.button.top-position.input.bottom),calls,externalResults:1,errors:errors.length}));
  await context.close();
 }
 await browser.close();
})().catch(e=>{console.error(e.stack||String(e));process.exitCode=1});
