'use strict';
(function(root){
 function check(forecast,official,now=Date.now()){
  const origin=forecast?.gws?.[0],deadline=Date.parse(forecast?.origin_deadline);
  if(!Number.isInteger(origin)||!Number.isFinite(deadline))return {usable:false,reason:'Not Available: forecast mangler en verificeret deadline'};
  if(forecast?.freshness_limit_hours!==undefined){const cutoff=Date.parse(forecast.data_asof),limit=forecast.freshness_limit_hours;if(!Number.isFinite(cutoff)||!Number.isFinite(limit)||limit<=0||now<cutoff||now-cutoff>limit*3600000)return {usable:false,reason:'Not Available: forecast er for gammel. En ny verificeret kørsel kræves.'};}
  if(now>=deadline)return {usable:false,reason:'Historisk diagnostik: GW '+origin+' er udløbet. Ny forecast kræves.'};
  if(!official||official.next_gw!==origin)return {usable:false,reason:'Not Available: forecast-GW og den officielle næste GW stemmer ikke overens'};
  if(forecast.model==='B-MM-PM-TS-v1'){
   if(!Array.isArray(forecast.players)||!forecast.players.length||!Array.isArray(official.players)||!official.players.length)return {usable:false,reason:'Not Available: spillerkatalog kan ikke verificeres'};
   const catalogue=new Map(official.players.map(p=>[p.id,p]));
   if(catalogue.size!==official.players.length||catalogue.size!==forecast.players.length||new Set(forecast.players.map(p=>p.id)).size!==forecast.players.length)return {usable:false,reason:'Not Available: spillertruppen er ændret. Nyt forecast kræves.'};
   for(const p of forecast.players){const q=catalogue.get(p.id);if(!q||!Number.isInteger(p.price_tenths)||!Number.isFinite(q.price)||Math.abs(q.price*10-p.price_tenths)>1e-6||q.team!==p.team_id||q.position!==p.position)return {usable:false,reason:'Not Available: priser, klubber eller positioner er ændret. Nyt forecast kræves.'};}
  }
  return {usable:true,reason:'Diagnostisk GW '+origin+' · deadline '+new Date(deadline).toLocaleString('da-DK')};
 }
 const api={check};root.FplForecastWindow=api;if(typeof module!=='undefined')module.exports=api;
})(typeof window!=='undefined'?window:globalThis);

FplLatestSnapshot.installWindow();

/* Installed after the existing B snapshot window so its deadline policy remains in force. */
(function () {
  const previous = FplForecastWindow.check;
  FplForecastWindow.check = (forecast, official, now = Date.now()) => {
    const result = previous(forecast, official, now);
    if (!result.usable) return result;
    const compatible = FplModelContractV1.validateOfficialCompatibility(forecast, official);
    if (!compatible.ok) return { usable: false, reason: compatible.message };
    const cutoff = Date.parse(forecast.data_asof);
    const deadline = Date.parse(forecast.origin_deadline);
    if (forecast.season !== official.season || cutoff > now || now >= deadline) {
      return { usable: false, reason: 'Historisk prognose. Sæson, cutoff eller deadline matcher ikke.' };
    }
    const current = official.live_window;
    const observed = Date.parse(current?.observed_at);
    if (!current || current.gw !== forecast.gws[0] || Date.parse(current.deadline) !== deadline ||
        !Number.isFinite(observed) || observed > now + 30_000 || now - observed > 2 * 3_600_000) {
      return { usable: false, reason: Number.isFinite(observed)&&now-observed>2*3600000?'FPL-status fra '+new Date(observed).toLocaleString('da-DK')+' er mere end to timer gammel. Datatjenesten skal opdatere status, før TS v3 kan beregnes.':'Den aktuelle officielle gameweek eller deadline mangler eller matcher ikke. Afventer verificerede data.' };
    }
    if (current.catalogue_matches !== true) {
      return { usable: false, reason: 'Det officielle spillerkatalog er ændret. Afventer en ny prognose.' };
    }
    return result;
  };
})();
