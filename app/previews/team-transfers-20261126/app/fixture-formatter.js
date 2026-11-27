// Fixture formatting helpers. Dates come only from real kickoff_utc values in FPL_DATA.fixtures.
(function(){
  function dateText(iso){
    if(!iso) return '';
    const d=new Date(iso); if(Number.isNaN(d.getTime())) return '';
    return `${d.getUTCDate()} ${d.toLocaleString('en-GB',{month:'short',timeZone:'UTC'})}`;
  }
  function parseFixture(s){
    const raw=String(s||'').trim();
    const m=raw.match(/^(.+?)\s*\(([HA])\)\s*$/i);
    return m?{opp:m[1].trim(),venue:m[2].toUpperCase()}:{opp:raw,venue:''};
  }
  function findFixture(gw, fixture){
    const data=window.FPL_DATA||{}; const p=parseFixture(fixture);
    for(const f of (data.fixtures||[])){
      if(Number(f.gw)!==Number(gw)) continue;
      // Fixture label is from the player's perspective: OPP (A) means opponent is home.
      if(p.venue==='A' && String(f.home)===p.opp) return f;
      if(p.venue==='H' && String(f.away)===p.opp) return f;
    }
    return null;
  }
  window.fixtureDate=function(gw, fixture){const f=findFixture(gw,fixture);return dateText(f?.kickoff_utc)};
  window.formatFixture=function(gw, fixture){
    if(!fixture) return `GW${gw||''}`.trim();
    const date=window.fixtureDate(gw,fixture);
    return `GW${gw}${date?' · '+date:''} · ${fixture}`;
  };
  window.formatFixtureCompact=function(gw, fixture){
    const date=window.fixtureDate(gw,fixture);
    return {top:`GW${gw}${date?' · '+date:''}`,bottom:String(fixture||'—')};
  };
})();
