'use strict';
(function(root){
 function describe(info,now=Date.now()){
  const next=new Date(now);next.setUTCMinutes(17,0,0);if(next.getTime()<=now)next.setUTCHours(next.getUTCHours()+1);
  const at=Date.parse(info?.observed_at),known=Number.isFinite(at)&&at<=now;
  const stale=!known||now-at>2*3600000;
  const scheduled=Number.isFinite(Date.parse(info?.last_scheduled_success?.observed_at));
  return {next:next.toISOString(),warning:stale||info?.status!=='success'||!scheduled,
   message:!known?'Opdateringsstatus kunne ikke verificeres.':
    'Seneste forecastforsøg: '+info.status+' · '+new Date(at).toLocaleString('da-DK')+
    (info.trigger==='schedule'?' · tidsstyret':info.trigger?' · '+info.trigger:' · starttype ikke dokumenteret')+
    (stale?'. Opdateringer er udeblevet i over to timer.':info.status!=='success'?'. Ny kørsel fejlede; seneste verificerede forecast bevares.':'.')+
    (scheduled?' Seneste fuldt beståede automatiske kørsel: '+new Date(info.last_scheduled_success.observed_at).toLocaleString('da-DK')+'.':' En fuld tidsstyret kørsel er endnu ikke verificeret.')};
 }
 const api={describe};root.FplPipelineStatus=api;if(typeof module!=='undefined')module.exports=api;
})(typeof window!=='undefined'?window:globalThis);
