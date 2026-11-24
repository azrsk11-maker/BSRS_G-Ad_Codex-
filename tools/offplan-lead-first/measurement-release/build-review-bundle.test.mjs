import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync, writeFileSync, mkdirSync, mkdtempSync, rmSync, existsSync} from 'node:fs';
import {join, resolve, relative, isAbsolute, dirname} from 'node:path';
import {pathToFileURL, fileURLToPath} from 'node:url';
import {spawnSync} from 'node:child_process';
import {buildReviewModel, bumpVersion, transformVerifiedMap, verifyInstalledRoot, verifyBundle,
  writeReviewBundle, sha, PIN} from './build-review-bundle.mjs';

// CI supplies existing Source and a private/temp output root. No private audit or full fixture copy is needed.
assert.ok(process.env.BSRE_SOURCE_ROOT && process.env.BSRE_MEASUREMENT_TEST_OUTPUT, 'Set BSRE_SOURCE_ROOT and BSRE_MEASUREMENT_TEST_OUTPUT');
const sourceRoot = resolve(process.env.BSRE_SOURCE_ROOT), outputRoot = resolve(process.env.BSRE_MEASUREMENT_TEST_OUTPUT);
const {readRegularTree} = await import(pathToFileURL(join(sourceRoot,'tools/website-tracking/coupled-package/compose.mjs')).href);
const captureRoot = join(sourceRoot,'tools/staging-lab/fixtures/bsre-enquiries');
const fixture = readRegularTree(captureRoot);
const temporary = mkdtempSync(join(outputRoot, '.measurement-focused-test-'));
function cleanup() {
  const r = relative(outputRoot, resolve(temporary));
  assert.ok(r && !r.startsWith('..') && !isAbsolute(r)); rmSync(temporary, {recursive: true});
}
process.on('exit', cleanup);
const frame = 'assets/google-measurement.js', entry = 'bsre-enquiries.php';
const originalEntry = readFileSync(join(captureRoot,entry));
const rows = [...fixture].map(([path,b]) => ({path,bytes:b.length,current_raw_sha256:sha(b)}));
const freshNames = ['assets/lead.js',frame,'assets/google-runtime.js','includes/measurement-runtime.php',
  'includes/parent-isolation.php','includes/presentation.php','templates/page.php','templates/hub.php','includes/measurement-settings.php'];
const observedRow = p => ({path:p,bytes:fixture.get(p).length,sha256:sha(fixture.get(p))});
function jsonFile(name, value) { const file=join(temporary,name); writeFileSync(file,JSON.stringify(value,null,2)+'\n'); return file; }
const freshAudit = jsonFile('synthetic-editor.json',{plugin:'bsre-enquiries',version_header:'0.2.12',files:freshNames.map(observedRow),
  observed_at_utc:'SYNTHETIC_SOURCE_FIXTURE_ONLY',measurement_controls:'ALL_OFF',code_saved:false});
const normalizedEntry = Buffer.from(originalEntry.toString('utf8').replaceAll('\r\n','\n'),'utf8');
const extraAudit = jsonFile('synthetic-extra-editor.json',{raw_server_byte_identity_claimed:false,
  observed_at_utc:'SYNTHETIC_SOURCE_FIXTURE_ONLY',files:[{path:entry,bytes:normalizedEntry.length,sha256:sha(normalizedEntry)},
    observedRow('assets/consent-bridge.js'),observedRow('templates/source/off-plan.html')]});
const historicalReceipt = jsonFile('synthetic-raw.json',{results:rows,verified_utc:'SYNTHETIC_SOURCE_FIXTURE_ONLY'});
const bindings = jsonFile('synthetic-bindings.json',{schema:'bsre-private-measurement-input-bindings-v1',classification:'SYNTHETIC_SOURCE_FIXTURE_ONLY',
  fresh_editor_audit_sha256:sha(readFileSync(freshAudit)),extra_editor_audit_sha256:sha(readFileSync(extraAudit)),
  historical_raw_receipt_sha256:sha(readFileSync(historicalReceipt))});
const options = {sourceRoot,captureRoot,freshAudit,extraAudit,historicalReceipt,bindings};
const model = await buildReviewModel(options);
const copyMap = map => new Map([...map].map(([p,b]) => [p,Buffer.from(b)]));

test('deterministic portable bundle changes exactly two of thirty members and always stays held', async () => {
  const again = await buildReviewModel(options);
  assert.deepEqual([...model.files.keys()], [...again.files.keys()]);
  for (const [p, bytes] of model.files) assert.ok(bytes.equals(again.files.get(p)));
  assert.equal(model.original.size, 30); assert.equal(model.proposed.size, 30);
  assert.deepEqual([...model.original.keys()].filter(p => !model.original.get(p).equals(model.proposed.get(p))).sort(), [frame,entry].sort());
  assert.equal(model.manifest.ready_to_install, false); assert.equal(model.manifest.deployment_prohibited, true);
  assert.equal(model.manifest.evidence.fresh_entrypoint_editor_hash_available, true);
  assert.equal(model.manifest.evidence.fresh_entrypoint_raw_identity_verified, false);
  assert.equal(model.manifest.evidence.entrypoint_editor_representation.transformation_applied_to_patch_inputs, false);
  assert.equal(model.manifest.evidence.input_classification, 'SYNTHETIC_SOURCE_FIXTURE_ONLY');
  assert.equal(model.manifest.complete_plugin_zip, false); assert.equal(model.files.size, 7);
  assert.equal([...model.files.keys()].some(p => /\.zip$/i.test(p)), false);
  assert.equal(sha(model.proposed.get(frame)), PIN.frameAfter);
  assert.equal(model.manifest.before_inventory.length, 30); assert.equal(model.manifest.after_inventory.length, 30);
});

test('version patch changes only two final digits and preserves mixed line endings and other bytes', () => {
  const result = bumpVersion(originalEntry), after = result.bytes;
  assert.equal(after.length, originalEntry.length);
  const changes = [...originalEntry.keys()].filter(i => originalEntry[i] !== after[i]);
  assert.equal(changes.length, 2);
  for (const i of changes) { assert.equal(originalEntry[i], 50); assert.equal(after[i], 51); }
  assert.equal(after.toString('utf8').split('0.2.13').length - 1, 2);
  assert.equal(after.toString('utf8').includes('0.2.12'), false);
  assert.equal((after.toString('utf8').match(/\r\n/g) || []).length, 1);
  assert.deepEqual(after, model.proposed.get(entry)); assert.equal(result.edits.length, 2);
});

test('complete exact preimage and rollback guards preserve all original bytes, including contacts and protocol', () => {
  const forward = transformVerifiedMap(model.original, model, 'forward');
  const reverse = transformVerifiedMap(forward, model, 'rollback');
  for (const [p, bytes] of model.original) assert.ok(reverse.get(p).equals(bytes));
  for (const member of [entry,frame,'assets/lead.js','includes/protocol.php']) {
    const drift = copyMap(model.original); drift.get(member)[0] ^= 1;
    assert.throws(() => transformVerifiedMap(drift, model, 'forward'), /INSTALLED_PREIMAGE_CHANGED/);
  }
  const missing = copyMap(model.original); missing.delete('assets/lead.js');
  assert.throws(() => transformVerifiedMap(missing, model), /MEMBER_SET_MISMATCH/);
  const extra = copyMap(model.original); extra.set('unexpected.php', Buffer.from('unexpected'));
  assert.throws(() => transformVerifiedMap(extra, model), /MEMBER_SET_MISMATCH/);
  assert.throws(() => transformVerifiedMap(model.original, model, 'rollback'), /INSTALLED_PREIMAGE_CHANGED/);
  const partial = copyMap(model.original); partial.set(frame,model.proposed.get(frame));
  for (const direction of ['forward','rollback']) assert.throws(() => transformVerifiedMap(partial,model,direction), /INSTALLED_PREIMAGE_CHANGED/);
  assert.throws(() => transformVerifiedMap(model.original, model, 'install'), /DIRECTION_INVALID/);
});

test('full-byte entrypoint guard rejects drift and editor-normalized bytes rather than accepting a new pin', () => {
  assert.throws(() => bumpVersion(Buffer.concat([originalEntry, Buffer.from('\n')])), /ENTRY_PREIMAGE_CHANGED/);
  const drift = Buffer.from(originalEntry); drift[10] ^= 1;
  assert.throws(() => bumpVersion(drift), /ENTRY_PREIMAGE_CHANGED/);
  assert.equal(sha(normalizedEntry), '1c349529207e9e4ae15bf7b168aaea2d43f7119f6cad4b2dbc5ac4817d641d13');
  assert.throws(() => bumpVersion(normalizedEntry), /ENTRY_PREIMAGE_CHANGED/);
});

test('bound evidence rejects changes and does not claim supplied pins establish release authority', async () => {
  for (const [option,code] of [['freshAudit','FRESH_AUDIT_CHANGED'],['historicalReceipt','HISTORICAL_RECEIPT_CHANGED'],['extraAudit','EXTRA_AUDIT_CHANGED']]) {
    const invalid = jsonFile('invalid-'+option+'.json',{});
    await assert.rejects(buildReviewModel({...options,[option]:invalid}),new RegExp(code));
  }
  const invalidBindings=jsonFile('invalid-bindings.json',{ready_to_install:true});
  await assert.rejects(buildReviewModel({...options,bindings:invalidBindings}),/INPUT_BINDINGS_INVALID/);
  assert.equal(model.manifest.evidence.supplied_bindings_are_not_release_authority,true);
  await assert.rejects(buildReviewModel(),/EXPLICIT_INPUT_PATHS_REQUIRED/);
});

test('incomplete raw capture rejects with no full plugin copies or partial release output', async () => {
  const incomplete=join(temporary,'incomplete');mkdirSync(incomplete);writeFileSync(join(incomplete,'tiny.php'),'test only');
  await assert.rejects(buildReviewModel({...options,captureRoot:incomplete}),/MEMBER_SET_MISMATCH/);
});

test('duplicate or substituted editor observations cannot inflate the twelve-member evidence coverage', async () => {
  const originalBindings=JSON.parse(readFileSync(bindings,'utf8'));
  for(const [option,pinKey,code,mutate] of [
    ['freshAudit','fresh_editor_audit_sha256','FRESH_AUDIT_SCOPE_CHANGED',j=>{j.files[1]=j.files[0];}],
    ['freshAudit','fresh_editor_audit_sha256','FRESH_AUDIT_SCOPE_CHANGED',j=>{j.files[1]=observedRow('assets/consent-bridge.js');}],
    ['extraAudit','extra_editor_audit_sha256','EXTRA_AUDIT_SCOPE_CHANGED',j=>{j.files[1]=j.files[0];}],
  ]) {
    const changed=JSON.parse(readFileSync(options[option],'utf8'));mutate(changed);
    const changedFile=jsonFile('cohort-'+option+'-'+code+'.json',changed);
    const rebound=jsonFile('cohort-bindings-'+option+'.json',{...originalBindings,[pinKey]:sha(readFileSync(changedFile))});
    await assert.rejects(buildReviewModel({...options,[option]:changedFile,bindings:rebound}),new RegExp(code));
  }
});

test('read-only verifier binds full inventory, both rollback originals and manifest bytes', async () => {
  const bundle=join(temporary,'bundle');writeReviewBundle(bundle,model,{outputRoot});
  await verifyBundle(bundle,options);
  const result=await verifyInstalledRoot({bundleRoot:bundle,installedRoot:captureRoot,direction:'forward'},options);
  assert.equal(result.checked_members,30);assert.equal(result.would_change_members,2);
  assert.equal(result.ready_to_install,false);assert.equal(result.installer_executed,false);assert.equal(result.input_writes,0);
  for (const sub of ['forward','rollback']) {
    const payload=join(bundle,sub,entry),good=readFileSync(payload);
    writeFileSync(payload,Buffer.concat([good,Buffer.from('\n')]));
    await assert.rejects(verifyBundle(bundle,options),/BUNDLE_BYTES_CHANGED/);writeFileSync(payload,good);
  }
  const manifest=join(bundle,'MANIFEST.json'),text=readFileSync(manifest,'utf8');
  writeFileSync(manifest,text.replace('"ready_to_install": false','"ready_to_install": true'));
  await assert.rejects(verifyBundle(bundle,options),/BUNDLE_BYTES_CHANGED/);writeFileSync(manifest,text);
  writeFileSync(join(bundle,'extra.php'),'extra');
  await assert.rejects(verifyBundle(bundle,options),/MEMBER_SET_MISMATCH/);
});

test('writer requires explicit disjoint output ownership and leaves all Source fixture bytes untouched', () => {
  assert.throws(() => writeReviewBundle(join(temporary,'no-root'),model),/EXPLICIT_OUTPUT_ROOT_REQUIRED/);
  assert.throws(() => writeReviewBundle(temporary,model,{outputRoot}),/NEW_OWNED_OUTPUT_REQUIRED/);
  assert.throws(() => writeReviewBundle(join(sourceRoot,'forbidden-new-output'),model,{outputRoot:sourceRoot}),/OUTPUT_INPUT_ROOT_OVERLAP/);
  assert.throws(() => writeReviewBundle(resolve(outputRoot,'../outside-output'),model,{outputRoot}),/NEW_OWNED_OUTPUT_REQUIRED/);
  for(const [p,b] of fixture)assert.ok(readFileSync(join(captureRoot,...p.split('/'))).equals(b));
});

test('CLI fails closed without explicit paths and reports only a bounded symbolic error', () => {
  const result=spawnSync(process.execPath,[fileURLToPath(new URL('./build-review-bundle.mjs',import.meta.url)),'build','--output',join(temporary,'cli-missing-inputs'),'--output-root',outputRoot],{encoding:'utf8'});
  assert.equal(result.status,1);assert.deepEqual(JSON.parse(result.stderr),{status:'REJECTED',code:'EXPLICIT_INPUT_PATHS_REQUIRED',ready_to_install:false});
  assert.equal(existsSync(join(temporary,'cli-missing-inputs')),false);
});
