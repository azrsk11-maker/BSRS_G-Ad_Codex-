import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {validateFormContract} from './validate_form_contract.mjs';

const receipt = JSON.parse(readFileSync(new URL('../../docs/audit/NATIVE_ENQUIRY_FORM_CONTRACT_READBACK_2026-11-11.json', import.meta.url), 'utf8'));
test('native form contract receipt validates', () => {
  const result = validateFormContract(receipt);
  assert.equal(result.valid, true, result.errors.join('; '));
  assert.equal(result.release_authorized, false);
});
test('runtime acceptance cannot be implied by HTML contract', () => {
  const altered = structuredClone(receipt);
  altered.evidence_limit = 'HTML only';
  assert.equal(validateFormContract(altered).valid, false);
});
