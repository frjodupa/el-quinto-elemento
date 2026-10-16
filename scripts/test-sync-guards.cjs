const assert=require('node:assert/strict');const fs=require('node:fs');const src=fs.readFileSync('public/index.html','utf8');
const pull=src.slice(src.indexOf('async function pullRemote('),src.indexOf('async function syncNow('));
const sync=src.slice(src.indexOf('async function syncNow('),src.indexOf('function schedulePush('));
assert.match(pull,/if\(localStorage\.getItem\(META_DIRTY\)==='1'\)[\s\S]*?return false;[\s\S]*?applyState\(remote\)/,'polling pull must never discard dirty local changes');
assert.match(sync,/if\(localStorage\.getItem\(META_DIRTY\)==='1'\)[\s\S]*?return;[\s\S]*?applyState\(remote\.data\)/,'manual sync must never discard dirty local changes');
assert.match(src,/expectedUpdatedAt:Number\(expectedUpdatedAt\|\|0\)/,'cloud sync must provide optimistic concurrency timestamp');
console.log('EQE sync guards: 3 passed');
