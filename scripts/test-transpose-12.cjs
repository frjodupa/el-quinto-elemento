const {chromium}=require('playwright');
const fs=require('node:fs');
(async()=>{
 fs.mkdirSync('ui-review', {recursive:true});
 const browser=await chromium.launch({headless:true});
 for(const [name,width,height] of [['iphone',390,844],['ipad',820,1180],['desktop',1280,800]]){
  const ctx=await browser.newContext({viewport:{width,height},isMobile:width<900,hasTouch:width<900,serviceWorkers:'block'});
  const page=await ctx.newPage();
  const errors=[];
  page.on('pageerror',e=>errors.push(String(e)));
  await page.route('**/api/sync**',r=>r.fulfill({status:200,contentType:'application/json',body:'{"ok":true,"data":{}}'}));
  await page.route('**/api/backups**',r=>r.fulfill({status:200,contentType:'application/json',body:'{"ok":true,"backups":[]}'}));
  await page.goto('http://127.0.0.1:4173/?semitone-test='+name,{waitUntil:'domcontentloaded',timeout:30000});
  await page.waitForTimeout(250);
  const fail=(m)=>{throw Error(name+': '+m)};
  await page.locator('#grid .songBtn').first().click();
  await page.waitForTimeout(250);
  const fixture={
    lines:{"0":"SOL"},
    words:{"0:0":"DOm7/SOL","1:1":"REm"},
    intro:"DO · SOL",
    introText:"Con su ritmo original",
    instrumentals:{"4":"MI7 · RE"},
    instrumentalsText:{"4":"Riff instrumental"},
    references:[{"type":"mark","line":2}]
  };
  const baseline=await page.evaluate((fixture)=>{
    localStorage.setItem('quintoElemento.chords.v2.'+current,JSON.stringify(fixture));
    localStorage.removeItem('quintoElemento.transpose.v1.'+current);
    renderLyrics();
    return {id:current,text:getSongText(current)};
  },fixture);
  await page.locator('#settingsBtn').click();
  const range=page.locator('#transposeSemitoneRange');
  const count=page.locator('#transposeSemitoneCount');
  if(!(await range.isVisible()))fail('range hidden');
  if(await range.getAttribute('min')!=='-12'||await range.getAttribute('max')!=='12'||await range.getAttribute('step')!=='1')fail('range malformed');
  const geometry=await page.evaluate(()=>{
    const ids=['transposeOctDown','transposeStepDown','transposeStepOriginal','transposeStepUp','transposeOctUp'];
    return ids.map(id=>{const b=document.getElementById(id),r=b.getBoundingClientRect();return {id,x:r.left,right:r.right,width:r.width,visible:r.width>0&&r.height>0}});
  });
  if(geometry.some(x=>!x.visible||x.x<0||x.right>width+2))fail('controls outside viewport: '+JSON.stringify(geometry));
  const state=async()=>page.evaluate((id)=>{
    const raw=localStorage.getItem('quintoElemento.chords.v2.'+id);
    const offset=localStorage.getItem('quintoElemento.transpose.v1.'+id);
    return {chords:JSON.parse(raw||'{}'),offset:offset===null?0:Number(offset),text:getSongText(id)};
  },baseline.id);
  let now=await state();
  if(now.offset!==0||!(await count.innerText()).includes('Original'))fail('bad initial state');

  await page.locator('#transposeStepUp').click();
  now=await state();
  if(now.offset!==1||now.chords.words['0:0']!=='DO#m7/SOL#'||now.chords.intro!=='DO# · SOL#'||now.chords.instrumentals['4']!=='FA7 · RE#')fail('up one semitone failed '+JSON.stringify(now));
  if(now.text!==baseline.text)fail('lyrics changed up1');
  if(JSON.stringify(now.chords.references)!==JSON.stringify(fixture.references))fail('references changed');

  await page.locator('#transposeStepDown').click();
  now=await state();
  if(now.offset!==0||now.chords.words['0:0']!=='DOm7/SOL')fail('down one semitone did not restore pitch class');
  const beforeOct=JSON.stringify(now.chords);
  await page.locator('#transposeOctUp').click();
  now=await state();
  if(now.offset!==12||JSON.stringify(now.chords)!==beforeOct)fail('+12 rewrote chord notation or wrong offset');
  if(!(await page.locator('#transposeStepUp').isDisabled()))fail('upper bound not enforced');
  await page.locator('#transposeStepOriginal').click();
  now=await state();
  if(now.offset!==0||JSON.stringify(now.chords)!==beforeOct)fail('original after +12 differs');
  await page.locator('#transposeOctDown').click();
  now=await state();
  if(now.offset!==-12||JSON.stringify(now.chords)!==beforeOct)fail('-12 rewrote chords');
  if(!(await page.locator('#transposeStepDown').isDisabled()))fail('lower bound not enforced');

  await range.evaluate(el=>{el.value='-7';el.dispatchEvent(new Event('input',{bubbles:true}))});
  if(!(await count.innerText()).includes('-7'))fail('range preview missing');
  now=await state();
  if(now.offset!==-12)fail('drag triggered premature write');
  await range.evaluate(el=>el.dispatchEvent(new Event('change',{bubbles:true})));
  now=await state();
  if(now.offset!==-7)fail('slider did not commit -7');
  if(now.text!==baseline.text)fail('lyrics changed by slider');
  if(now.chords.introText!==fixture.introText||JSON.stringify(now.chords.instrumentalsText)!==JSON.stringify(fixture.instrumentalsText))fail('Intro/Instrumental text corrupted');
  await page.locator('#transposeStepOriginal').click();
  now=await state();
  if(now.offset!==0)fail('reset to original did not work');
  await page.screenshot({path:'ui-review/'+name+'-transpose-12.png',fullPage:false});
  if(errors.length)fail('JS errors '+errors.slice(0,3).join(' | '));
  console.log('PASS '+name,JSON.stringify({viewport:width,initial:0,upOne:true,plus12:true,minus12:true,rangeMinus7:true,reset:true,preservedOriginalLyrics:true,errors:errors.length}));
  await ctx.close();
 }
 await browser.close();
})().catch(err=>{console.error(err.stack||String(err));process.exitCode=1});
