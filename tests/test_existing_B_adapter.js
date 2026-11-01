'use strict';
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict'),{webcrypto,createHash}=require('node:crypto');
const source=fs.readFileSync('app/mm-preview/existing-app-adapter.js','utf8');
const bytes=x=>JSON.stringify(x),sha=x=>createHash('sha256').update(bytes(x)).digest('hex');
const forecast={model:'B_locked_PM_preview',forecast_sha256:'same',locked_model_active:false};
const documents={'current-players.json':{players:[{id:1}],teams:{1:{name:'Official'}}},'live-fixtures.json':{fixtures:[]},'club-lineups.json':{source:'B_MM_assignment'}};
const data={forecast_sha256:'same',documents};
const index={model:'B_locked_PM_preview',locked_model_active:false,minute_sampler:'locked',forecast_sha256:'same',forecast_file:'forecast.json',forecast_file_sha256:sha(forecast),existing_app_data_sha256:sha(data)};
const historyDocs={'current-players.json':{fetched_at:'actual-clock',players:[{id:1}]},'live-fixtures.json':{fetched_at:'actual-clock',fixtures:[{id:10}]},'match-results.json':{observed_at:'actual-clock',match_rows:[{player_id:1,fixture_id:10}],gw_rows:[]}};
const historyIndex={schema:'fpl-preview-actual-history-v1',observed_at:'actual-clock',production_run:123,production_artifact:456,files:Object.fromEntries(Object.entries(historyDocs).map(([n,d])=>[n,sha(d)]))};
function context(broken=false,brokenHistory=false){const calls=[],window={fetch:async(input)=>{const url=String(input);calls.push(url);const key=url.split('/').pop();const value=url.includes('/history/')?(key==='index.json'?historyIndex:brokenHistory?{}:historyDocs[key]):key==='index.json'?index:key==='forecast.json'?forecast:key==='existing-app-data.json'?(broken?{}:data):{original:true};return new Response(bytes(value),{headers:{'Content-Type':'application/json'}});}};const c={window,location:{href:'https://example.org/fpl/mm-preview/app/player.html?id=1',origin:'https://example.org'},document:{addEventListener(){}},URL,Response,TextEncoder,TextDecoder,Uint8Array,crypto:webcrypto,setTimeout(){}};vm.runInNewContext(source,c);return {window,calls};}
(async()=>{
 const {window:w,calls}=context();
 assert.deepEqual(await(await w.fetch('vfinal-diagnostic.json')).json(),forecast);
 assert.deepEqual(await(await w.fetch('current-players.json')).json(),documents['current-players.json']);
 assert.deepEqual(await(await w.fetch('fixture-expectations.json')).json(),{cutoff:null,fixtures:[]});
 const history=await(await w.fetch('match-results.json')).json();assert.equal(history.observed_at,'actual-clock');assert.equal(history.historical_catalogue.fetched_at,'actual-clock');assert.equal(history.history_provenance.production_run,123);assert(calls.some(u=>u.endsWith('/mm-preview/history/match-results.json')));
 await assert.rejects(async()=>context(false,true).window.fetch('match-results.json'),/Checksum/);
 await w.fetch('https://backend.example/plans/private',{headers:{'X-Plan-Key':'secret'}});assert.equal(calls.at(-1),'https://backend.example/plans/private');
 assert.equal((await w.FplBExistingApp.forecast()).forecast_sha256,'same');
 await assert.rejects(async()=>context(true).window.fetch('vfinal-diagnostic.json'),/checksum/);
 assert(!source.includes('localStorage.setItem'));
 console.log('Existing B app adapter: 8 checksum, routing, stale-source isolation and privacy checks passed');
})().catch(e=>{console.error(e);process.exitCode=1});
