'use strict';

window.addEventListener('DOMContentLoaded', async () => {
  const button = document.getElementById('import-manager');
  if (!button) return;
  try {
    const response = await fetch('manager-service.json', { cache: 'no-store' });
    if (!response.ok || (await response.json()).supports_public_squad_import !== true) return;
  } catch {
    return;
  }
  button.closest('section').hidden = false;
  const message = document.getElementById('manager-import-status');
  const entry = document.getElementById('manager-import-entry');
  button.addEventListener('click', async () => {
    if (!window.FplManagerOnline?.canImport()) {
      message.textContent = 'Afventer det verificerede spillerkatalog.';
      return;
    }
    if (!/^[1-9][0-9]{0,8}$/.test(entry.value.trim())) {
      message.textContent = 'Angiv et gyldigt FPL-manager-ID.';
      return;
    }
    button.disabled = true;
    message.textContent = 'Henter den seneste offentlige holdopstilling …';
    try {
      const response = await fetch('/preview-api/squad/' + entry.value.trim(), { cache: 'no-store' });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || 'Holdet kunne ikke hentes.');
      window.FplManagerOnline.importDraft(data);
      message.textContent = 'Kladde fra GW ' + data.source_gw + '. Kontrollér ændringer i FPL, og udfyld aktuelle købspriser, bank og gratis transfers før bekræftelse.';
    } catch (error) {
      message.textContent = error.message;
    } finally {
      button.disabled = false;
    }
  });
});
