'use strict';

const assert = require('node:assert/strict');
const test = require('node:test');
const { schema, validate } = require('./modules-v1');

const hash = ch => ch.repeat(64);
const data_cutoff = '2026-11-20T12:00:00Z';
const deadline = '2026-11-21T12:00:00Z';
const input_sha256 = hash('a');
const mm = { kind: 'MM', version: 'B', output_sha256: hash('b'), data_cutoff };
const payload = { players: [] };

function sample(kind, version, dependencies) {
  const expected = { kind, version, deadline, input_sha256 };
  return [expected, {
    schema, kind, version, data_cutoff, input_sha256, output_sha256: hash('c'),
    dependencies, payload,
  }];
}

test('accepts either explicitly configured PM version with the same verified MM input', () => {
  for (const version of ['vFinal', 'candidate']) {
    const [expected, output] = sample('PM', version, [mm]);
    assert.equal(validate(output, expected, [mm]), payload);
  }
});

test('rejects unconfigured models, altered dependencies and deadline cutoffs', () => {
  const [expected, output] = sample('PM', 'vFinal', [mm]);
  assert.throws(() => validate({ ...output, version: 'candidate' }, expected, [mm]), /configured version/);
  assert.throws(() => validate(output, expected, [{ ...mm, output_sha256: hash('d') }]), /dependency/);
  assert.throws(() => validate({ ...output, data_cutoff: deadline }, expected, [mm]), /deadline/);
});

test('TS requires both upstream results and the exact configured input identity', () => {
  const pm = { kind: 'PM', version: 'vFinal', output_sha256: hash('d'), data_cutoff };
  const [expected, output] = sample('TS', 'v3', [mm, pm]);
  assert.equal(validate(output, expected, [mm, pm]), payload);
  assert.throws(() => validate({ ...output, dependencies: [mm, mm] }, expected, [mm, pm]), /dependency/);
  assert.throws(() => validate({ ...output, input_sha256: hash('e') }, expected, [mm, pm]), /identity/);
});
