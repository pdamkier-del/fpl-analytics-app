'use strict';

(function (root, factory) {
  const api = factory();
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  else root.FplModelModulesV1 = api;
})(globalThis, function () {
  const schema = 'fpl-model-module/v1';
  const dependencyKinds = { MM: [], PM: ['MM'], TS: ['MM', 'PM'] };
  const validSha = value => typeof value === 'string' && /^[a-f0-9]{64}$/.test(value);
  const instant = value => typeof value === 'string' &&
    /(?:Z|[+-]\d{2}:\d{2})$/.test(value) && Number.isFinite(Date.parse(value));

  function validate(result, expected, dependencies) {
    const reject = reason => {
      throw new Error(`Incompatible ${expected.kind} result: ${reason}`);
    };
    if (!result || result.schema !== schema || !Object.hasOwn(dependencyKinds, expected.kind) ||
        result.kind !== expected.kind || typeof expected.version !== 'string' ||
        !expected.version.trim() || result.version !== expected.version) {
      reject('module kind, schema or configured version differs');
    }
    if (!validSha(expected.input_sha256) || result.input_sha256 !== expected.input_sha256 ||
        !validSha(result.output_sha256) || result.payload == null) {
      reject('input or output identity is missing or unexpected');
    }
    if (!instant(result.data_cutoff) || !instant(expected.deadline) ||
        Date.parse(result.data_cutoff) >= Date.parse(expected.deadline)) {
      reject('data cutoff must precede the official deadline');
    }
    const kinds = dependencyKinds[expected.kind];
    if (!Array.isArray(result.dependencies) || result.dependencies.length !== kinds.length ||
        !Array.isArray(dependencies) || dependencies.length !== kinds.length) {
      reject('dependency list differs from the module contract');
    }
    for (const kind of kinds) {
      const actual = result.dependencies.filter(item => item?.kind === kind);
      const parent = dependencies.find(item => item?.kind === kind);
      if (actual.length !== 1 || !parent || actual[0].version !== parent.version ||
          !validSha(parent.output_sha256) || actual[0].output_sha256 !== parent.output_sha256 ||
          !instant(parent.data_cutoff) || Date.parse(result.data_cutoff) < Date.parse(parent.data_cutoff)) {
        reject(`${kind} dependency version, content identity or cutoff differs`);
      }
    }
    return result.payload;
  }

  return Object.freeze({ schema, validate });
});
