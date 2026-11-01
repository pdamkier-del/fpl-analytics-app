const assert=require('node:assert/strict');
global.FplForecastWindow=require('../app/forecast-window.js');
global.FplTeamNews=require('../app/mm-preview/dashboard-team-news.js');
const productionCheck=FplForecastWindow.check;
const S=require('../app/mm-preview/latest-snapshot.js');
S.installWindow();S.installNews();
const now=Date.now(),f={model:'B-MM-PM-TS-v1',gws:[8],data_asof:new Date(now-30*3600000).toISOString(),origin_deadline:new Date(now+3600000).toISOString(),freshness_limit_hours:6,forecast_sha256:'test'},o={next_gw:8,players:[]};
assert.equal(productionCheck(f,o,now).usable,false);
assert.equal(FplForecastWindow.check(f,o,now).usable,true);
const state={gw:8,observed_at:new Date(now-1000).toISOString(),squad:[]};
const r=FplTeamNews.evaluate({forecast:f,official:o,state,stateValid:true,usable:true,news:null},now);
assert.equal(r.canCompute,true);assert.equal(r.aligned,true);assert(r.issue); // Missing news is an explicit advisory.
assert.equal(FplForecastWindow.check({...f,origin_deadline:new Date(now-1).toISOString()},o,now).usable,false);
assert.equal(FplForecastWindow.check({...f,data_asof:new Date(now+1).toISOString()},o,now).usable,false);
assert.equal(FplForecastWindow.check(f,{next_gw:9},now).usable,false);
assert.equal(FplForecastWindow.check({...f,model:'original_locked_vFinal_diagnostic'},o,now).usable,false);
assert.equal(FplTeamNews.evaluate({forecast:f,official:o,state:{...state,gw:7},stateValid:true,usable:true},now).canCompute,false);
console.log('PASS: old B data and later team observations are usable with advisory; deadlines, future data, other GW and production remain protected.');
