'use strict';
(function(root){
 function check(forecast,official,now=Date.now()){
  const origin=forecast?.gws?.[0],deadline=Date.parse(forecast?.origin_deadline);
  if(!Number.isInteger(origin)||!Number.isFinite(deadline))return {usable:false,reason:'Not Available: forecast mangler en verificeret deadline'};
  if(now>=deadline)return {usable:false,reason:'Historisk diagnostik: GW '+origin+' er udløbet. Ny forecast kræves.'};
  if(!official||official.next_gw!==origin)return {usable:false,reason:'Not Available: forecast-GW og den officielle næste GW stemmer ikke overens'};
  return {usable:true,reason:'Diagnostisk GW '+origin+' · deadline '+new Date(deadline).toLocaleString('da-DK')};
 }
 const api={check};root.FplForecastWindow=api;if(typeof module!=='undefined')module.exports=api;
})(typeof window!=='undefined'?window:globalThis);
