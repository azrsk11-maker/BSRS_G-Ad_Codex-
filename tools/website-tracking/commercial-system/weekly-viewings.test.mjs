/** Synthetic arithmetic and boundary controls only. */
import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import test from 'node:test';
import {commercialReport} from './report.mjs';
import {withWeeklyViewingReport} from './weekly-viewings.mjs';

const from = '2026-11-01T20:00:00Z';
const to = '2026-11-08T20:00:00Z';
const now = '2026-11-10T20:00:00Z';
const financeInput = {
  verified_export: true,
  source_ref: 'SYNTHETIC-finance',
  complete: {spend: true, transactions: true, collections: true, qualifications: true, opportunities: true},
  from: '2026-11-02T00:00:00+04:00',
  to: '2026-11-09T00:00:00+04:00',
  spend: [
    {campaign_key: 'BSRE-C0001', date: '2026-11-03', amount_minor: 1200, verified: true, source_ref: 'SYNTHETIC-spend'},
  ],
  transactions: [],
  collections: [],
  qualifications: [],
  opportunities: [],
};
const financePolicy = {
  approved: true,
  approval_ref: 'SYNTHETIC-finance-policy',
  currency: 'AED',
  timezone: 'Asia/Dubai',
  commission_basis: 'gross_cash_including_vat',
  refunds_basis: 'net_of_vat',
  cost_basis: 'separate_not_already_netted',
  media_basis: 'actual_ads_cost_excluding_vat',
  allocation_model: 'explicit_transaction_weights_ppm',
};
const base = commercialReport(financeInput, financePolicy);
const metrics = (booked, attended) => ({
  viewings_booked_in_window: booked,
  viewings_attended_in_window: attended,
});

const evidence = (rows, reviewChanges = {}, now_utc = now) => {
  const ledgerBytes = Buffer.from(JSON.stringify(rows));
  return {
    ledgerBytes, now_utc, review: {
      schema: 'bsre-weekly-viewing-review-v1',
      scope: 'fixture',
      approval_ref: 'SYNTHETIC-review',
      source_ref: 'SYNTHETIC-viewings',
      ledger_sha256: createHash('sha256').update(ledgerBytes).digest('hex'),
      coverage_from_utc: from,
      coverage_to_utc: to,
      evidence_as_of_utc: '2026-11-10T08:00:00Z',
      reviewed_at_utc: '2026-11-10T12:00:00Z',
      valid_until_utc: '2026-11-11T00:00:00Z',
      ...reviewChanges,
    },
  };
};
const event = (index, viewing, stage, date, changes = {}) => ({
  outcome_id: '00000000-0000-4000-8000-' + String(index).padStart(12, '0'),
  viewing_id: viewing === null ? null : 'synthetic-view-' + viewing,
  canonical_lead_id: 'synthetic-lead-A',
  stage: 'viewing_' + stage,
  occurred_at_utc: date,
  recorded_at_utc: date,
  is_test: false,
  source_kind: 'authorized_ledger',
  source_evidence_reference: 'synthetic-occur-' + index,
  adjusts_outcome_id: null,
  ...changes,
});
const booked = event(1, 'A', 'booked', from, {source_kind: 'booking_provider'});
const attended = event(2, 'A', 'attended', '2026-11-07T16:00:00.000001Z');
const request = event(3, null, 'request', '2026-11-05T10:00:00Z', {source_kind: 'web_intake'});

function assertUnknown(actual, hold) {
  assert.deepEqual(actual, {
    status: 'UNKNOWN', hold, metrics: metrics(null, null), unit: 'appointment', denominator: null, currency: null, evidence: null,
  });
}

test('an uncovered week stays unknown and the existing commercial report is retained', () => {
  const {weekly_viewings: viewings, ...financial} = withWeeklyViewingReport(base);
  assert.deepEqual(financial, base);
  assert.equal(financial.totals.media_spend_minor, 1200);
  assertUnknown(viewings, 'VIEWING_COVERAGE_UNAVAILABLE');
});

test('a blocked commercial report preserves its blockers and never reads evidence', () => {
  const blocked = commercialReport(financeInput, {});
  const unread = new Proxy({}, {get() { assert.fail('read from held report'); }});
  const {weekly_viewings: viewings, ...financial} = withWeeklyViewingReport(blocked, unread);
  assert.deepEqual(financial, blocked);
  assertUnknown(viewings, 'COMMERCIAL_WINDOW_UNAVAILABLE');
});

test('separate bookings and attendance use occurrence time, retain cancelled and no-show bookings, and exclude TEST', () => {
  const rows = [
    attended, request, booked, {...booked}, // review extract ordering and replay do not matter
    event(10, 'cancelled', 'booked', '2026-11-02T12:00:00Z'),
    event(11, 'cancelled', 'cancelled', '2026-11-03T12:00:00Z'),
    event(20, 'no-show', 'booked', '2026-11-02T12:00:00Z'),
    event(21, 'no-show', 'no_show', '2026-11-03T12:00:00Z'),
    event(30, 'prior', 'booked', '2026-11-01T19:59:59.999999Z'),
    event(31, 'prior', 'attended', '2026-11-02T13:00:00Z'),
    event(40, 'late', 'booked', '2026-11-02T12:00:00Z'),
    event(41, 'late', 'attended', to),
    event(50, 'later-booking', 'booked', to),
    event(60, 'late-recorded', 'booked', '2026-11-03T13:00:00Z', {recorded_at_utc: '2026-11-09T15:00:00Z'}),
    event(70, 'excluded', 'booked', '2026-11-03T13:00:00Z', {is_test: true}),
    event(71, 'excluded', 'attended', '2026-11-03T14:00:00Z', {is_test: true}),
  ];
  const {weekly_viewings: viewings, ...financial} = withWeeklyViewingReport(base, evidence(rows));
  assert.deepEqual(financial, base);
  assert.equal(viewings.status, 'SYNTHETIC_FIXTURE_ONLY');
  assert.deepEqual(viewings.fixture_counts, metrics(5, 2));
  assert.deepEqual(viewings.metrics, metrics(null, null));
  assert.equal(viewings.evidence.evidence_as_of_utc, '2026-11-10T08:00:00Z');
  assert.equal(viewings.evidence.source_truth_independently_verified, false);
  assert.doesNotMatch(JSON.stringify(viewings), /synthetic-(?:view-|lead-|occur-)|00000000-/);
});

test('a request alone and an empty fully covered fixture both produce illustrative zero only', () => {
  for (const rows of [[request], []]) {
    const {weekly_viewings: viewings} = withWeeklyViewingReport(base, evidence(rows));
    assert.deepEqual(viewings.fixture_counts, metrics(0, 0));
    assert.deepEqual(viewings.metrics, metrics(null, null));
  }
});

test('ledger bytes cannot choose their own trust or replace an approved digest', () => {
  const packet = evidence([booked]);
  assertUnknown(withWeeklyViewingReport(base, {...packet, review: undefined}).weekly_viewings, 'VIEWING_TRUSTED_REVIEW_REQUIRED');
  packet.ledgerBytes = Buffer.from(JSON.stringify([booked, attended]));
  assertUnknown(withWeeklyViewingReport(base, packet).weekly_viewings, 'VIEWING_EXTRACT_HASH_MISMATCH');
});

test('non-JSON or over-limit extracts fail without leaking bytes', () => {
  const packet = evidence([]);
  packet.ledgerBytes = Buffer.from('private invalid data');
  packet.review.ledger_sha256 = createHash('sha256').update(packet.ledgerBytes).digest('hex');
  assertUnknown(withWeeklyViewingReport(base, packet).weekly_viewings, 'VIEWING_EXTRACT_INVALID');
  packet.ledgerBytes = Buffer.alloc(8 * 1024 * 1024 + 1);
  assertUnknown(withWeeklyViewingReport(base, packet).weekly_viewings, 'VIEWING_EXTRACT_BYTES_REQUIRED');
});

for (const [label, changes, clock, hold] of [
  ['changing the report window', {coverage_from_utc: '2026-11-01T20:00:00.000001Z'}, now, 'VIEWING_WINDOW_COVERAGE_REQUIRED'],
  ['coverage ending before the report closes', {evidence_as_of_utc: '2026-11-08T19:59:59.999999Z'}, now, 'VIEWING_COVERAGE_INCOMPLETE_OR_STALE'],
  ['a stale review at the exact expiry', {}, '2026-11-11T00:00:00Z', 'VIEWING_COVERAGE_INCOMPLETE_OR_STALE'],
  ['a future review a microsecond away', {}, '2026-11-10T11:59:59.999999Z', 'VIEWING_COVERAGE_INCOMPLETE_OR_STALE'],
  ['a normalized invalid calendar timestamp', {valid_until_utc: '2027-02-30T00:00:00Z'}, now, 'VIEWING_UTC_TIMESTAMP_REQUIRED'],
]) {
  test(label + ' leaves both metrics unknown', () => {
    const {weekly_viewings: viewings} = withWeeklyViewingReport(base, evidence([booked], changes, clock));
    assertUnknown(viewings, hold);
  });
}

for (const [label, rows, hold] of [
  ['web source claiming booking', [{...booked, source_kind: 'web_intake'}], 'VIEWING_OUTCOME_SOURCE_REQUIRED'],
  ['booking source claiming attendance', [booked, {...attended, source_kind: 'booking_provider'}], 'VIEWING_OUTCOME_SOURCE_REQUIRED'],
  ['legacy completion label without mapped attendance evidence', [booked, {...attended, stage: 'viewing_completed'}], 'VIEWING_OUTCOME_SOURCE_REQUIRED'],
  ['conflicting retry of the same outcome ID', [booked, {...booked, recorded_at_utc: attended.recorded_at_utc}], 'VIEWING_OUTCOME_ID_CONFLICT'],
  ['same evidence under a second appointment', [booked, {...event(9, 'B', 'booked', from), source_kind: booked.source_kind,
    source_evidence_reference: booked.source_evidence_reference}], 'VIEWING_EVIDENCE_REFERENCE_REUSED'],
  ['second booking under the same stable viewing ID', [booked, event(9, 'A', 'booked', from)], 'VIEWING_BOOKING_CONFLICT'],
  ['attendance on a different canonical lead', [booked, {...attended, canonical_lead_id: 'synthetic-lead-B'}], 'VIEWING_APPOINTMENT_IDENTITY_CONFLICT'],
  ['a TEST to genuine relabel on one viewing', [booked, {...attended, is_test: true}], 'VIEWING_APPOINTMENT_IDENTITY_CONFLICT'],
  ['attendance without its booking predecessor', [attended], 'VIEWING_BOOKING_BEFORE_TERMINATION_REQUIRED'],
  ['cancellation followed by attendance on the same viewing', [booked, attended, event(9, 'A', 'cancelled', '2026-11-02T08:00:00Z')],
    'VIEWING_TERMINATION_CONFLICT'],
  ['attendance before booking at microsecond precision', [{...booked, occurred_at_utc: '2026-11-07T16:00:00.000002Z',
    recorded_at_utc: '2026-11-07T16:00:00.001Z'}, attended], 'VIEWING_BOOKING_BEFORE_TERMINATION_REQUIRED'],
  ['ledger amendment awaiting review', [booked, {...attended, adjusts_outcome_id: booked.outcome_id}], 'VIEWING_ADJUSTMENT_REVIEW_REQUIRED'],
  ['ledger entry recorded after observation', [{...booked, recorded_at_utc: '2026-11-10T08:00:00.000001Z'}], 'VIEWING_OUTCOME_CLOCK_CONFLICT'],
]) {
  test(label + ' leaves both metrics unknown', () => {
    assertUnknown(withWeeklyViewingReport(base, evidence(rows)).weekly_viewings, hold);
  });
}
