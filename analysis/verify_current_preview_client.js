'use strict';
// Integration check against actual sealed current outputs, never a demo team.
const fs=require('fs'),path=require('path'),crypto=require('crypto'),assert=require('assert');
const contract=require('../app/mm-preview/live-contract.js');
const windowContract=require('../app/forecast-window.js');
const dir=process.argv[2];if(!dir)throw Error('Current public export directory required');
const read=name=>JSON.parse(fs.readFileSync(path.join(dir,name),'utf8'));
const index=read('index.json');
for(const [name,digest] of [[index.forecast_file,index.forecast_file_sha256],[index.mm_file,index.mm_file_sha256],[index.catalogue_file,index.catalogue_sha256]])assert.equal(crypto.createHash('sha256').update(fs.readFileSync(path.join(dir,name))).digest('hex'),digest);
const f=read(index.forecast_file),m=read(index.mm_file),c=read(index.catalogue_file);
assert(contract.catalogue(f,c));
const mm=new Map(m.players.map(p=>[p.fixture_id+'|'+p.player_id,p]));let rows=0,hard=0;
for(const p of f.players)for(const w of p.weeks){
 const metrics=contract.metrics(p,w.gw,mm);assert(Number.isFinite(metrics.xp)&&Number.isFinite(metrics.xm));
 let xm=0,notPlay=1;
 for(const x of w.fixtures){const r=mm.get(x.fixture_uuid+'|'+p.player_uuid);assert(r);rows++;
  assert(Math.abs(r.xmins-(r.p_start*r.start_minutes+(1-r.p_start)*r.p_sub_given_not_start*r.sub_minutes))<1e-6);
  assert(!('interval80' in r)&&!('minute_pmf' in r)&&!('minute_probabilities' in r));
  assert(contract.interval(r).startsWith('Not Available'));
  xm+=r.xmins;notPlay*=1-r.p_play;
  if(['OUT','SUSPENDED'].includes(r.availability)){assert.equal(r.xmins,0);assert.equal(x.xpts,0);hard++;}
 }
 assert(Math.abs(xm-w.xmins)<1e-6);assert(Math.abs((1-notPlay)-w.p_play)<1e-6);
}
for(const t of m.teams){const xi=m.players.filter(r=>r.fixture_id===t.fixture_id&&r.club_id===t.club_id&&r.expected_xi);assert.equal(xi.length,11);assert.equal(xi.filter(r=>r.slot==='GK').length,1);}
assert(windowContract.check(f,c,Date.parse(f.data_asof)+1000).usable);
assert(!windowContract.check(f,c,Date.parse(f.origin_deadline)+1).usable);
assert(!windowContract.check(f,c,Date.parse(f.data_asof)+25*3600000).usable);
const changed=structuredClone(c);changed.players[0].price+=.1;assert.throws(()=>contract.catalogue(f,changed));
console.log(JSON.stringify({cutoff:f.data_asof,players:f.players.length,fixtures:f.fixtures,gws:f.gws,MM_PM_matched_rows:rows,legal_club_XI:m.teams.length,hard_unavailable_zero_rows:hard,raw_checksums_verified:true,MM_PM_probabilities_and_means_verified:true,expired_and_changed_catalogue_rejected:true,unvalidated_intervals_hidden:true,manager_tested:false,locked_model_active:false},null,2));
