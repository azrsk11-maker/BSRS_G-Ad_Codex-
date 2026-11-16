import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {resolve} from 'node:path';
import {fileURLToPath,pathToFileURL} from 'node:url';
import {createHash} from 'node:crypto';
import {buildCanonicalCaptureProducer,verifyCanonicalProducerSources} from './build-canonical-capture-producer.mjs';
const source=resolve(process.env.BSRE_CANONICAL_PRODUCER_TEST_SOURCE||fileURLToPath(new URL('../../../',import.meta.url)));
const {buildG34ProfileCandidate}=await import(pathToFileURL(resolve(source,'tools/website-tracking/tracking-system/build-g34-profile-candidate.mjs')));
const {buildG5RuntimeCandidate}=await import(pathToFileURL(resolve(source,'tools/website-tracking/g5-runtime-ports/build-candidate.mjs')));
const sha=b=>createHash('sha256').update(b).digest('hex');
const files=new Map(buildG34ProfileCandidate(readFileSync(resolve(source,'docs/audit/INSTALLED_SOURCE_COMPARISON_2026-11-07.json'))).files.map(r=>[r.path,Buffer.from(r.content_base64,'base64')]));
for(const [p,b]of Object.entries(buildG5RuntimeCandidate().outputs)){const path=p.replace(/^plugin\//,'');assert(!files.has(path));files.set(path,b);}
const before=files.get('bsre-enquiries.php');const append=Buffer.from("\nrequire_once __DIR__ . '/includes/candidate/runtime/CanonicalCaptureProducer.php';\n");
files.set('bsre-enquiries.php',Buffer.concat([before,append]));assert.equal(files.size,55);
const value={schema:'bsre-canonical-lease-source-v1',profile:'G35_CANONICAL_LEASE_CODE_ONLY',files:Object.fromEntries([...files].sort(([a],[b])=>a.localeCompare(b)).map(([p,b])=>[p,sha(b)])),deployment_prohibited:true};
const raw=Buffer.from(JSON.stringify(value,null,2)+'\n');const encode=v=>Buffer.from(JSON.stringify(v));
test('renderer binds actual 55-member G34/G5 source and class-only main bytes',()=>{
 assert.equal(verifyCanonicalProducerSources(raw,p=>files.get(p)),true);const r=buildCanonicalCaptureProducer(raw);
 assert.equal(r.manifest_sha256,sha(raw));assert.equal(r.producer_sha256,sha(r.producer));assert.equal(r.provider_authority,false);assert.equal(r.operational_retention_accepted,false);
 assert.equal(r.producer.toString().includes('__BSRE_CODE_MANIFEST_SHA256__'),false);assert.match(r.producer.toString(),new RegExp("MANIFEST_SHA256='"+sha(raw)+"'"));
 assert.deepEqual(files.get('bsre-enquiries.php').subarray(0,-append.length),before);
});
test('one changed actual source byte fails the complete source verifier',()=>{
 const target='includes/g2-profile/purpose-store.php';assert.throws(()=>verifyCanonicalProducerSources(raw,p=>p===target?Buffer.concat([files.get(p),Buffer.from('\n')]):files.get(p)),/CANONICAL_SOURCE_CHANGED/);
});
test('a missing member fails without source fallback',()=>{
 assert.throws(()=>verifyCanonicalProducerSources(raw,p=>{if(p==='includes/g3-profile/route-context.php')throw new Error('absent');return files.get(p);}),/CANONICAL_SOURCE_UNAVAILABLE/);
});
test('closed source manifest rejects reduced, extra, unready and wrong-profile forms',()=>{
 for(const mutate of [v=>delete v.files['assets/lead.js'],v=>v.files.extra='a'.repeat(64),v=>v.deployment_prohibited=false,v=>v.profile='other',v=>v.accepted=true]){
  const bad=structuredClone(value);mutate(bad);assert.throws(()=>buildCanonicalCaptureProducer(encode(bad)),/CANONICAL_MANIFEST/);
 }
 assert.throws(()=>buildCanonicalCaptureProducer(value),/CANONICAL_MANIFEST_BYTES_REQUIRED/);
});
test('manifest rejects traversal, self/circular sources and missing required source identities',()=>{
 for(const name of ['../outside.php','includes/candidate/runtime/CanonicalCaptureProducer.php','includes/candidate/runtime/canonical-source.json']){
  const bad=structuredClone(value);delete bad.files['assets/lead.js'];bad.files[name]='a'.repeat(64);assert.throws(()=>buildCanonicalCaptureProducer(encode(bad)),/CANONICAL_MANIFEST/);
 }
 const bad=structuredClone(value);delete bad.files['includes/g2-profile/purpose-store.php'];bad.files['unused.php']='a'.repeat(64);assert.throws(()=>buildCanonicalCaptureProducer(encode(bad)),/CANONICAL_MANIFEST_SOURCE_SET_INCOMPLETE/);
});
test('raw manifest bytes are bound, not a caller-supplied digest certificate',()=>{
 const a=buildCanonicalCaptureProducer(raw),b=buildCanonicalCaptureProducer(Buffer.concat([raw,Buffer.from('\n')]));assert.notEqual(a.manifest_sha256,b.manifest_sha256);assert.notEqual(a.producer_sha256,b.producer_sha256);
 assert.deepEqual(a,buildCanonicalCaptureProducer(raw));
});
test('constructor exposes only the canonical connection and verifies loaded source identity',()=>{
 const text=buildCanonicalCaptureProducer(raw).producer.toString();assert.match(text,/function __construct\(private \\BSRE\\ClosedRetention\\LeaseBoundWpdb \$db\)/);
 assert.match(text,/new \\ReflectionClass/);assert.match(text,/new \\ReflectionFunction/);assert.match(text,/BSRE_CANONICAL_LEASE_BOOTSTRAPPED/);assert.match(text,/BSRE_CANONICAL_LEASE_PRODUCER_SHA256/);
 assert.doesNotMatch(text,/function __construct\([^)]*(?:array|manifest|authority|provider)/i);
});
test('code/store guard includes fresh schema, canonical repositories, final routes and admission readback',()=>{
 const text=buildCanonicalCaptureProducer(raw).producer.toString();for(const token of ['G\\inspect($db,true)','G\\Runtime::$db!==$db','P\\Runtime::$store!==$store','E\\consent_repository()!==$store','P\\repository()!==$store','SELECT DATABASE()','ROUTE_OWNER_CHANGED',"$gate['mode']??null","$readback['store_installed']??null"]){assert(text.includes(token),token);}
 assert.equal((text.match(/'\/receipt-recovery\/status'=>'status'/g)||[]).length,1);
});
test('purpose validation reuses pinned routines and preserves expired/asymmetric retained facts',()=>{
 const text=buildCanonicalCaptureProducer(raw).producer.toString();for(const token of ['P\\assert_record($row)','P\\normalize_touch($input,$purpose,$created)','P\\canonical($record)','$touch===null) continue','intdiv($touch->timestamp,1000)'])assert(text.includes(token),token);
 assert.doesNotMatch(text,/P\\(?:verified_touch|prepare_capture)\(/);assert.doesNotMatch(text,/touch->expires_at\s*[<=>]+\s*time\(/);
 assert.doesNotMatch(text,/add_action\(|register_rest_route\(|wp_mail\(|wp_remote_|proc_open\(|provider_authority\s*=>\s*true/);
 assert.ok(text.indexOf("foreach(['known','eligible','analytics','ad_measurement']")<text.indexOf('if((int)$version===0)'));
});
test('query exception is bound only to one canonical inherited pinned-core placeholder callback',()=>{
 const text=buildCanonicalCaptureProducer(raw).producer.toString();
 for(const token of ["WPDB_CORE_SHA256='e15403e90032dd0508811301505e491d4212de5152581a98f51b744a1a3903bd'",
  'array_keys($hook->callbacks)!==[0]','count($hook->callbacks[0])!==1',"($entry['accepted_args']??null)!==1","$callback[0]!==$this->db","$callback[1]!=='remove_placeholder_escape'",
  "get_class($hook)!=='WP_Hook'","$all->callbacks!==[]","new \\ReflectionMethod($this->db,$name)","$method->getDeclaringClass()->getName()!=='wpdb'",'hash_equals(self::WPDB_CORE_SHA256',"realpath((string)$method->getFileName())!==$core"]){assert(text.includes(token),token);}
 assert.doesNotMatch(text,/remove_filter\(|remove_all_filters\(|add_filter\(/);
});
