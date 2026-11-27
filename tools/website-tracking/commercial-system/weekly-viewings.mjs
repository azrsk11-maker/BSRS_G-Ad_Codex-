/** Offline composition over a trusted, reviewed private viewing extract. */
import {createHash} from 'node:crypto';

const MAX_BYTES = 8 * 1024 * 1024;
const MAX_ROWS = 10000;
const REVIEW_FIELDS = [
  'schema', 'scope', 'approval_ref', 'source_ref', 'ledger_sha256', 'coverage_from_utc',
  'coverage_to_utc', 'evidence_as_of_utc', 'reviewed_at_utc', 'valid_until_utc',
];
const ROW_FIELDS = [
  'outcome_id', 'viewing_id', 'canonical_lead_id', 'stage', 'occurred_at_utc', 'recorded_at_utc',
  'is_test', 'source_kind', 'source_evidence_reference', 'adjusts_outcome_id',
];
const SOURCES_BY_STAGE = new Map([
  ['viewing_request', ['web_intake', 'authorized_ledger']],
  ['viewing_booked', ['booking_provider', 'authorized_ledger']],
  ['viewing_cancelled', ['booking_provider', 'authorized_ledger']],
  ['viewing_no_show', ['authorized_ledger']],
  ['viewing_attended', ['authorized_ledger']],
]);
const COUNT_UNIT = {unit: 'appointment', denominator: null, currency: null};
const unknownCounts = () => ({viewings_booked_in_window: null, viewings_attended_in_window: null});
const unknown = hold => ({
  status: 'UNKNOWN', hold, metrics: unknownCounts(), ...COUNT_UNIT, evidence: null,
});

class ViewingEvidenceError extends Error {}
function require(condition, code) {
  if (!condition) throw new ViewingEvidenceError(code);
}

function exact(value, keys) {
  return value !== null && typeof value === 'object' && !Array.isArray(value) &&
    Object.keys(value).length === keys.length && keys.every(key => Object.hasOwn(value, key));
}

const opaqueRef = value => typeof value === 'string' && /^[a-zA-Z0-9][a-zA-Z0-9:_-]{0,100}$/.test(value);
const outcomeId = value => typeof value === 'string' &&
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/.test(value);

function instant(value) {
  require(typeof value === 'string' && /^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.(\d{1,6}))?Z$/.test(value),
    'VIEWING_UTC_TIMESTAMP_REQUIRED');
  const milliseconds = Date.parse(value);
  require(Number.isFinite(milliseconds) && new Date(milliseconds).toISOString().slice(0, 19) === value.slice(0, 19),
    'VIEWING_UTC_TIMESTAMP_REQUIRED');
  const fraction = /\.(\d+)/.exec(value)?.[1] ?? '';
  return BigInt(milliseconds) * 1000n + BigInt(fraction.padEnd(6, '0').slice(3));
}

function readExtract(window, options) {
  const {ledgerBytes, review, now_utc} = options;
  require(exact(review, REVIEW_FIELDS) && review.schema === 'bsre-weekly-viewing-review-v1' &&
    ['business', 'fixture'].includes(review.scope) && opaqueRef(review.approval_ref) && opaqueRef(review.source_ref) &&
    typeof review.ledger_sha256 === 'string' && /^[0-9a-f]{64}$/.test(review.ledger_sha256),
  'VIEWING_TRUSTED_REVIEW_REQUIRED');
  const from = instant(review.coverage_from_utc);
  const to = instant(review.coverage_to_utc);
  const evidenceAsOf = instant(review.evidence_as_of_utc);
  const reviewed = instant(review.reviewed_at_utc);
  const expires = instant(review.valid_until_utc);
  const now = instant(now_utc);
  // The Finance report already validated its Dubai-day boundary timestamps.
  require(window?.end_exclusive === true && window.timezone === 'Asia/Dubai' && from < to &&
    from === BigInt(Date.parse(window.from)) * 1000n && to === BigInt(Date.parse(window.to)) * 1000n,
  'VIEWING_WINDOW_COVERAGE_REQUIRED');
  require(to <= evidenceAsOf && evidenceAsOf <= reviewed && reviewed <= now && now < expires,
    'VIEWING_COVERAGE_INCOMPLETE_OR_STALE');
  require(Buffer.isBuffer(ledgerBytes) && ledgerBytes.length <= MAX_BYTES, 'VIEWING_EXTRACT_BYTES_REQUIRED');
  const bytes = Buffer.from(ledgerBytes);
  require(createHash('sha256').update(bytes).digest('hex') === review.ledger_sha256, 'VIEWING_EXTRACT_HASH_MISMATCH');
  const rows = JSON.parse(new TextDecoder('utf-8', {fatal: true, ignoreBOM: true}).decode(bytes));
  require(Array.isArray(rows) && rows.length <= MAX_ROWS, 'VIEWING_EXTRACT_ROWS_INVALID');
  return {rows, from, to, evidenceAsOf, review};
}

function readAppointments(rows, evidenceAsOf) {
  const events = new Map();
  const occurrences = new Set();
  const appointments = new Map();
  for (const row of rows) {
    require(exact(row, ROW_FIELDS) && outcomeId(row.outcome_id) && opaqueRef(row.canonical_lead_id) &&
      opaqueRef(row.source_evidence_reference) && typeof row.is_test === 'boolean', 'VIEWING_OUTCOME_FIELDS_INVALID');
    require(row.adjusts_outcome_id === null, 'VIEWING_ADJUSTMENT_REVIEW_REQUIRED');
    const isRequest = row.stage === 'viewing_request';
    require(opaqueRef(row.viewing_id) || (isRequest && row.viewing_id === null), 'VIEWING_APPOINTMENT_ID_REQUIRED');
    require(SOURCES_BY_STAGE.get(row.stage)?.includes(row.source_kind), 'VIEWING_OUTCOME_SOURCE_REQUIRED');
    const occurred = instant(row.occurred_at_utc);
    const recorded = instant(row.recorded_at_utc);
    require(occurred <= recorded && recorded <= evidenceAsOf, 'VIEWING_OUTCOME_CLOCK_CONFLICT');

    const serialized = JSON.stringify(ROW_FIELDS.map(field => row[field]));
    if (events.has(row.outcome_id)) {
      require(events.get(row.outcome_id) === serialized, 'VIEWING_OUTCOME_ID_CONFLICT');
      continue;
    }
    events.set(row.outcome_id, serialized);
    const occurrence = JSON.stringify([row.source_kind, row.source_evidence_reference]);
    require(!occurrences.has(occurrence), 'VIEWING_EVIDENCE_REFERENCE_REUSED');
    occurrences.add(occurrence);
    if (row.viewing_id === null) continue;

    if (!appointments.has(row.viewing_id)) {
      appointments.set(row.viewing_id, {
        canonicalLead: row.canonical_lead_id, isTest: row.is_test, requests: [], booked: null, termination: null,
      });
    }
    const appointment = appointments.get(row.viewing_id);
    require(appointment.canonicalLead === row.canonical_lead_id && appointment.isTest === row.is_test,
      'VIEWING_APPOINTMENT_IDENTITY_CONFLICT');
    if (isRequest) {
      appointment.requests.push(occurred);
    } else if (row.stage === 'viewing_booked') {
      require(appointment.booked === null, 'VIEWING_BOOKING_CONFLICT');
      appointment.booked = occurred;
    } else {
      require(appointment.termination === null, 'VIEWING_TERMINATION_CONFLICT');
      appointment.termination = {stage: row.stage, occurred};
    }
  }
  return appointments;
}

function countViewings({rows, from, to, evidenceAsOf}) {
  let booked = 0;
  let attended = 0;
  const inWindow = value => from <= value && value < to;
  for (const appointment of readAppointments(rows, evidenceAsOf).values()) {
    const {requests, termination} = appointment;
    const confirmation = appointment.booked;
    require(termination === null || (confirmation !== null && confirmation < termination.occurred),
      'VIEWING_BOOKING_BEFORE_TERMINATION_REQUIRED');
    if (confirmation === null) continue;
    require(requests.every(requested => requested <= confirmation), 'VIEWING_REQUEST_AFTER_BOOKING');
    if (appointment.isTest) continue;
    if (inWindow(confirmation)) booked++;
    if (termination?.stage === 'viewing_attended' && inWindow(termination.occurred)) attended++;
  }
  return {viewings_booked_in_window: booked, viewings_attended_in_window: attended};
}

/**
 * Pass an existing commercial report covering the reporting period. The caller is
 * responsible for loading its viewing review from a separately trusted source.
 */
export function withWeeklyViewingReport(base, options) {
  let weeklyViewings;
  if (base.status !== 'CALCULATED_OFFLINE_NOT_RECONCILED_WITH_PROVIDER') {
    weeklyViewings = unknown('COMMERCIAL_WINDOW_UNAVAILABLE');
  } else if (options == null) {
    weeklyViewings = unknown('VIEWING_COVERAGE_UNAVAILABLE');
  } else {
    try {
      const extract = readExtract(base.window, options);
      const counts = countViewings(extract);
      const {review} = extract;
      const fixture = review.scope === 'fixture';
      weeklyViewings = {
        status: fixture ? 'SYNTHETIC_FIXTURE_ONLY' : 'CALCULATED_OFFLINE_REVIEWED_EXTRACT',
        hold: null,
        metrics: fixture ? unknownCounts() : counts,
        ...(fixture ? {fixture_counts: counts} : {}),
        ...COUNT_UNIT,
        evidence: {
          source_ref: review.source_ref,
          approval_ref: review.approval_ref,
          ledger_sha256: review.ledger_sha256,
          coverage_from_utc: review.coverage_from_utc,
          coverage_to_utc: review.coverage_to_utc,
          evidence_as_of_utc: review.evidence_as_of_utc,
          reviewed_at_utc: review.reviewed_at_utc,
          valid_until_utc: review.valid_until_utc,
          source_truth_independently_verified: false,
        },
      };
    } catch (error) {
      const hold = error instanceof ViewingEvidenceError ? error.message : 'VIEWING_EXTRACT_INVALID';
      weeklyViewings = unknown(hold);
    }
  }
  return {...base, weekly_viewings: weeklyViewings};
}
