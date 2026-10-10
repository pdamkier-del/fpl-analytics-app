'use strict';
const assert=require('node:assert/strict'),{check}=require('../app/forecast-window.js');
const forecast={gws:[7,8,9,10,11,12],origin_deadline:'2026-10-17T10:00:00Z'},official={next_gw:7};
assert.equal(check(forecast,official,Date.parse('2026-10-10T20:00:00Z')).usable,true);
assert.equal(check(forecast,official,Date.parse('2026-10-17T10:00:00Z')).usable,false);
assert.equal(check(forecast,{next_gw:8},Date.parse('2026-10-10T20:00:00Z')).usable,false);
assert.equal(check({gws:[7]},official,Date.parse('2026-10-10T20:00:00Z')).usable,false);
console.log('4 forecast deadline and official-GW checks passed');
