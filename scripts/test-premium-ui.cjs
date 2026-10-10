const { chromium, devices } = require('playwright');
const fs = require('node:fs');

(async()=>{
  fs.mkdirSync('ui-review', {recursive:true});
  const browser=await chromium.launch({headless:true});
  const scenarios=[
    {name:'iphone-390',width:390,height:844,isMobile:true,deviceScaleFactor:2},
    {name:'iphone-375',width:375,height:812,isMobile:true,deviceScaleFactor:2},
    {name:'ipad-820',width:820,height:1180,isMobile:true,deviceScaleFactor:2},
    {name:'desktop-1280',width:1280,height:800,isMobile:false,deviceScaleFactor:1}
  ];
  const reports=[];
  for(const s of scenarios){
    const context=await browser.newContext({
      viewport:{width:s.width,height:s.height},
      isMobile:s.isMobile,deviceScaleFactor:s.deviceScaleFactor,
      hasTouch:s.isMobile,serviceWorkers:'block'
    });
    const page=await context.newPage();
    const errors=[];
    page.on('pageerror',err=>errors.push(String(err)));
    await page.route('**/api/sync**',route=>route.fulfill({status:200,contentType:'application/json',body:JSON.stringify({ok:true,data:{}})}));
    await page.route('**/api/backups**',route=>route.fulfill({status:200,contentType:'application/json',body:JSON.stringify({ok:true,backups:[]})}));
    await page.route('**/api/song-search**',route=>route.fulfill({status:200,contentType:'application/json',body:JSON.stringify({ok:true,results:[]})}));
    await page.goto('http://127.0.0.1:4173/?premiumqa='+s.name,{waitUntil:'domcontentloaded',timeout:30000});
    await page.waitForTimeout(1200);
    const assert=async(q,msg)=>{if(!(await q))throw Error(s.name+': '+msg)};
    await assert(page.locator('#q').isVisible(),'search unavailable');
    await assert(page.locator('#managePassesBtn').isVisible(),'passes button unavailable');
    await assert(page.locator('.premium-svg').count().then(n=>n>=5),'offline icons missing');
    await assert(page.locator('#grid .songBtn').count().then(n=>n>60),'base songs missing');
    let home=await page.evaluate(()=>({
      viewport:innerWidth,scrollWidth:document.documentElement.scrollWidth,
      font: getComputedStyle(document.querySelector('#grid .songBtn')).fontSize,
      premium: getComputedStyle(document.querySelector('.directHome')).backgroundImage,
      count:document.querySelectorAll('#grid .songBtn').length
    }));
    await assert(home.scrollWidth<=s.width+3,'home overflows horizontally');
    await page.screenshot({path:'ui-review/'+s.name+'-home.png',fullPage:false});

    await page.locator('#grid .songBtn').first().click();
    await page.waitForTimeout(350);
    await assert(page.locator('#view').isVisible(),'song did not open');
    const song=await page.evaluate(()=>{
      const bar=document.querySelector('.directSongBar');
      const controls=['back','prev','next','settingsBtn','autoScrollBtn','directTransposeDown','directTransposeUp','minus','plus'].map(id=>{
        const e=document.getElementById(id),r=e?.getBoundingClientRect();
        return {id,left:r?.left,right:r?.right,top:r?.top,bottom:r?.bottom,visible:r&&r.width>0&&r.height>0};
      });
      return {width:innerWidth,barBottom:bar.getBoundingClientRect().bottom,controls}
    });
    await assert(song.controls.every(x=>x.visible&&x.left>=-2&&x.right<=s.width+3),
       'song bar controls cut off: '+JSON.stringify(song.controls));
    const readableWords=await page.locator('#ly .wordWrap').first().evaluate(node=>{
      return {marginRight:parseFloat(getComputedStyle(node).marginRight),
              text:node.querySelector('.wordToken')?.textContent||''};
    });
    await assert(readableWords.marginRight>=4,
      'adjacent lyric words too close: '+JSON.stringify(readableWords));
    await page.screenshot({path:'ui-review/'+s.name+'-song.png',fullPage:false});

    await page.locator('#settingsBtn').click();
    await page.waitForTimeout(300);
    await assert(page.locator('#settingsModal').isVisible(),'settings did not open');
    await assert(page.locator('#qeLegacyLiveCard').isHidden(),'unnecessary live music sheet visible');
    await assert(page.locator('#qeDuplicateScrollSettings').isHidden(),'duplicate scroll settings visible');
    await page.screenshot({path:'ui-review/'+s.name+'-settings.png',fullPage:false});
    await page.locator('#settingsAdvancedToggle').click();
    await page.waitForTimeout(150);
    await assert(page.locator('#settingsEditLyrics').isVisible(),'editing unavailable in advanced tools');
    await assert(page.locator('#settingsClose').isVisible(),'settings close hidden');
    await page.screenshot({path:'ui-review/'+s.name+'-advanced.png',fullPage:false});
    await page.locator('#settingsClose').click();
    await assert(page.locator('#settingsModal').isHidden(),'settings stayed open');
    await page.locator('#back').click();
    await page.locator('#managePassesBtn').click();
    await page.waitForTimeout(150);
    await assert(page.locator('#passesModal').isVisible(),'passes manager not reachable');
    await page.screenshot({path:'ui-review/'+s.name+'-passes.png',fullPage:false});

    const data={scenario:s.name,home,song,errors};
    reports.push(data);
    console.log('OK',JSON.stringify({name:s.name,homeCount:home.count,icons:true,controlsInView:true,pageErrors:errors.length}));
    await context.close();
  }
  fs.writeFileSync('ui-review/summary.json',JSON.stringify(reports,null,2));
  await browser.close();
})().catch(err=>{console.error(err.stack||String(err));process.exitCode=1});
