import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {validateGateMatrix} from './validate_gate_matrix.mjs';

const matrix = JSON.parse(readFileSync(new URL('../../docs/audit/CURRENT_GATE_MATRIX_2026-11-11.json', import.meta.url), 'utf8'));
test('current gate matrix validates fail-closed', () => {
  const result = validateGateMatrix(matrix);
  assert.equal(result.valid, true, result.errors.join('; '));
  assert.equal(result.release_authorized, false);
});
test('a matrix cannot self-authorize production', () => {
  const altered = structuredClone(matrix);
  altered.release_authorized = true;
  assert.equal(validateGateMatrix(altered).valid, false);
});
