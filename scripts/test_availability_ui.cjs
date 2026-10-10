'use strict';
const fs=require('fs'),vm=require('vm'),assert=require('assert');
const sandbox={window:{}};
vm.runInNewContext(fs.readFileSync('app/availability-ui.js','utf8'),sandbox,{filename:'availability-ui.js'});
const a=sandbox.window.FPLAvailability;
assert(a,'availability helper was not initialized');
for(const status of ['i','s','u']){
  assert.strictEqual(a.isUnavailable({status}),true,status+' must be hard unavailable');
  assert.strictEqual(a.display({status},6,6),'Not available');
  assert.strictEqual(a.display({status},7,6),null,'do not assume future GW unavailability');
}
for(const status of ['a','d','n',undefined,'']){
  assert.strictEqual(a.isUnavailable({status}),false,'do not falsely mark '+String(status));
  assert.strictEqual(a.display({status},6,6),null);
}
assert.strictEqual(a.isUnavailable(null),false);
assert.strictEqual(a.isUnavailableForGW({status:'s'},6,null),false);
assert.strictEqual(a.isUnavailableForGW({status:'s'},'6',6),true);
const pages=['my-team-live.html','locked-forecast.html','clubs-live.html','own-forecast.html','forecast-live.html'];
for(const page of pages){
  const html=fs.readFileSync('app/'+page,'utf8');
  assert(html.includes('availability-ui.js'),page+': missing common helper');
  assert(html.includes('Not available'),page+': missing availability label');
  const idx=html.indexOf('availability-ui.js'),inline=html.indexOf('<script>',idx);
  assert(idx>0&&inline>idx,page+': helper must load before inline render');
}
console.log('Availability UI: hard statuses labelled, doubtful excluded, future GW not inferred, 5 pages wired');
