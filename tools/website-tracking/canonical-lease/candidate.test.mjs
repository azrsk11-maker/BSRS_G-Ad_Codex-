import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {buildCanonicalLeaseCandidate,sha256} from './build-candidate.mjs';
import {buildCanonicalRouteNative} from './build-route-native.mjs';
import {buildG34ProfileCandidate} from '../tracking-system/build-g34-profile-candidate.mjs';
import {buildG5RuntimeCandidate} from '../g5-runtime-ports/build-candidate.mjs';
const audit=readFileSync(new URL('../../../docs/audit/INSTALLED_SOURCE_COMPARISON_2026-11-07.json',import.meta.url));
test('separate site candidate binds first-db drop-in, exact55code members and producer without circular pins',()=>{
 const result=buildCanonicalLeaseCandidate(audit),files=new Map(result.files.map(row=>[row.path,Buffer.from(row.content_base64,'base64')]));
 assert.equal(result.files.length,58);assert.equal(files.size,58);assert.equal(result.default_enabled,false);
 assert.equal(result.full_profile_complete,false);assert.equal(result.provider_accepted,false);assert.equal(result.deployment_prohibited,true);
 for(const row of result.files)assert.equal(sha256(files.get(row.path)),row.sha256);
 const root='wp-content/plugins/bsre-enquiries/',manifest=files.get(root+'includes/candidate/runtime/canonical-source.json');
 const value=JSON.parse(manifest);assert.equal(Object.keys(value.files).length,55);assert.equal(sha256(manifest),result.source_manifest_sha256);
 for(const [path,pin]of Object.entries(value.files))assert.equal(sha256(files.get(root+path)),pin);
 assert.equal(value.files['includes/candidate/runtime/CanonicalCaptureProducer.php'],undefined);
 const producer=files.get(root+'includes/candidate/runtime/CanonicalCaptureProducer.php');assert.equal(sha256(producer),result.producer_sha256);
 const dropin=files.get('wp-content/db.php').toString();assert.ok(dropin.includes(result.producer_sha256)&&dropin.includes(result.source_manifest_sha256));
 assert.equal(dropin.includes('__BSRE_'),false);assert.equal(producer.toString().includes('__BSRE_'),false);
});
test('all originalG34/G5members remain exact except one reversible class-only main include',()=>{
 const actual=new Map(buildCanonicalLeaseCandidate(audit).files.map(row=>[row.path,Buffer.from(row.content_base64,'base64')])),root='wp-content/plugins/bsre-enquiries/';
 for(const row of buildG34ProfileCandidate(audit).files){
  const expected=Buffer.from(row.content_base64,'base64'),body=actual.get(root+row.path);
  if(row.path==='bsre-enquiries.php'){
   assert.deepEqual(body.subarray(0,expected.length),expected);
   assert.equal(body.subarray(expected.length).toString(),"\n// Explicit G35 code guard only; no operational authority or activation.\nrequire_once __DIR__.'/includes/candidate/runtime/CanonicalCaptureProducer.php';\n");
  }else assert.deepEqual(body,expected,row.path);
 }
 for(const [path,body]of Object.entries(buildG5RuntimeCandidate().outputs))assert.deepEqual(actual.get(root+path.replace(/^plugin\//,'')),body,path);
});
test('the build is deterministic and emits no synthetic authority fixture as runtime code',()=>{
 const a=buildCanonicalLeaseCandidate(audit),b=buildCanonicalLeaseCandidate(audit);assert.deepEqual(a,b);
 assert.equal(a.files.some(row=>/native\.php|test|BUILD\.json/.test(row.path)),false);
 assert.equal(a.files.some(row=>Buffer.from(row.content_base64,'base64').includes(Buffer.from('class SyntheticWitness'))),false);
});
test('native route derivation preserves old assertions and excludes second-handle substitution',()=>{
 const result=buildCanonicalRouteNative(),text=result.php.toString();assert.equal(result.original_route_recovered,true);assert.equal(result.ordered_edits,7);
 for(const token of ['exact_receiver_row_and_email_count','receiver_rows_emails_identity_exact_once','_actual_canonical_producer_accepts_retained_row','new G5\\ActualJournal($wpdb',"$wpdb->query('SELECT 1')",'G5_LEASE_RELEASE_UNCONFIRMED'])assert.ok(text.includes(token),token);
 assert.equal(text.includes("define('WP_CONTENT_DIR','/opt/lab/g35/wp-content')"),true);
 assert.equal(text.includes("get_class($wpdb)==='BSRE\\ClosedRetention\\LeaseBoundWpdb'"),true);
});
