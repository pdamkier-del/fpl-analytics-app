'use strict';

(async () => {
  const status = document.getElementById('forecast-refresh-status');
  if (!status) return;
  try {
    const response = await fetch('../current/forecast.json', { cache: 'no-store' });
    if (!response.ok) throw new Error('Forecast unavailable');
    const forecast = await response.json();
    const issued = new Date(forecast.data_asof);
    const deadline = Date.parse(forecast.origin_deadline);
    if (!Number.isFinite(issued.getTime()) || !Number.isFinite(deadline)) throw new Error('Invalid forecast timestamp');
    const age = Date.now() - issued.getTime();
    const historical = age < 0 || age >= 36 * 60 * 60 * 1000 || Date.now() >= deadline;
    const time = new Intl.DateTimeFormat('da-DK', {
      dateStyle: 'short', timeStyle: 'short', timeZone: 'Europe/Copenhagen',
    }).format(issued);
    status.textContent = (historical ? 'Historisk prognose' : 'Senest godkendte prognose') + ' · ' + time + ' dansk tid';
  } catch {
    status.textContent = 'Kunne ikke læse tidspunktet for den senest godkendte prognose.';
  }
})();
