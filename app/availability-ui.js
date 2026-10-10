/* Current-gameweek hard availability presentation. NOT the locked MM model.
   Only an explicit hard-out official status is labelled unavailable.
   Doubtful players (d) continue to display forecast uncertainty normally.
   Never extrapolate origin GW unavailability to future GWs.
*/
(function(root){
  'use strict';
  const hard=new Set(['i','s','u']);
  function isUnavailable(player){
    return Boolean(player && hard.has(String(player.status||'').toLowerCase()));
  }
  function isUnavailableForGW(player,targetGW,nextGW){
    return Number.isInteger(Number(nextGW)) &&
      Number(targetGW)===Number(nextGW) && isUnavailable(player);
  }
  function display(player,targetGW,nextGW){
    return isUnavailableForGW(player,targetGW,nextGW) ? 'Not available' : null;
  }
  root.FPLAvailability=Object.freeze({isUnavailable,isUnavailableForGW,display,
    hardOfficialStatuses:Object.freeze(['i','s','u'])});
})(typeof window==='undefined'?globalThis:window);
