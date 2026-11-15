import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {createHash} from 'node:crypto';
import {buildG1RetentionStoreCandidate as build} from './build-g1-retention-store-candidate.mjs';
import {buildRetentionAdmissionStore} from './build-retention-admission-candidate.mjs';
const bytes=readFileSync(new URL('../../staging-lab/fixtures/bsre-enquiries/includes/consent-store.php',import.meta.url));
test('entire admission derivation remains exact after removing the one G1 fence',()=>{
  const original=Buffer.from(bytes), r=build(bytes);
  assert.equal(r.candidate.slice(0,r.insertion_offset)+r.candidate.slice(r.insertion_offset+r.insertion_characters),buildRetentionAdmissionStore(bytes));
  assert.deepEqual(bytes,original);
  assert.equal(createHash('sha256').update(r.candidate).digest('hex'),r.candidate_sha256);
  assert.equal(r.deployment_prohibited,true);
});
test('known is the outer guard; stale subject alone does not run retirement rejection',()=>{
  const r=build(bytes), fence=r.candidate.slice(r.insertion_offset,r.insertion_offset+r.insertion_characters);
  assert.ok(fence.indexOf("if ((int) $capture['known'] === 1)") < fence.indexOf("if ($capture['subject_key'] === '')"));
  assert.equal(fence.split('FOR UPDATE').length-1,2);
  assert.equal(fence.split('Consent evidence retired.').length-1,3);
  assert.ok(!fence.includes('INSERT') && !fence.includes('UPDATE ') && !fence.includes('DELETE'));
});
test('fence is before admission/purpose; both original version modes and receipt methods survive',()=>{
  const r=build(bytes), s=r.candidate;
  const start=s.indexOf("if ((int) $capture['known'] === 1)",r.insertion_offset);
  const admission=s.indexOf('\\BSRE\\RetentionAdmission\\assert_capture($this->db, $capture);',start);
  const purpose=s.indexOf('$capture += prepare_capture($this->db, $capture);',start);
  assert.ok(start<admission && admission<purpose);
  assert.ok(s.includes('public function admissionContract()') && s.includes('public function link('));
});
test('nonbuffer and source-drift inputs cannot bypass original provenance',()=>{
  assert.throws(()=>build(bytes.toString('utf8')),/G1_ORIGINAL_CHANGED/);
  assert.throws(()=>build(Buffer.concat([bytes,Buffer.from('\n')])),/G1_ORIGINAL_CHANGED/);
  const changed=Buffer.from(bytes);changed[0]^=1;
  assert.throws(()=>build(changed),/G1_ORIGINAL_CHANGED/);
});
