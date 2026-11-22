
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
      return { usable: false, reason: 'Den aktuelle officielle gameweek og deadline kan ikke bekræftes.' };
    }
    if (current.catalogue_matches !== true) {
      return { usable: false, reason: 'Det officielle spillerkatalog er ændret. Afventer en ny prognose.' };
    }
    return result;
  };
})();
