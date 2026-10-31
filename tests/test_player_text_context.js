'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs');
const api=require('../app/mm-preview/player-text-context.js');
const data=JSON.parse(fs.readFileSync('app/mm-preview/text-context/evidence.json')),index=JSON.parse(fs.readFileSync('app/mm-preview/text-context/index.json'));
assert.equal(api.validate(data,index).records.length,10);
assert.equal(new Set(data.records.map(r=>r.player_id)).size,9);
assert.equal(data.teams.length,20);
for(const change of [d=>d.forecast_effect='boost',d=>d.records[0].model_input_enabled=true,d=>d.records[0].source_url='javascript:alert(1)',d=>d.records[0].source_url='https://www.mancity.com.evil.example/news',d=>d.records[0].observed_at='2099-01-01T00:00:00Z',d=>d.records[0].scope='confirmed_next_start',d=>d.records[0].published_at='2099-01-01',d=>d.teams.push(d.teams[0])]){const copy=structuredClone(data);change(copy);assert.throws(()=>api.validate(copy,index));}
assert.equal(api.allowed('https://user:password@www.mancity.com/news'),false);
assert.equal(api.allowed('http://www.mancity.com/news'),false);
console.log('Player text context: 10 records, 20 clubs and invalid evidence rejection passed');
