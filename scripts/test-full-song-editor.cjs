const {chromium}=require('playwright');
const fs=require('node:fs');
async function main(){
 fs.mkdirSync('ui-review', {recursive:true});
 const browser=await chromium.launch({headless:true});
 for(const [name,width,height] of [['iphone-375',375,812],['iphone-390',390,844],['ipad-820',820,1180],['desktop-1280',1280,800]]){
   const context=await browser.newContext({viewport:{width,height},isMobile:width<900,hasTouch:width<900,serviceWorkers:'block'});
   const page=await context.newPage(), errors=[];
   page.on('pageerror',e=>errors.push(e.message));
   await page.route('**/api/sync**',r=>r.fulfill({status:200,contentType:'application/json',body:JSON.stringify({ok:true,data:{}})}));
   await page.route('**/api/backups**',r=>r.fulfill({status:200,contentType:'application/json',body:JSON.stringify({ok:true,backups:[]})}));
   await page.goto('http://127.0.0.1:4173/?editorqa='+name,{waitUntil:'domcontentloaded',timeout:30000});
   await page.locator('#grid .songBtn').first().click();
   await page.locator('#quickEditSongBtn').waitFor({state:'visible'});
   const fail=message=>{throw new Error(name+': '+message)};
   await page.locator('#quickEditSongBtn').click();
   const menu=page.locator('#quickEditMenu');
   if(!(await menu.isVisible()))fail('Editar menu is not visible');
   for(const id of ['quickEditLyricsBtn','quickEditTitleBtn','quickEditChordsBtn','quickEditIntroBtn','quickEditInstrumentalBtn']){
      if(!(await page.locator('#'+id).isVisible()))fail(id+' hidden');
   }
   const mrect=await menu.boundingBox();
   if(!mrect||mrect.x<0||mrect.x+mrect.width>width+2||mrect.y+mrect.height>height+2)fail('Editor menu clipped '+JSON.stringify(mrect));
   await page.screenshot({path:'ui-review/'+name+'-edit-menu.png',fullPage:false});

   // Both title and the ENTIRE editable lyrics must be visible.
   await page.locator('#quickEditLyricsBtn').click();
   if(!(await page.locator('#lyricEditorModal').isVisible()))fail('Lyrics editor not opened');
   const text=page.locator('#lyricEditorText'), save=page.locator('#lyricEditorSave');
   if(!(await text.isVisible()))fail('Lyrics textarea missing');
   if(!(await save.isVisible()))fail('Save lyrics action missing');
   const rect=await text.boundingBox(), saveRect=await save.boundingBox();
   if(!rect||rect.height<115||rect.y>=height||!saveRect||saveRect.y>=height)fail('Lyrics textarea/footer clipped: '+JSON.stringify({rect,saveRect}));
   if(!(await text.inputValue()).trim())fail('Current lyrics did not load');
   await page.screenshot({path:'ui-review/'+name+'-lyrics-editor.png',fullPage:false});
   await page.locator('#lyricEditorCancel').click();

   await page.locator('#quickEditSongBtn').click();
   await page.locator('#quickEditTitleBtn').click();
   if(!(await page.locator('#lyricEditorSongTitle').isVisible()))fail('Title input not visible');
   if(!(await page.locator('#lyricEditorText').isVisible()))fail('Lyrics hidden in title mode');
   await page.locator('#lyricEditorCancel').click();

   await page.locator('#quickEditSongBtn').click();
   await page.locator('#quickEditChordsBtn').click();
   if(!(await page.locator('#view').evaluate(el=>el.classList.contains('editing'))))fail('Chord mode failed');
   if(!(await page.locator('#quickChordIntro').isVisible())||!(await page.locator('#quickChordInstrumental').isVisible()))fail('Intro/instrumental tools missing in chord mode');
   await page.locator('#quickChordSave').click();
   if(await page.locator('#view').evaluate(el=>el.classList.contains('editing')))fail('Chord mode did not exit');
   await page.locator('#quickEditSongBtn').click();
   await page.locator('#quickEditIntroBtn').click();
   if(!(await page.locator('#chordModal').isVisible()))fail('Intro chord picker not opened');
   const cancel=page.locator('#chordCancel');
   if(await cancel.count())await cancel.click();
   else await page.locator('#chordModal').evaluate(el=>el.classList.remove('on'));
   // Avoid writing test data; confirmation of menu accessibility and exact editor wiring.
   if(errors.length)fail('JS errors: '+errors.join(' | '));
   console.log('PASS '+name+' menu=5 lyrics=visible height='+Math.round(rect.height)+' title=yes chords=yes intro=yes errors=0');
   await context.close();
 }
 await browser.close();
}
main().catch(e=>{console.error(e.stack||String(e));process.exitCode=1});
