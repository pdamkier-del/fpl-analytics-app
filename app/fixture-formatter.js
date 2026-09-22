// Fixture date helper - formats fixture strings with dates from kickoff_utc
(function() {
  if (!window.FPL_DATA || !window.FPL_DATA.fixtures) return;
  
  // Build lookup: gw-home-away -> date string
  const dateMap = {};
  for (const f of window.FPL_DATA.fixtures) {
    if (!f.kickoff_utc) continue;
    try {
      const dt = new Date(f.kickoff_utc);
      const day = String(dt.getUTCDate()).padStart(2, '0');
      const month = dt.toLocaleString('en-US', {month: 'short', timeZone: 'UTC'});
      const dateStr = (dt.getUTCDate() + ' ' + month).replace(/^\d/, m => String(Number(m))); // strip leading 0
      const key = `${f.gw}|${f.home}|${f.away}`;
      dateMap[key] = dateStr;
    } catch(e) {}
  }
  
  // Helper: format fixture label with date
  window.formatFixture = function(gw, fixture) {
    if (!fixture || !gw) return fixture || '';
    // fixture format is like "LIV (A)" or "LIV (H)"
    const away = fixture.includes('(A)');
    let club = fixture.replace(/\s*\([AH]\)\s*$/, '').trim();
    // Find matching fixture
    for (const f of window.FPL_DATA.fixtures) {
      if (f.gw !== gw) continue;
      if ((away && f.away === club) || (!away && f.home === club)) {
        const date = dateMap[`${f.gw}|${f.home}|${f.away}`];
        return `GW${gw} · ${date || '?'} · ${fixture}`;
      }
    }
    return `GW${gw} · ${fixture}`;
  };
})();
