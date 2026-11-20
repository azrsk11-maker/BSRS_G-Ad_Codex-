import {createHash} from 'node:crypto';
import {buildPurposeClientCandidate} from './build-purpose-attribution-candidate.mjs';
import {buildRetentionAdmissionClient} from './build-retention-admission-candidate.mjs';

const BASELINE = '3d469cccef9891702ba1462e29f17ba3135261fff23ea2a40c052aa6afb99154';
const PREFIX = Buffer.from(String.raw`/^https:\/\/wa\.me\/`);
const SUFFIX = Buffer.from(String.raw`(?:\?|$)/.test(href)`);
const digest = bytes => createHash('sha256').update(bytes).digest('hex');
const need = (condition, code) => { if (!condition) throw new Error(code); };

function bindingRecord(binding) {
  need(binding !== null && typeof binding === 'object' &&
    [Object.prototype, null].includes(Object.getPrototypeOf(binding)), 'CONTACT_BINDING_SHAPE');
  const keys = Reflect.ownKeys(binding);
  need(keys.length === 2 && keys.every(k => ['baseline_sha256', 'target_sha256'].includes(k)), 'CONTACT_BINDING_SHAPE');
  for (const key of keys) {
    const field = Object.getOwnPropertyDescriptor(binding, key);
    need(Object.hasOwn(field, 'value') && typeof field.value === 'string' && /^[a-f0-9]{64}$/.test(field.value),
      'CONTACT_BINDING_HASH');
  }
}

function literal(bytes) {
  const start = bytes.indexOf(PREFIX);
  need(start >= 0 && bytes.indexOf(PREFIX, start + PREFIX.length) === -1, 'CONTACT_MATCHER_ANCHOR');
  const from = start + PREFIX.length, end = bytes.indexOf(SUFFIX, from);
  need(end >= from && bytes.indexOf(SUFFIX, end + SUFFIX.length) === -1, 'CONTACT_MATCHER_ANCHOR');
  const digits = bytes.subarray(from, end);
  need(digits.length >= 7 && digits.length <= 15 && /^[1-9][0-9]+$/.test(digits.toString('ascii')) &&
    digits.every(byte => byte >= 48 && byte <= 57), 'CONTACT_MATCHER_LITERAL');
  return {from, end, digits};
}

// Diagnostic text only. Never writes a fixture, chooses a business contact or activates a candidate.
function buildBoundCandidate(baselineBytes, targetBytes, binding, profile) {
  bindingRecord(binding);
  for (const bytes of [baselineBytes, targetBytes]) {
    need(Buffer.isBuffer(bytes) && bytes.length > 0 && bytes.length <= 262144, 'CONTACT_RAW_BYTES_REQUIRED');
    need(Buffer.from(bytes.toString('utf8'), 'utf8').equals(bytes), 'CONTACT_INVALID_UTF8');
  }
  need(binding.baseline_sha256 === BASELINE && digest(baselineBytes) === BASELINE, 'CONTACT_BASELINE_CHANGED');
  need(digest(targetBytes) === binding.target_sha256, 'CONTACT_TARGET_HASH_CHANGED');
  const old = literal(baselineBytes), current = literal(targetBytes);
  need(!old.digits.equals(current.digits), 'CONTACT_TARGET_UNCHANGED');
  need(baselineBytes.subarray(0, old.from).equals(targetBytes.subarray(0, current.from)) &&
    baselineBytes.subarray(old.end).equals(targetBytes.subarray(current.end)), 'CONTACT_UNRELATED_SOURCE_CHANGE');

  // The original pinned chain receives only its immutable original bytes.
  need(['purpose', 'retention-admission'].includes(profile), 'CONTACT_PROFILE_INVALID');
  const original = Buffer.from(profile === 'retention-admission'
    ? buildRetentionAdmissionClient(baselineBytes) : buildPurposeClientCandidate(baselineBytes), 'utf8');
  const anchor = literal(original);
  need(anchor.digits.equals(old.digits), 'CONTACT_COMPOSED_MATCHER_CHANGED');
  const candidate = Buffer.concat([original.subarray(0, anchor.from), current.digits, original.subarray(anchor.end)]);
  const check = literal(candidate);
  need(Buffer.concat([candidate.subarray(0, check.from), old.digits, candidate.subarray(check.end)]).equals(original),
    'CONTACT_OUTPUT_OVERLAY_CHANGED');
  return Object.freeze({
    status: 'DIAGNOSTIC_CANDIDATE_ONLY', diagnostic_only: true, deployment_prohibited: true,
    baseline_sha256: BASELINE, target_sha256: digest(targetBytes),
    original_candidate_sha256: digest(original), candidate_sha256: digest(candidate),
    permitted_difference: 'ONE_WHATSAPP_RECOGNITION_LITERAL',
    holds: Object.freeze(['CONTACT_AUTHORITY_NOT_ESTABLISHED_BY_ADAPTER', 'PUBLIC_DELIVERY_CONVERGENCE_UNVERIFIED',
      'COUPLED_PACKAGE_REVIEW_REQUIRED', 'RUNTIME_AND_RELEASE_ACCEPTANCE_REQUIRED']),
    candidate: candidate.toString('utf8'),
  });
}

// Preserve the original purpose-only adapter's text and result contract.
export function buildContactCompatibleClientCandidate(baselineBytes, targetBytes, binding) {
  return buildBoundCandidate(baselineBytes, targetBytes, binding, 'purpose');
}

export function buildContactCompatibleRetentionAdmissionClientCandidate(baselineBytes, targetBytes, binding) {
  return Object.freeze({...buildBoundCandidate(baselineBytes, targetBytes, binding, 'retention-admission'),
    profile: 'RETENTION_ADMISSION_CLIENT_ONLY'});
}
