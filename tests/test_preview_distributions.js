const assert=require('node:assert/strict');
const {distribution}=require('../app/mm-preview/gk/contract.js');
const d={draws:400,p_start:.5,p_zero:.3,p_cameo:.2,p_60_plus:.4,p_90:.1,p_2_plus:.6,p_5_plus:.2,p_10_plus:.05,minute_bins:[.3,.3,.3,.1],points_interval80:[0,8],pm_expected_minutes:42};
assert.equal(distribution(d),d);
for(const change of [{p_start:NaN},{p_cameo:.5},{p_90:.6},{p_5_plus:.8},{minute_bins:[.2,.2,.2,.2]},{points_interval80:[8,0]}])assert.throws(()=>distribution({...d,...change}));
console.log('PM probability validation passed');
