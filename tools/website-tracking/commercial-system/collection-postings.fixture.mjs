import {segmentFinanceInputHash} from
  './segments.mjs';
import {collectionPostingCrosswalkHash, reconcileCollectionPostings} from './collection-postings.mjs';

export const policy = Object.freeze({
  approved: true,
  approval_ref: 'SYNTHETIC-FIXTURE-FINANCE-POLICY',
  currency: 'AED',
  timezone: 'Asia/Dubai',
  commission_basis: 'gross_cash_including_vat',
  refunds_basis: 'net_of_vat',
  cost_basis: 'separate_not_already_netted',
  media_basis: 'actual_ads_cost_excluding_vat',
  allocation_model: 'explicit_transaction_weights_ppm',
});
const source = Object.freeze({verified: true, source_ref: 'SYNTHETIC-FINANCE-EXPORT'});
const purchase = 'synthetic-purchase-transaction';
const buyerCampaign = 'BSRE-C0121';
const ownerCampaign = 'BSRE-C0336';
const zero = {
  gross_commission_minor: 0, vat_minor: 0, refund_minor: 0, pass_through_minor: 0,
  agent_payout_minor: 0, referral_payout_minor: 0, direct_cost_minor: 0, nonmedia_acquisition_minor: 0,
};
const november = {
  gross_commission_minor: 120000, vat_minor: 20000, pass_through_minor: 5000, agent_payout_minor: 20000,
  referral_payout_minor: 5000, direct_cost_minor: 10000, nonmedia_acquisition_minor: 2000,
};

function posting(recordId, at, amounts) {
  return {record_id: recordId, transaction_ref: purchase, collected_at: at, ...zero, ...amounts, ...source};
}

export const windows = {
  october: ['2026-10-01', '2026-11-01'],
  november: ['2026-11-01', '2026-12-01'],
  december: ['2026-12-01', '2027-01-01'],
  january: ['2027-01-01', '2027-02-01'],
  combined: ['2026-10-01', '2027-02-01'],
};

export function financeFixture(window) {
  const [from, to] = windows[window].map(date => date + 'T00:00:00+04:00');
  const first = posting('synthetic-export-a', '2026-11-01T00:00:00+04:00', november);
  const second = {...first, record_id: 'synthetic-export-b'};
  const alias = {...first, record_id: 'synthetic-export-replay', source_ref: 'SYNTHETIC-REPRINT-EXPORT'};
  return {
    verified_export: true, source_ref: source.source_ref,
    complete: {spend: true, transactions: true, collections: true, qualifications: true, opportunities: true},
    from, to,
    spend: [
      {campaign_key: buyerCampaign, date: '2026-11-01', amount_minor: 12000, ...source},
      {campaign_key: ownerCampaign, date: '2026-11-02', amount_minor: 8000, ...source},
      {campaign_key: buyerCampaign, date: '2026-12-01', amount_minor: 5000, ...source},
    ],
    transactions: [
      {transaction_ref: purchase, closed_at: '2026-10-31T23:59:59.999999+04:00',
        allocations: [{campaign_key: buyerCampaign, weight_ppm: 600000},
          {campaign_key: ownerCampaign, weight_ppm: 400000}], ...source},
      {transaction_ref: 'synthetic-contract-without-payment', closed_at: '2026-11-22T11:00:00+04:00',
        allocations: [{campaign_key: null, source_class: 'other', weight_ppm: 1000000}], ...source},
    ],
    collections: [
      first, {...first}, second, alias,
      posting('synthetic-export-c', '2026-11-30T20:00:00Z',
        {gross_commission_minor: 50000, vat_minor: 5000, pass_through_minor: 1000,
          agent_payout_minor: 10000, referral_payout_minor: 1000, direct_cost_minor: 3000,
          nonmedia_acquisition_minor: 1000}),
      posting('synthetic-export-refund-d', '2026-12-12T09:00:00+04:00', {refund_minor: 4000}),
      posting('synthetic-export-refund-e', '2027-01-05T15:00:00+04:00', {refund_minor: 6000}),
    ],
    qualifications: [],
    opportunities: [],
  };
}

export function crosswalkFixture(input) {
  return {
    schema: 'bsre-finance-posting-crosswalk-v1',
    finance_input_sha256: segmentFinanceInputHash(input),
    entries: [
      {record_id: 'synthetic-export-a', posting_ref: 'synthetic-posting-first'},
      {record_id: 'synthetic-export-b', posting_ref: 'synthetic-posting-second'},
      {record_id: 'synthetic-export-replay', posting_ref: 'synthetic-posting-first'},
      {record_id: 'synthetic-export-c', posting_ref: 'synthetic-posting-third'},
      {record_id: 'synthetic-export-refund-d', posting_ref: 'synthetic-posting-refund-first'},
      {record_id: 'synthetic-export-refund-e', posting_ref: 'synthetic-posting-refund-second'},
    ],
  };
}

export function reconcileFixture(input, crosswalk = crosswalkFixture(input)) {
  return reconcileCollectionPostings(input, crosswalk, collectionPostingCrosswalkHash(crosswalk));
}
