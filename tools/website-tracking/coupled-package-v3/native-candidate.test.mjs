import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {resolve,join} from 'node:path';
import {fileURLToPath,pathToFileURL} from 'node:url';
import {buildG36Native,deriveNative,reverseNative,digest,PREIMAGES,PROFILE} from './build-native.mjs';
import {buildG36LabPacket} from '../../staging-lab/build-coupled-canonical-v3-lab.mjs';
const root=resolve(process.env.BSRE_SOURCE_ROOT||fileURLToPath(new URL('../../../',import.meta.url)));
const built=await buildG36Native({source_root:root});
const originals={bootstrap:readFileSync(join(root,'tools/staging-lab/canonical-lease-bootstrap-native.php')),
  route:(await import(pathToFileURL(join(root,'tools/website-tracking/canonical-lease/build-route-native.mjs')).href)).buildCanonicalRouteNative().php,
  purpose:readFileSync(join(root,'tools/staging-lab/canonical-purpose-native.php'))};
const names={bootstrap:'bootstrap-native.php',route:'route-native.php',purpose:'purpose-native.php'};
for(const name of Object.keys(names))test('G36 '+name+' derives and fully reverses its accepted G35 preimage',()=>{
  const bytes=built.files.get(names[name]),receipt=built.receipts[name];
  assert.equal(receipt.input_sha256,PREIMAGES[name]);assert.equal(receipt.output_sha256,digest(bytes));
  assert.equal(receipt.reverse_verified,true);assert.ok(reverseNative(bytes,receipt).equals(originals[name]));
  assert.ok(receipt.edits.every(r=>Number.isSafeInteger(r.offset)&&r.offset>=0&&r.before!==r.after));
});
test('unreviewed source bytes cannot enter a native derivative',()=>{
  assert.throws(()=>deriveNative(Buffer.concat([originals.bootstrap,Buffer.from('\n')]),PREIMAGES.bootstrap,[]),/PREIMAGE_CHANGED/);
});
test('changed and duplicate exact anchors fail closed',()=>{
  const b=Buffer.from('fixture fixture');
  assert.throws(()=>deriveNative(b,digest(b),[{before:'fixture',after:'other',count:1,label:'duplicate'}]),/ANCHOR_CHANGED/);
  assert.throws(()=>deriveNative(b,digest(b),[{before:'absent',after:'other',label:'missing'}]),/ANCHOR_CHANGED/);
});
test('reverse rejects altered output and altered edit position',()=>{
  const bytes=built.files.get(names.bootstrap),r=built.receipts.bootstrap;
  assert.throws(()=>reverseNative(Buffer.concat([bytes,Buffer.from('\n')]),r),/OUTPUT_CHANGED/);
  const changed=structuredClone(r);changed.edits[0].offset++;
  assert.throws(()=>reverseNative(bytes,changed),/REVERSE_/);
});
test('all literal hashes, original methods and old check names remain unchanged',()=>{
  for(const name of Object.keys(names)){
    const before=originals[name].toString(),after=built.files.get(names[name]).toString();
    assert.deepEqual([...after.matchAll(/['"]([a-f0-9]{64})['"]/g)].map(r=>r[1]),[...before.matchAll(/['"]([a-f0-9]{64})['"]/g)].map(r=>r[1]));
    assert.deepEqual([...after.matchAll(/function\s+([A-Za-z0-9_]+)/g)].map(r=>r[1]),[...before.matchAll(/function\s+([A-Za-z0-9_]+)/g)].map(r=>r[1]));
    assert.deepEqual([...after.matchAll(/(?:g35check|g3check|canonical_check|\$check)\('([^']*)'/g)].map(r=>r[1]),[...before.matchAll(/(?:g35check|g3check|canonical_check|\$check)\('([^']*)'/g)].map(r=>r[1]));
    assert.ok(!after.includes('/opt/lab/g35')&&!after.includes('/tmp/g35'));
  }
});
test('bootstrap closes the exact67 site/64 source inventories without broad number edits',()=>{
  const b=built.files.get(names.bootstrap).toString();
  assert.ok(b.includes("count($build['files'])===67")&&b.includes("count($manifest['files'])===64")&&b.includes("$build['profile']==='"+PROFILE+"'"));
  assert.equal((b.match(/count\(\$site\['files'\]\)===67/g)||[]).length,2);
  assert.ok(b.includes("copy_exact_58_verified_source_files")&&b.includes("pre_source58_manifest_and_hashes_verified"));
  assert.ok(b.includes("hash_file('sha256',$classFile)==='a358c8f28a6186ce5bc452aa699c93ddd96fb71b58528f1e21acc9e42b854b58'"));
});
test('route derives fixed G36 phases and reconciles final hub before inherited draft setup',()=>{
  const r=built.files.get(names.route).toString();
  assert.ok(r.indexOf('\\BSRE\\G36Native\\reconcile();')<r.indexOf('$pages=E\\ensure_drafts(false)'));
  for(const phase of ['g36_route_context','g36_canonical_custody'])assert.ok(r.includes("'phase'=>'"+phase+"'"));
  assert.deepEqual(built.inherited_checks,{route:101,forwards:20,custody_routes:63,custody_loss:69,purpose:43});
});
const packet=await buildG36LabPacket({source_root:root});
test('synthetic lab packet isolates exact67 site files and unchanged external companion',()=>{
  assert.equal(packet.site.size,67);assert.equal(packet.summary.plugin_files,66);assert.equal(packet.summary.source_members,64);
  assert.ok([...packet.site.keys()].every(p=>p==='wp-content/db.php'||p.startsWith('wp-content/plugins/bsre-enquiries/')));
  assert.equal(digest(packet.receiver),packet.receiver_v2_sha256);
  assert.equal(packet.receiver_v2_sha256,'00b62f1edc8996ab4f566a80155715a85f741bc5d68e7a0a54c94fc4ef2cbdc5');
  const build=JSON.parse(packet.auxiliary.get('BUILD.json'));assert.deepEqual(Object.keys(build),['profile','files']);assert.equal(build.files.length,67);
  for(const row of build.files)assert.equal(row.sha256,digest(packet.site.get(row.path)));
});
test('candidate native hub and all six full-contact sources bind final synthetic contact bytes',()=>{
  const base='wp-content/plugins/bsre-enquiries/',m=JSON.parse(packet.site.get(base+'includes/candidate/runtime/canonical-source.json'));
  assert.equal(m.profile,PROFILE);assert.equal(Object.keys(m.files).length,64);
  assert.ok(packet.site.get(base+'includes/parent-isolation.php').toString().includes("const OWNED_HUB_SHA256 = '"+digest(packet.site.get(base+'templates/source/hub.html'))+"';"));
  for(const name of ['hub','off-plan','resale','rent','sell','let']){
    const path='templates/source/'+name+'.html',bytes=packet.site.get(base+path),body=bytes.toString();assert.equal(digest(bytes),m.files[path]);
    assert.equal(body.split('tel:+19995550123').length-1,name==='hub'?1:3);assert.equal(body.split('https://wa.me/19995550123').length-1,name==='hub'?0:3);
    assert.ok(!body.includes('971568285677')&&!body.includes('+971 56 828 5677'));
  }
});
test('native proof files remain outside plugin manifest and missing operational ports remain absent',()=>{
  const all=[...packet.site.keys()];assert.ok(!all.some(p=>p.endsWith('contact-abi.php')||p.endsWith('contact-native.php')));
  for(const p of ['retention/ActualPreferenceRetention.php','receiver/ActualRetirementPort.php'])assert.ok(!all.includes('wp-content/plugins/bsre-enquiries/includes/candidate/'+p));
  assert.equal(packet.auxiliary.get('contact-native.php').toString().split("'g36_coupled_contact_abi'").length-1,1);
  assert.equal(packet.summary.native_executed,false);
});
