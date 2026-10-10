'use strict';
(function(root){
 function check(forecast,official,now=Date.now()){
  const origin=forecast?.gws?.[0],deadline=Date.parse(forecast?.origin_deadline);
  if(!Number.isInteger(origin)||!Number.isFinite(deadline))return {usable:false,reason:'Not Available: forecast mangler en verificeret deadline'};
  if(forecast?.freshness_limit_hours!==undefined){const cutoff=Date.parse(forecast.data_asof),limit=forecast.freshness_limit_hours;if(!Number.isFinite(cutoff)||!Number.isFinite(limit)||limit<=0||now<cutoff||now-cutoff>limit*3600000)return {usable:false,reason:'Not Available: forecast er for gammel. En ny verificeret kørsel kræves.'};}
  if(now>=deadline)return {usable:false,reason:'Historisk diagnostik: GW '+origin+' er udløbet. Ny forecast kræves.'};
  if(!official||official.next_gw!==origin)return {usable:false,reason:'Not Available: forecast-GW og den officielle næste GW stemmer ikke overens'};
  return {usable:true,reason:'Diagnostisk GW '+origin+' · deadline '+new Date(deadline).toLocaleString('da-DK')};
 }
 const api={check};root.FplForecastWindow=api;if(typeof module!=='undefined')module.exports=api;
})(typeof window!=='undefined'?window:globalThis);
