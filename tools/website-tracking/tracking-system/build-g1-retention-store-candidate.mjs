// Separate review candidate; original builders, fixtures and default lanes stay unchanged.
import {createHash} from 'node:crypto';
import {buildRetentionAdmissionStore} from './build-retention-admission-candidate.mjs';
const sha = bytes => createHash('sha256').update(bytes).digest('hex');
const ORIGINAL = '7ccb7fdf0d88a3d2b1d54832f61c71bfcc025554bebf3927d7f5ce0c72f12262';
const ADMISSION = '5390f2733e7e76c6c2a0e514add39c15ae94327adafd4d23f33e393ef6b4daa8';
export function buildG1RetentionStoreCandidate(bytes) {
  if (!Buffer.isBuffer(bytes) || sha(bytes) !== ORIGINAL) throw new Error('G1_ORIGINAL_CHANGED');
  const before = buildRetentionAdmissionStore(bytes);
  if (sha(before) !== ADMISSION) throw new Error('G1_ADMISSION_ANCESTRY_CHANGED');
  const anchor = 'return $this->transaction(function () use ($capture) {';
  const next = '\n            \\BSRE\\RetentionAdmission\\assert_capture($this->db, $capture);';
  if (before.split(anchor).length !== 2) throw new Error('G1_STAGE_ANCHOR_CHANGED');
  const at = before.indexOf(anchor) + anchor.length;
  if (!before.slice(at).startsWith(next)) throw new Error('G1_STAGE_ORDER_CHANGED');
  const fence = `
            // Unknown captures carry no grant; a stale subject alone cannot deny intake.
            // Known evidence must still exist under the retirement/choice state lock.
            if ((int) $capture['known'] === 1) {
                if ($capture['subject_key'] === '') throw new \\RuntimeException('Consent evidence retired.');
                $current = $this->row($this->db->prepare("SELECT * FROM {$this->state} WHERE subject_key=%s FOR UPDATE", $capture['subject_key']));
                if (!$current) throw new \\RuntimeException('Consent evidence retired.');
                $original = $this->row($this->db->prepare("SELECT receipt FROM {$this->history} WHERE subject_key=%s AND revision=%d FOR UPDATE", $capture['subject_key'], $capture['original_revision']));
                if (!$original || !hash_equals($original['receipt'], $capture['decision_version'])) throw new \\RuntimeException('Consent evidence retired.');
            }`;
  const candidate = before.slice(0, at) + fence + before.slice(at);
  if (candidate.slice(0, at) + candidate.slice(at + fence.length) !== before) throw new Error('G1_REVERSE_CHANGED');
  return Object.freeze({candidate, original_sha256: ORIGINAL, admission_sha256: ADMISSION,
    candidate_sha256: sha(candidate), insertion_offset: at, insertion_characters: fence.length,
    status: 'G1_KNOWN_EVIDENCE_FENCE_ONLY', deployment_prohibited: true});
}
