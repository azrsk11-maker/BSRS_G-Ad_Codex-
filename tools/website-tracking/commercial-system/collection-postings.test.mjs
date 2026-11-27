import assert from 'node:assert/strict';
import {test} from 'node:test';
import {commercialReport} from
  './report.mjs';
import {crosswalkFixture, financeFixture, policy, reconcileFixture} from './collection-postings.fixture.mjs';
import {collectionPostingCrosswalkHash, reconcileCollectionPostings} from './collection-postings.mjs';

function report(window) {
  return commercialReport(reconcileFixture(financeFixture(window)).input, policy);
}

function commercialMetrics({totals}) {
  return [
    totals.transactions_closed_in_window, totals.transactions_with_cash_receipts_in_window,
    totals.collected_net_revenue_minor, totals.contribution_before_acquisition_minor,
    totals.nonmedia_acquisition_minor, totals.media_spend_minor, totals.post_acquisition_contribution_minor,
  ];
}

test('current report recognizes an exact replay but counts the new export ID as another posting', () => {
  const input = financeFixture('november');
  const baseline = commercialReport(input, policy);
  assert.equal(baseline.totals.collected_net_revenue_minor, 285000);
  const {counts, input: reconciledInput} = reconcileFixture(input);
  assert.deepEqual(counts, {
    input_rows: 7, unique_export_records: 6, canonical_postings: 5,
    exact_export_repeats: 1, reconciled_export_aliases: 1,
  });
  const reconciled = commercialReport(reconciledInput, policy);
  assert.equal(reconciled.totals.collected_net_revenue_minor, 190000);
  assert.equal(input.collections.length, 7);
  assert.deepEqual(reconciledInput.collections.filter(row => row.collected_at === '2026-11-01T00:00:00+04:00')
    .map(row => row.record_id), ['synthetic-posting-first', 'synthetic-posting-second']);
});

test('separate Dubai close and payment periods reconcile through installments and later refunds', () => {
  const expected = {
    october: [1, 0, 0, 0, 0, 0, 0],
    november: [1, 1, 190000, 120000, 4000, 20000, 96000],
    december: [0, 1, 40000, 26000, 1000, 5000, 20000],
    january: [0, 0, -6000, -6000, 0, 0, -6000],
  };
  const uniqueWindow = [2, 1, 224000, 140000, 5000, 25000, 110000];
  const monthly = Object.keys(expected).map(window => {
    const metrics = commercialMetrics(report(window));
    assert.deepEqual(metrics, expected[window]);
    return metrics;
  });
  const combined = commercialMetrics(report('combined'));
  assert.deepEqual(combined, uniqueWindow);
  for (const index of [0, 2, 3, 4, 5, 6]) {
    assert.equal(monthly.reduce((sum, metrics) => sum + metrics[index], 0), combined[index]);
  }
  assert.equal(monthly.reduce((sum, metrics) => sum + metrics[1], 0), 2);
  assert.equal(combined[1], 1);
});

test('the purchase and owner attribution sum to a single cash transaction and exact contribution', () => {
  const {campaigns, totals, network_calls, production_writes} = report('combined');
  const buyer = campaigns.find(row => row.campaign_key === 'BSRE-C0121');
  const owner = campaigns.find(row => row.campaign_key === 'BSRE-C0336');
  const contract = campaigns.find(row => row.campaign_key === 'OTHER_SOURCE');
  assert.deepEqual([buyer.allocated_transaction_weight_in_window_ppm, owner.allocated_transaction_weight_in_window_ppm],
    [600000, 400000]);
  assert.deepEqual([buyer.allocated_cash_receipt_transaction_weight_ppm, owner.allocated_cash_receipt_transaction_weight_ppm],
    [600000, 400000]);
  assert.deepEqual([buyer.allocated_collected_net_revenue_minor, owner.allocated_collected_net_revenue_minor],
    [134400, 89600]);
  assert.deepEqual([buyer.post_acquisition_contribution_minor, owner.post_acquisition_contribution_minor], [64000, 46000]);
  assert.equal(campaigns.reduce((amount, row) => amount + row.post_acquisition_contribution_minor, 0),
    totals.post_acquisition_contribution_minor);
  assert.equal(contract.allocated_transaction_weight_in_window_ppm, 1000000);
  assert.equal(contract.allocated_cash_receipt_transaction_weight_ppm, 0);
  assert.equal(network_calls + production_writes, 0);
});

test('duplicates cannot inflate a later refund under another record ID', () => {
  const input = financeFixture('january');
  const replay = {...input.collections.at(-1), record_id: 'synthetic-export-refund-reprint'};
  input.collections.push(replay);
  const crosswalk = crosswalkFixture(input);
  crosswalk.entries.push({record_id: replay.record_id, posting_ref: 'synthetic-posting-refund-second'});
  assert.equal(commercialReport(input, policy).totals.collected_net_revenue_minor, -12000);
  const result = commercialReport(reconcileFixture(input, crosswalk).input, policy);
  assert.deepEqual(commercialMetrics(result), [0, 0, -6000, -6000, 0, 0, -6000]);
});

test('the result stays deterministic after an independently reviewed input reorder', () => {
  const input = financeFixture('combined');
  const expected = reconcileFixture(input).input.collections;
  input.collections.reverse();
  assert.deepEqual(reconcileFixture(input).input.collections, expected);
});

test('a modified posting map fails its review hash and a changed window requires a rebound input', () => {
  const input = financeFixture('combined');
  const crosswalk = crosswalkFixture(input);
  const hash = collectionPostingCrosswalkHash(crosswalk);
  assert.throws(() => reconcileCollectionPostings(input, crosswalk), /REVIEWED_POSTING_CROSSWALK_HASH_REQUIRED/);
  assert.throws(() => reconcileCollectionPostings(financeFixture('november'), crosswalk, hash),
    /POSTING_FINANCE_INPUT_HASH_MISMATCH/);
  crosswalk.entries[1].posting_ref = crosswalk.entries[0].posting_ref;
  assert.throws(() => reconcileCollectionPostings(input, crosswalk, hash), /POSTING_CROSSWALK_HASH_MISMATCH/);
});

test('missing, unused and repeated evidence bindings fail closed', () => {
  const input = financeFixture('combined');
  const incomplete = crosswalkFixture(input);
  incomplete.entries.pop();
  assert.throws(() => reconcileFixture(input, incomplete), /POSTING_CROSSWALK_RECORD_MISSING/);
  const repeated = crosswalkFixture(input);
  repeated.entries.push(repeated.entries[0]);
  assert.throws(() => reconcileFixture(input, repeated), /POSTING_CROSSWALK_RECORD_REPEATED/);
  const unused = crosswalkFixture(input);
  unused.entries.push({record_id: 'synthetic-unused-export', posting_ref: 'synthetic-unused-posting'});
  assert.throws(() => reconcileFixture(input, unused), /POSTING_CROSSWALK_HAS_UNUSED_RECORDS/);
});

test('an already-seen export ID with different bytes is a conflict', () => {
  const input = financeFixture('combined');
  input.collections[1].refund_minor = 1;
  assert.throws(() => reconcileFixture(input), /POSTING_EXPORT_RECORD_CONFLICT/);
});

test('a canonical posting cannot move to another transaction, instant or amount via an alias', () => {
  const changes = {
    transaction_ref: 'synthetic-contract-without-payment',
    collected_at: '2026-11-01T00:00:01+04:00',
    gross_commission_minor: 120001,
  };
  for (const [field, value] of Object.entries(changes)) {
    const input = financeFixture('combined');
    input.collections[3][field] = value;
    assert.throws(() => reconcileFixture(input), /CANONICAL_POSTING_CONTENT_CONFLICT/);
  }
});

test('source prerequisites and existing report constraints still gate calculated outcomes', () => {
  const incomplete = financeFixture('combined');
  incomplete.complete.collections = false;
  assert.throws(() => reconcileFixture(incomplete), /VERIFIED_COLLECTION_EXPORT_REQUIRED/);
  const unverified = financeFixture('combined');
  unverified.collections[3].verified = false;
  assert.throws(() => reconcileFixture(unverified), /POSTING_COLLECTION_ROW_INVALID/);
  const candidate = reconcileFixture(financeFixture('combined')).input;
  assert.equal(commercialReport(candidate, {...policy, approved: false}).metrics, null);
  candidate.collections[0].property_price = 100000000;
  assert.throws(() => commercialReport(candidate, policy), /UNKNOWN_COLLECTION_FIELD/);
});
