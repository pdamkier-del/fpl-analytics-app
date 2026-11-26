'use strict';

(function (root, factory) {
  const api = factory();
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  else root.FplManagerStore = api.create(root.localStorage);
})(globalThis, function () {
  const key = 'fpl-manager-state-v1';

  function create(storage) {
    function read() {
      try {
        const state = JSON.parse(storage.getItem(key));
        return state && typeof state === 'object' && !Array.isArray(state) ? state : null;
      } catch {
        return null;
      }
    }

    function save(state) {
      if (!state || state.validation_only || state.draft_only || !Array.isArray(state.squad) ||
          state.squad.length !== 15 || new Set(state.squad.map(player => player?.id)).size !== 15 ||
          !state.squad.every(player => Number.isInteger(player?.id) && player.id > 0)) {
        throw new Error('Kun et bekræftet hold med 15 forskellige spillere kan gemmes.');
      }
      storage.setItem(key, JSON.stringify(state));
    }

    return Object.freeze({ key, read, save });
  }

  return Object.freeze({ create });
});
