const assert=require('node:assert/strict');
const fs=require('node:fs');
const {JSDOM}=require('jsdom');
const html=fs.readFileSync('app/forecast-center.html','utf8');
const script=html.match(/<script>([\s\S]*?)<\/script>/)?.[1];
assert.ok(script,'Forecast Center script not found');
new Function(script);
const dom=new JSDOM(html,{url:'http://localhost:8765/forecast-center.html',runScripts:'outside-only'});
const {window}=dom,document=window.document;
const payload={
  mode:'bridge_preview_indicative_only',locked_forecast_active:false,
  data:{season:'2026/27',model_version:'live_simple_baseline_v0.1',updated:'2026-09-22 20:12',
    stale:true,official_next_gw:6,official_observed_at_utc:'2026-10-09T14:00:00Z',
    available_gws:[6,7,8],official_player_count:667,forecast_end_gw:11,
    player_count:562,fixture_count:380,actual_count:3250},
  alerts:['Ældre forecast-bridge'],
  chips:[
    {id:'fh',label:'Free Hit',candidate_gw:null,expected_gain_proxy:0,confidence:'indicative_only',reason:'Ikke beregnet'},
    {id:'wc',label:'Wildcard',candidate_gw:8,expected_gain_proxy:11.5,confidence:'indicative_only',reason:'Simuleret'},
    {id:'bb',label:'Bench Boost',candidate_gw:7,bench_gross_xp:14.1,confidence:'indicative_only',reason:'Brutto'},
    {id:'tc',label:'Triple Captain',candidate_gw:6,captain_xp:7.2,player:'Haaland',confidence:'indicative_only',reason:'Indikativ'}
  ],
  weeks:[{gw:6,formation:'3-4-3',captain:'Haaland',captain_xp:7.2,bench_gross_xp:11.4,xi_xp:57.3,
          xi:[{id:411,name:'Haaland',xpts:7.2}],bench:[]}]
};
window.fetch=async()=>({ok:true,json:async()=>payload});
window.eval(script);
setTimeout(()=>{
 try{
  assert.equal(document.querySelectorAll('#chip-grid .chip-card').length,4);
  assert.ok(document.querySelector('#weekly-table').textContent.includes('57,30'));
  assert.ok(document.querySelector('#source-data').textContent.includes('667'));
  assert.ok(document.querySelector('#mode-status').textContent.includes('forældede'));
  assert.ok(document.querySelector('#alerts').textContent.includes('Ældre forecast-bridge'));
  console.log('FORECAST_UI_SMOKE_OK',document.querySelectorAll('#chip-grid .chip-card').length);
 }catch(e){console.error(e);process.exitCode=1}
},0);
