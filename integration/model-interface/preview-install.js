'use strict';
if ('serviceWorker' in navigator && window.isSecureContext) {
  navigator.serviceWorker.register('./preview-sw.js', { updateViaCache: 'none' })
    .catch(error => console.warn('FPL Analytics kunne ikke installere offline-siden.', error));
}
