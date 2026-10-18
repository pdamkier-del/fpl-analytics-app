'use strict';
const assert=require('node:assert/strict'),C=require('../app/mm-preview/gk/contract.js');
const row={fixture_id:'f',player_id:'p',p_start:.7,xmins:63,p_60_plus:.7,p_90:.7,interval80:[0,90],minute_pmf:Array(91).fill(0)};row.minute_pmf[0]=.3;row.minute_pmf[90]=.7;
const now=Date.parse('2026-10-18T10:00:00Z'),f={model:C.VERSION,locked_model_active:false,minute_sampler_audit:{sampler:C.VERSION},origin_deadline:'2026-10-23T17:30:00Z',component_source_asof:{original_B_PM:'2026-10-18T09:00:00Z',official_GK_roster:'2026-10-18T09:30:00Z'},fixtures:1,
players:[{id:1,player_uuid:'p',position:1,team_id:1,weeks:[{fixtures:[{fixture_uuid:'f',xmins:63,pm_analytic_minutes:63,xpts:3}]}]},{id:2,player_uuid:'q',position:1,team_id:2,weeks:[{fixtures:[{fixture_uuid:'f',xmins:63,pm_analytic_minutes:63,xpts:3}]}]}],
gk_team_fixtures:[{team:'1',fixture_uuid:'f',unlisted_start_probability:.3,unlisted_expected_minutes:27},{team:'2',fixture_uuid:'f',unlisted_start_probability:.3,unlisted_expected_minutes:27}]};
const m={players:[row,{...structuredClone(row),player_id:'q'}]};assert.equal(C.validate(f,m,now).size,2);
for(const mutation of [x=>x.gk_team_fixtures[0].unlisted_expected_minutes=26,x=>x.gk_team_fixtures[0].unlisted_start_probability=.2,x=>x.players[0].weeks[0].fixtures[0].pm_analytic_minutes=60,x=>x.component_source_asof.original_B_PM='2026-10-16T09:00:00Z',x=>x.minute_sampler_audit.sampler='locked']){const x=structuredClone(f);mutation(x);assert.throws(()=>C.validate(x,m,now));}
const bad=structuredClone(m);bad.players[0].p_90=.6;assert.throws(()=>C.validate(f,bad,now));
assert.equal(C.interval(row),'0–90');assert.equal(C.interval(null),'Not Available');console.log('Joint GK preview: integrity,90-minute coverage,exclusive start mass,staleness and probability checks passed');
