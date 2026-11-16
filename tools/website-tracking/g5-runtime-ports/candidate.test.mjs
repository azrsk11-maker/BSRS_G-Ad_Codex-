import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {buildG5RuntimeCandidate, readG5NativeFixture, SOURCE_SHA256, CANDIDATE_SHA256, OUTPUT_SHA256, REQUIRED_OUTPUTS, RULE_SPANS, NATIVE_SHA256, sha256} from './build-candidate.mjs';
import {buildG5RuntimeLab} from '../../staging-lab/build-g5-runtime-lab.mjs';
const read = relative => readFileSync(new URL('../../' + relative.replace(/^tools\//,''), import.meta.url));

test('default pure factory emits all 13 exact held outputs',()=>{
  const {outputs,manifest}=buildG5RuntimeCandidate();
  assert.equal(Object.keys(outputs).length,13); assert.deepEqual(Object.keys(outputs).sort(),REQUIRED_OUTPUTS);
  for(const [name,pin] of Object.entries(OUTPUT_SHA256)) assert.equal(sha256(outputs[name]),pin,name);
  assert.equal(manifest.status,'HELD'); assert.equal(manifest.native_accepted,false); assert.equal(manifest.actual_provider_accepted,false); assert.equal(manifest.production_authorized,false); assert.equal(manifest.full_profile_complete,false);
});
test('eight original outputs remain byte-for-byte guarded domain sources',()=>{
  const {outputs}=buildG5RuntimeCandidate();
  const names=['Workflow','NoMailCopy','RetirementIntent','ClosureCollection','RetirementJournal','ClosureCollectionJournal','LeaseBoundWpdb'];
  for(const name of names) assert.deepEqual(outputs[`plugin/includes/candidate/closed-enquiry-retention/${name}.php`],read(`tools/closed-enquiry-retention/${name}.php`));
  assert.deepEqual(outputs['plugin/includes/candidate/consent-retention/RetentionInventory.php'],read('tools/consent-retention/RetentionInventory.php'));
  assert.match(outputs['plugin/includes/candidate/closed-enquiry-retention/Workflow.php'].toString(),/ISOLATED_LAB_ONLY/);
});
test('five runtime modules equal their reviewed public candidate bytes',()=>{
  const {outputs}=buildG5RuntimeCandidate();
  assert.equal(Object.keys(CANDIDATE_SHA256).length,5);
  for(const relative of Object.keys(CANDIDATE_SHA256)) {const name=relative.slice(relative.indexOf('/candidate/')+'/candidate/'.length); assert.deepEqual(outputs[name],read(relative));}
});
test('changed original input is rejected before output',()=>{
  const target=Object.keys(SOURCE_SHA256)[0];
  assert.throws(()=>buildG5RuntimeCandidate({read:p=>p===target?Buffer.concat([read(p),Buffer.from('\n')]):read(p)}),/G5_PREIMAGE_CHANGED/);
});
test('changed runtime module is rejected before output',()=>{
  const target=Object.keys(CANDIDATE_SHA256)[0];
  assert.throws(()=>buildG5RuntimeCandidate({read:p=>p===target?Buffer.concat([read(p),Buffer.from('\n')]):read(p)}),/G5_PREIMAGE_CHANGED/);
});
test('missing input fails closed with a portable source name',()=>{
  const target=Object.keys(SOURCE_SHA256)[0];
  assert.throws(()=>buildG5RuntimeCandidate({read:p=>{if(p===target)throw new Error('PRIVATE_LOCAL_PATH');return read(p);}}),e=>e.message==='G5_INPUT_UNAVAILABLE:'+target);
});
test('capture rule original pin, four spans and exact derivation are preserved',()=>{
  const path='tools/closed-enquiry-retention/WpCaptureResource.php';const bytes=read(path);assert.equal(sha256(bytes),SOURCE_SHA256[path]);
  const source=bytes.toString();assert.equal(RULE_SPANS.length,4);
  for(const {start,end_exclusive,sha256:pin} of RULE_SPANS)assert.equal(sha256(Buffer.from(source.slice(source.indexOf(start),source.indexOf(end_exclusive)))),pin);
  const {outputs}=buildG5RuntimeCandidate();assert.equal(sha256(outputs['plugin/includes/candidate/closed-enquiry-retention/CaptureRules.php']),OUTPUT_SHA256['plugin/includes/candidate/closed-enquiry-retention/CaptureRules.php']);
});
test('native fixture pin is separate from runtime authority',()=>{
  const bytes=readG5NativeFixture();assert.equal(sha256(bytes),NATIVE_SHA256);assert.match(bytes.toString(),/SyntheticWitness/);assert.match(bytes.toString(),/actual_provider_accepted'=>false/);
  assert.throws(()=>readG5NativeFixture({read:()=>Buffer.from('changed')}),/G5_PREIMAGE_CHANGED/);
});
test('repeated builds are deterministic and contain no runtime fixture authority',()=>{
  const a=buildG5RuntimeCandidate();const b=buildG5RuntimeCandidate();assert.deepEqual(a,b);
  const newNames=Object.keys(CANDIDATE_SHA256).map(p=>p.slice(p.indexOf('/candidate/')+'/candidate/'.length));
  for(const name of newNames)assert.doesNotMatch(a.outputs[name].toString(),/LabAdapters\.php|ReceiverPipe\.php|TestDoubles\.php|SyntheticWitness|SyntheticEvidence|\/opt\/lab\/|[A-Z]:[\\/]/);
  assert.ok(a.manifest.remaining.includes('canonical_common_connection_lease'));assert.ok(a.manifest.remaining.includes('ActualPreferenceRetention.php'));assert.ok(a.manifest.remaining.includes('ActualRetirementPort.php'));
});
test('fixed lab wrapper refuses an ordinary repository or desktop path',()=>{
  assert.throws(()=>buildG5RuntimeLab(),/G5_FIXED_LAB_BUILD_PATH_REQUIRED/);
});
