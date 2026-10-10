const {chromium}=require('playwright');
const fs=require('node:fs');

const fixture='<div data-light-contrast-fixture class="lyricLine">'+
 '<div class="lineBody"><span class="wordWrap"><span class="wordChord">LA7</span><span class="wordToken">POR</span></span> '+
 '<span class="wordWrap"><span class="wordChord">SI7</span><span class="wordToken">EL</span></span>'+
 '<span class="lineChord">SOL7</span></div></div>'+
 '<div data-light-section-fixture class="musicSection"><div class="musicSectionTitle">INTRO</div>'+
 '<div class="musicSectionChords"><span class="musicChordChip">LA7</span>'+
 '<span class="musicChordChip">SI7</span></div></div>';

function channels(value){
  const matches=String(value).match(/[\d.]+/g)||[];
  return matches.slice(0,3).map(Number).map(x=>x/255);
}
function luminance(value){
  const c=channels(value).map(x=>x<=0.04045?x/12.92:Math.pow((x+.055)/1.055,2.4));
  return c[0]*.2126+c[1]*.7152+c[2]*.0722;
}
function contrast(a,b){const x=luminance(a),y=luminance(b);return (Math.max(x,y)+.05)/(Math.min(x,y)+.05);}
async function check(page,label,selector,bg,minimum=4.5){
  const found=await page.locator(selector).first().evaluate(e=>({
    color:getComputedStyle(e).color,
    fill:getComputedStyle(e).webkitTextFillColor,
    text:e.textContent.trim().slice(0,55),
    visible:!!(e.offsetWidth||e.offsetHeight||e.getClientRects().length)
  }));
  if(!found.visible)throw Error(label+': hidden '+selector);
  const ratio=contrast(found.color,bg);
  if(!Number.isFinite(ratio)||ratio<minimum){
    throw Error(label+': low contrast '+ratio.toFixed(2)+' for '+selector+
       ' text='+found.color+' against '+bg+' ('+found.text+')');
  }
  if(found.fill!==found.color){
    const fillRatio=contrast(found.fill,bg);
    if(fillRatio<minimum)throw Error(label+': WebKit fill low contrast '+fillRatio.toFixed(2)+' for '+selector);
  }
  return {name:label,ratio:+ratio.toFixed(2),color:found.color};
}

(async()=>{
 fs.mkdirSync('ui-review',{recursive:true});
 const browser=await chromium.launch({headless:true});
 const scenarios=[
   {name:'iphone-375',width:375,height:812,isMobile:true},
   {name:'iphone-390',width:390,height:844,isMobile:true},
   {name:'ipad-820',width:820,height:1180,isMobile:true},
   {name:'desktop-1280',width:1280,height:800,isMobile:false}
 ];
 const all=[];
 for(const s of scenarios){
   const context=await browser.newContext({viewport:{width:s.width,height:s.height},
      isMobile:s.isMobile,hasTouch:s.isMobile,deviceScaleFactor:s.isMobile?2:1,serviceWorkers:'block'});
   const page=await context.newPage();
   page.setDefaultTimeout(10000);
   const errors=[];
   page.on('pageerror',e=>errors.push(String(e)));
   await page.route('**/api/sync**',r=>r.fulfill({status:200,contentType:'application/json',body:'{"ok":true,"data":{}}'}));
   await page.route('**/api/backups**',r=>r.fulfill({status:200,contentType:'application/json',body:'{"ok":true,"backups":[]}'}));
   await page.goto('http://127.0.0.1:4173/?lightcontrast='+s.name,{waitUntil:'domcontentloaded',timeout:20000});
   await page.waitForTimeout(1300);
   await page.evaluate(()=>document.body.classList.add('lightTheme'));
   await page.waitForTimeout(250);
   const home=[];
   home.push(await check(page,'Home brand','.directHome .brand','rgb(247,244,237)'));
   home.push(await check(page,'Song counter','.directMeta .count','rgb(243,240,232)'));
   home.push(await check(page,'Pases button','.directActions .directActionPrimary','rgb(255,247,229)'));
   home.push(await check(page,'Internet help','.internetSearchHint','rgb(243,240,232)'));
   if(!(await page.locator('#internetSearchBtn').isVisible()))throw Error('Internet search button invisible');
   await page.screenshot({path:'ui-review/'+s.name+'-home-light.png',fullPage:false});
   const song=page.locator('#grid .songBtn').filter({hasText:'A LA LUZ DEL LORENZO'}).first();
   if(!(await song.isVisible()))throw Error(s.name+': sample song absent');
   await song.click();
   await page.waitForTimeout(400);
   if(!(await page.locator('#view').isVisible()))throw Error('Song screen hidden');
   await page.evaluate(markup=>document.getElementById('ly').insertAdjacentHTML('afterbegin',markup),fixture);
   const songChecks=[];
   songChecks.push(await check(page,'Lyrics','[data-light-contrast-fixture] .wordToken','rgb(243,240,232)'));
   songChecks.push(await check(page,'Word chord','[data-light-contrast-fixture] .wordChord','rgb(243,240,232)'));
   songChecks.push(await check(page,'Line chord','[data-light-contrast-fixture] .lineChord','rgb(243,240,232)'));
   songChecks.push(await check(page,'Intro heading','[data-light-section-fixture] .musicSectionTitle','rgb(255,250,240)'));
   songChecks.push(await check(page,'Intro chord','[data-light-section-fixture] .musicChordChip','rgb(244,229,190)'));
   songChecks.push(await check(page,'Song title','#view.on .title','rgb(243,240,232)'));
   songChecks.push(await check(page,'Scroll action','#autoScrollBtn','rgb(248,233,197)'));
   songChecks.push(await check(page,'Transpose down','#directTransposeDown','rgb(255,248,230)'));
   songChecks.push(await check(page,'Speed value','#autoScrollSpeedValue','rgb(248,245,238)'));
   await page.screenshot({path:'ui-review/'+s.name+'-song-light.png',fullPage:false});
   await page.evaluate(()=>document.body.classList.remove('lightTheme'));
   await page.waitForTimeout(120);
   const darkChord=await page.locator('[data-light-contrast-fixture] .wordChord').first().evaluate(e=>getComputedStyle(e).color);
   const lightChord=songChecks.find(x=>x.name==='Word chord').color;
   if(darkChord===lightChord)throw Error(s.name+': dark chord unexpectedly has light color');
   if(errors.length)throw Error(s.name+': page JavaScript errors '+errors.join(' | '));
   const result={viewport:s.name,home,songChecks,darkChord,errors:errors.length};
   all.push(result);
   console.log('PASS',s.name,JSON.stringify({home:home.map(x=>[x.name,x.ratio]),song:songChecks.map(x=>[x.name,x.ratio]),errors:0}));
   await context.close();
 }
 fs.writeFileSync('ui-review/contrast-summary.json',JSON.stringify(all,null,2));
 await browser.close();
})().catch(error=>{console.error(error.stack||String(error));process.exit(1)});
