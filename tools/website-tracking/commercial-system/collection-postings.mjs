/** Prepare an offline finance export using explicitly reviewed canonical posting identities. */
import {segmentFinanceInputHash} from
  './segments.mjs';

const SCHEMA = 'bsre-finance-posting-crosswalk-v1';
const ID = /^[a-zA-Z][a-zA-Z0-9:_-]{0,100}$/;
const SHA256 = /^[a-f0-9]{64}$/;
const ROW_LIMIT = 10_000;

function require(condition, code) {
  if (!condition) throw new Error(code);
}

function exactKeys(object, keys) {
  return object !== null && typeof object === 'object' && !Array.isArray(object) &&
    Object.keys(object).length === keys.length && keys.every(key => Object.hasOwn(object, key));
}

function identifier(value) {
  return typeof value === 'string' && ID.test(value);
}

export function collectionPostingCrosswalkHash(crosswalk) {
  return segmentFinanceInputHash({schema: SCHEMA, crosswalk});
}

/**
 * The caller supplies the reviewed crosswalk hash through a protected channel.
 * This offline utility checks the bytes and mapping, leaving evidence truth and
 * policy approval to the finance owner.
 */
export function reconcileCollectionPostings(input, crosswalk, reviewedCrosswalkHash) {
  require(typeof reviewedCrosswalkHash === 'string' && SHA256.test(reviewedCrosswalkHash),
    'REVIEWED_POSTING_CROSSWALK_HASH_REQUIRED');
  require(exactKeys(crosswalk, ['schema', 'finance_input_sha256', 'entries']) && crosswalk.schema === SCHEMA &&
    Array.isArray(crosswalk.entries) && crosswalk.entries.length <= ROW_LIMIT, 'POSTING_CROSSWALK_INVALID');
  require(collectionPostingCrosswalkHash(crosswalk) === reviewedCrosswalkHash, 'POSTING_CROSSWALK_HASH_MISMATCH');
  require(input?.verified_export === true && identifier(input.source_ref) && input.complete?.collections === true &&
    Array.isArray(input.collections) && input.collections.length <= ROW_LIMIT, 'VERIFIED_COLLECTION_EXPORT_REQUIRED');
  require(crosswalk.finance_input_sha256 === segmentFinanceInputHash(input), 'POSTING_FINANCE_INPUT_HASH_MISMATCH');

  const byRecord = new Map();
  for (const entry of crosswalk.entries) {
    require(exactKeys(entry, ['record_id', 'posting_ref']) && identifier(entry.record_id) &&
      identifier(entry.posting_ref), 'POSTING_CROSSWALK_ENTRY_INVALID');
    require(!byRecord.has(entry.record_id), 'POSTING_CROSSWALK_RECORD_REPEATED');
    byRecord.set(entry.record_id, entry.posting_ref);
  }

  const seenRecords = new Map();
  const postings = new Map();
  for (const row of input.collections) {
    require(row && identifier(row.record_id) && row.verified === true && identifier(row.source_ref),
      'POSTING_COLLECTION_ROW_INVALID');
    const postingRef = byRecord.get(row.record_id);
    require(postingRef !== undefined, 'POSTING_CROSSWALK_RECORD_MISSING');
    const duplicate = seenRecords.get(row.record_id);
    if (duplicate !== undefined) {
      require(segmentFinanceInputHash(duplicate) === segmentFinanceInputHash(row), 'POSTING_EXPORT_RECORD_CONFLICT');
      continue;
    }
    seenRecords.set(row.record_id, row);
    const {record_id, source_ref, ...postingValues} = row;
    const digest = segmentFinanceInputHash(postingValues);
    const previous = postings.get(postingRef);
    require(previous === undefined || previous.digest === digest, 'CANONICAL_POSTING_CONTENT_CONFLICT');
    if (previous === undefined || record_id < previous.recordId) {
      postings.set(postingRef, {recordId: record_id, digest, row: {...postingValues, record_id: postingRef, source_ref}});
    }
  }
  require(seenRecords.size === byRecord.size, 'POSTING_CROSSWALK_HAS_UNUSED_RECORDS');
  const collections = [...postings.keys()].sort().map(key => postings.get(key).row);
  return {
    input: {...input, collections},
    counts: {
      input_rows: input.collections.length,
      unique_export_records: seenRecords.size,
      canonical_postings: collections.length,
      exact_export_repeats: input.collections.length - seenRecords.size,
      reconciled_export_aliases: seenRecords.size - collections.length,
    },
  };
}
