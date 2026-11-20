import test from 'node:test';
import assert from 'node:assert/strict';
import {validateStaffGate} from './validate_staff_gate.mjs';

const timing = {peak_first_contact_sample_count:4, peak_first_contact_max_seconds:1200, missing_first_attempt_count:0, late_first_attempt_count:0};
const capacity = {staffed_days_supplied:2, total_completed:18, min_daily_completions_observed:8, sample_representativeness_verified:true};
test('reviewed representative staff evidence can pass the local gate', () => {
  const result = validateStaffGate(timing, capacity, true);
  assert.equal(result.valid, true, result.errors.join('; '));
  assert.equal(result.release_authorized, false);
});
test('missing or late attempts keep the gate open', () => {
  const result = validateStaffGate({...timing, late_first_attempt_count:1}, capacity, true);
  assert.equal(result.valid, false);
});
test('synthetic summaries do not pass without owner review', () => {
  assert.equal(validateStaffGate(timing, capacity, false).valid, false);
});
