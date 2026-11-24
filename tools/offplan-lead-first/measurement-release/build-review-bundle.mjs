/** Private offline proposal. No installer, upload, plugin ZIP or network path. */
import {createHash, randomUUID} from 'node:crypto';
import {readFileSync, writeFileSync, mkdirSync, renameSync, rmSync, existsSync, lstatSync, realpathSync} from 'node:fs';
import {resolve, dirname, relative, isAbsolute, join} from 'node:path';
import {fileURLToPath, pathToFileURL} from 'node:url';

export const PIN = Object.freeze({
  frame: '2e87c3c715d74e09b459d02d706f72008b2edcfd73d0401bd6bfcbee64e9b837',
  frameAfter: 'd861b0df762b2b703f4b567305fc9e9f96113fcd3ddfdd82b4b5fc8545aeadfb',
  entry: '9a0bd37545bd0da326d592bae7ac78eff0a8b79085bd4b1542d65289d627855b',
});
const MODULES = Object.freeze({
  'tools/website-tracking/tracking-system/build-frame-delivery-candidate.mjs': '21c265855c5f7483a2febccffa011558cf6fa912ab6ab90002104e84b91cca54',
  'tools/website-tracking/coupled-package/compose.mjs': 'f96c2293723f3414f83d912895fc37db2c2d55401a296dc7f75efecd93a2d475',
  'tools/website-tracking/coupled-package/baseline-pins.json': 'f6d9b1d1c0b5225a8b7f1dcee96e198e5818c01c078a2af27c16451285e96d10',
  'tools/website-tracking/coupled-package/profile-contract.json': '284c4650ee124352dcf14383f408b601901bd39fdcccbb44d43c2d259053e039',
});
const FRAME = 'assets/google-measurement.js', ENTRY = 'bsre-enquiries.php';
const CHANGED = Object.freeze([FRAME, ENTRY].sort());
const EDITOR_NAMES = Object.freeze(['assets/lead.js',FRAME,'assets/google-runtime.js','includes/measurement-runtime.php',
  'includes/parent-isolation.php','includes/presentation.php','templates/page.php','templates/hub.php','includes/measurement-settings.php'].sort());
const EXTRA_EDITOR_NAMES = Object.freeze([ENTRY,'assets/consent-bridge.js','templates/source/off-plan.html'].sort());
const need = (ok, code) => { if (!ok) throw new Error(code); };
export const sha = bytes => createHash('sha256').update(bytes).digest('hex');
const json = object => Buffer.from(JSON.stringify(object, null, 2) + '\n', 'utf8');
const row = (path, bytes) => ({path, bytes: bytes.length, sha256: sha(bytes)});
const inside = (root, value) => { const r = relative(resolve(root), resolve(value)); return r !== '' && !r.startsWith('..') && !isAbsolute(r); };
const overlaps = (a,b) => resolve(a).toLowerCase() === resolve(b).toLowerCase() || inside(a,b) || inside(b,a);
const OPTION_KEYS = Object.freeze(['sourceRoot','captureRoot','historicalReceipt','freshAudit','extraAudit','bindings']);
function optionsFor(value) {
  need(value && typeof value === 'object' && OPTION_KEYS.every(k => typeof value[k] === 'string' && value[k].length > 0), 'EXPLICIT_INPUT_PATHS_REQUIRED');
  return value;
}
function inputBindings(file) {
  const bytes = readFileSync(regularPath(file)), pins = JSON.parse(bytes.toString('utf8'));
  const keys = ['schema','classification','fresh_editor_audit_sha256','extra_editor_audit_sha256','historical_raw_receipt_sha256'].sort();
  need(Object.keys(pins).sort().join(',') === keys.join(',') && pins.schema === 'bsre-private-measurement-input-bindings-v1' &&
    ['ACTUAL_PRIVATE_READBACK','SYNTHETIC_SOURCE_FIXTURE_ONLY'].includes(pins.classification), 'INPUT_BINDINGS_INVALID');
  for (const k of keys.filter(k => k.endsWith('_sha256'))) need(/^[a-f0-9]{64}$/.test(pins[k]), 'INPUT_BINDINGS_INVALID');
  return {pins, bytes};
}

function regularPath(file) {
  const absolute = resolve(file); let at = absolute;
  while (true) {
    need(existsSync(at) && !lstatSync(at).isSymbolicLink(), 'INPUT_LINK_OR_MISSING');
    const next = dirname(at); if (next === at) break; at = next;
  }
  need(realpathSync(absolute).toLowerCase() === absolute.toLowerCase(), 'INPUT_REDIRECTED');
  need(lstatSync(absolute).isFile() && lstatSync(absolute).size <= 1048576, 'INPUT_NOT_BOUNDED_FILE');
  return absolute;
}
function pinnedBytes(file, expected, code) {
  const bytes = readFileSync(regularPath(file)); need(sha(bytes) === expected, code); return bytes;
}
async function helpers(sourceRoot) {
  const pins = [];
  for (const [path, expected] of Object.entries(MODULES)) {
    const bytes = pinnedBytes(join(sourceRoot, ...path.split('/')), expected, 'SOURCE_DEPENDENCY_CHANGED');
    pins.push(row(path, bytes));
  }
  const common = await import(pathToFileURL(join(sourceRoot, 'tools/website-tracking/coupled-package/compose.mjs')).href);
  const frame = await import(pathToFileURL(join(sourceRoot, 'tools/website-tracking/tracking-system/build-frame-delivery-candidate.mjs')).href);
  return {...common, ...frame, sourcePins: pins};
}

export function bumpVersion(bytes) {
  need(Buffer.isBuffer(bytes) && sha(bytes) === PIN.entry, 'ENTRY_PREIMAGE_CHANGED');
  let output = Buffer.from(bytes);
  const edits = [];
  for (const [before, after] of [[" * Version: 0.2.12\n", " * Version: 0.2.13\n"],
    ["const PLUGIN_VERSION = '0.2.12';", "const PLUGIN_VERSION = '0.2.13';"]]) {
    const from = Buffer.from(before), to = Buffer.from(after), start = output.indexOf(from);
    need(start >= 0 && output.indexOf(from, start + from.length) === -1, 'VERSION_ANCHOR_CHANGED');
    output = Buffer.concat([output.subarray(0, start), to, output.subarray(start + from.length)]);
    edits.push({offset: start, before_utf8: before, after_utf8: after});
  }
  let inverse = Buffer.from(output);
  for (const edit of [...edits].reverse()) {
    const from = Buffer.from(edit.after_utf8), to = Buffer.from(edit.before_utf8);
    need(inverse.subarray(edit.offset, edit.offset + from.length).equals(from), 'VERSION_INVERSE_ANCHOR_CHANGED');
    inverse = Buffer.concat([inverse.subarray(0, edit.offset), to, inverse.subarray(edit.offset + from.length)]);
  }
  need(inverse.equals(bytes), 'VERSION_INVERSE_CHANGED');
  return {bytes: output, edits};
}

const HOLDS = Object.freeze([
  'CURRENT_EDITOR_EVIDENCE_COVERS_ONLY_TWELVE_MEMBERS',
  'ENTRYPOINT_EDITOR_NEWLINE_EQUIVALENCE_IS_NOT_CURRENT_RAW_FILE_IDENTITY',
  'FRESH_COMPLETE_THIRTY_MEMBER_PREIMAGE_AND_ENTRYPOINT_READBACK_REQUIRED',
  'CURRENT_SERVED_BYTES_AND_CACHE_VERSION_CONVERGENCE_REQUIRED',
  'CURRENT_GTM_PUBLISHED_BOOTSTRAP_AND_REVIEWED_PUBLICATION_REQUIRED',
  'ISOLATED_NATIVE_BROWSER_TLS_CSP_CONSENT_LEASE_ACCEPTANCE_REQUIRED',
  'GENUINE_INTAKE_SHEET_MAIL_AND_PROVIDER_DEDUP_ACCEPTANCE_REQUIRED',
  'INDEPENDENT_HUMAN_AND_EXACT_PRODUCTION_RELEASE_GATES_REQUIRED',
]);
const BUNDLE_README = Buffer.from(`# REVIEW ONLY — measurement patch and rollback\n\nThis is a two-file patch bundle, NOT a complete plugin, plugin ZIP, installer or approved release. Do not upload it with WordPress's plugin uploader or replace the plugin directory. Do not install either proposed member alone. All other plugin members, current contact, consent, routing, signed wire, receiver and intake remain unchanged.\n\nProposed changes: the existing bounded iframe accepted-event queue and primary plugin header/PLUGIN_VERSION 0.2.12 → 0.2.13. The global version change gives the existing renderer a new query version for its assets. No renderer/PHP logic change is proposed.\n\nforward/ contains proposed replacement bytes; rollback/ contains the exact original bytes. MANIFEST.json binds the complete expected 30-member before/after inventories. PATCHES.json describes both directions. Before any separately authorized transfer, the verifier requires an exact full local installed-file mirror; rollback verification requires exact postimages. It makes no writes to the supplied mirror. A full byte match never clears external acceptance or human gates: ready_to_install remains false.\n\nFresh evidence covers twelve editor representations. The entrypoint editor hash equals a CRLF-to-LF diagnostic view of the historical raw capture; this is NOT current raw-file identity. Patch inputs, proposed bytes and rollback retain the exact mixed-newline raw bytes. The complete raw inventory still comes from the pinned historical capture. Current opcache, served cache, GTM publication, native browser/privacy, genuine delivery/provider dedup and release acceptance are not inferred. Restore BOTH originals only after the exact rollback preimage check and authorized coordinator review.\n`, 'utf8');

export async function buildReviewModel(options) {
  const o = optionsFor(options), bound = inputBindings(o.bindings);
  const h = await helpers(o.sourceRoot);
  const auditBytes = pinnedBytes(o.freshAudit, bound.pins.fresh_editor_audit_sha256, 'FRESH_AUDIT_CHANGED');
  const extraAuditBytes = pinnedBytes(o.extraAudit, bound.pins.extra_editor_audit_sha256, 'EXTRA_AUDIT_CHANGED');
  const historicalBytes = pinnedBytes(o.historicalReceipt, bound.pins.historical_raw_receipt_sha256, 'HISTORICAL_RECEIPT_CHANGED');
  const audit = JSON.parse(auditBytes.toString('utf8')), historical = JSON.parse(historicalBytes.toString('utf8'));
  need(audit.plugin === 'bsre-enquiries' && audit.version_header === '0.2.12' && Array.isArray(audit.files) && audit.files.length === 9 &&
    new Set(audit.files.map(r => r?.path)).size === 9 && JSON.stringify(audit.files.map(r => r?.path).sort()) === JSON.stringify(EDITOR_NAMES) &&
    audit.measurement_controls === 'ALL_OFF' && audit.code_saved === false, 'FRESH_AUDIT_SCOPE_CHANGED');
  const names = historical.results.map(r => r.path).sort();
  need(names.length === 30 && new Set(names).size === 30, 'HISTORICAL_INVENTORY_CHANGED');
  const original = h.readRegularTree(o.captureRoot, names);
  for (const r of historical.results) {
    need(sha(original.get(r.path)) === r.current_raw_sha256 && original.get(r.path).length === r.bytes, 'CAPTURE_PREIMAGE_CHANGED');
  }
  for (const r of audit.files) {
    need(original.has(r.path) && sha(original.get(r.path)) === r.sha256 && original.get(r.path).length === r.bytes, 'FRESH_EDITOR_CAPTURE_MISMATCH');
  }
  const extraAudit = JSON.parse(extraAuditBytes.toString('utf8'));
  need(Array.isArray(extraAudit.files) && extraAudit.files.length === 3 && new Set(extraAudit.files.map(r => r?.path)).size === 3 &&
    JSON.stringify(extraAudit.files.map(r => r?.path).sort()) === JSON.stringify(EXTRA_EDITOR_NAMES) &&
    new Set([...audit.files,...extraAudit.files].map(r => r.path)).size === 12 &&
    extraAudit.raw_server_byte_identity_claimed === false, 'EXTRA_AUDIT_SCOPE_CHANGED');
  const entryEditor = extraAudit.files.find(r => r.path === ENTRY);
  const entryRaw = original.get(ENTRY), crlf = entryRaw.indexOf(Buffer.from('\r\n'));
  need(crlf === 13067 && entryRaw.indexOf(Buffer.from('\r\n'), crlf + 2) === -1, 'ENTRY_NEWLINE_DIAGNOSTIC_CHANGED');
  const diagnosticView = Buffer.concat([entryRaw.subarray(0, crlf), entryRaw.subarray(crlf + 1)]);
  need(entryEditor && entryEditor.sha256 === sha(diagnosticView) && entryEditor.bytes === diagnosticView.length,
    'ENTRY_EDITOR_REPRESENTATION_CHANGED');
  for (const r of extraAudit.files.filter(r => r.path !== ENTRY)) {
    need(original.has(r.path) && sha(original.get(r.path)) === r.sha256 && original.get(r.path).length === r.bytes,
      'EXTRA_EDITOR_CAPTURE_MISMATCH');
  }
  need(sha(original.get(FRAME)) === PIN.frame && sha(original.get(ENTRY)) === PIN.entry, 'PATCH_PREIMAGE_CHANGED');
  const frame = Buffer.from(h.buildFrameDeliveryCandidate(original.get(FRAME)), 'utf8');
  need(sha(frame) === PIN.frameAfter && frame.length === 7313, 'FRAME_CANDIDATE_CHANGED');
  const bumped = bumpVersion(original.get(ENTRY));
  const proposed = new Map([...original].map(([p, b]) => [p, Buffer.from(b)]));
  proposed.set(FRAME, frame); proposed.set(ENTRY, bumped.bytes);
  const changed = names.filter(p => !original.get(p).equals(proposed.get(p)));
  need(JSON.stringify(changed) === JSON.stringify(CHANGED), 'PATCH_SCOPE_CHANGED');
  const changes = CHANGED.map(p => ({path: p, before: row(p, original.get(p)), after: row(p, proposed.get(p)),
    forward_file: 'forward/' + p, rollback_file: 'rollback/' + p,
    derivation: p === FRAME ? 'EXISTING_HASH_BOUND_FRAME_BUILDER' : 'TWO_EXACT_VERSION_ANCHORS',
    inverse: 'EXACT_SAVED_ORIGINAL_BYTES'}));
  const manifest = {
    schema: 'bsre-private-measurement-patch-review-v1', classification: 'PRIVATE_REVIEW_ONLY_NOT_PLUGIN_PACKAGE',
    deployment_prohibited: true, ready_to_install: false, complete_plugin_zip: false, automatic_install_supported: false,
    derivation_source: 'EXACT_MODULE_HASHES', source_pins: h.sourcePins,
    evidence: {input_classification: bound.pins.classification, input_bindings_sha256: sha(bound.bytes),
      supplied_bindings_are_not_release_authority: true,
      fresh_editor_audit_sha256: bound.pins.fresh_editor_audit_sha256, fresh_editor_observed_at_utc: audit.observed_at_utc,
      original_editor_audit_member_count: 9, extra_editor_audit_member_count: 3, fresh_editor_member_count: 12,
      extra_editor_audit_sha256: bound.pins.extra_editor_audit_sha256, extra_editor_observed_at_utc: extraAudit.observed_at_utc,
      fresh_entrypoint_editor_hash_available: true, fresh_entrypoint_raw_identity_verified: false,
      entrypoint_editor_representation: {bytes: entryEditor.bytes, sha256: entryEditor.sha256,
        diagnostic_raw_CRLF_to_LF_match: true, diagnostic_CRLF_offset: crlf,
        transformation_applied_to_patch_inputs: false, raw_preimage_preserved: true},
      historical_raw_receipt_sha256: bound.pins.historical_raw_receipt_sha256, historical_raw_observed_at: historical.verified_utc,
      current_raw_host_snapshot_accepted: false, controls_at_audit: 'ALL_OFF'},
    plugin_version: {before: '0.2.12', after: '0.2.13', header_and_constant_only: true},
    counts: {complete_inventory: 30, proposed_replacement_files: 2, rollback_files: 2, byte_unchanged_members: 28},
    changes, version_edits: bumped.edits,
    before_inventory: names.map(p => row(p, original.get(p))), after_inventory: names.map(p => row(p, proposed.get(p))),
    release_holds: HOLDS,
    behavior_evidence_reused: {iframe_cases: 5, composed_cases: 4, live_or_provider_acceptance: false},
  };
  const operations = {schema: 'bsre-exact-replacement-review-v1', installer: false,
    forward: changes.map(c => ({member: c.path, requires_sha256: c.before.sha256, replacement: c.forward_file, result_sha256: c.after.sha256})),
    rollback: changes.map(c => ({member: c.path, requires_sha256: c.after.sha256, replacement: c.rollback_file, result_sha256: c.before.sha256}))};
  const files = new Map([['MANIFEST.json', json(manifest)], ['PATCHES.json', json(operations)], ['README.md', BUNDLE_README]]);
  for (const c of changes) { files.set(c.forward_file, proposed.get(c.path)); files.set(c.rollback_file, original.get(c.path)); }
  return {files, manifest, original, proposed, helpers: h, inputRoots: [resolve(o.sourceRoot),resolve(o.captureRoot)]};
}

export function transformVerifiedMap(input, model, direction = 'forward') {
  need(direction === 'forward' || direction === 'rollback', 'DIRECTION_INVALID');
  const expected = direction === 'forward' ? model.original : model.proposed;
  const output = direction === 'forward' ? model.proposed : model.original;
  const names = [...expected.keys()].sort();
  const checked = model.helpers.memberMap([...input].map(([path, bytes]) => ({path, bytes})), names);
  for (const p of names) need(checked.get(p).equals(expected.get(p)), 'INSTALLED_PREIMAGE_CHANGED');
  return new Map(names.map(p => [p, Buffer.from(output.get(p))])); // In-memory only; never writes input.
}

export async function verifyBundle(bundleRoot, options) {
  const model = await buildReviewModel(options);
  const found = model.helpers.readRegularTree(bundleRoot, [...model.files.keys()].sort());
  for (const [path, bytes] of model.files) need(found.get(path).equals(bytes), 'BUNDLE_BYTES_CHANGED');
  return model;
}
export async function verifyInstalledRoot({bundleRoot, installedRoot, direction = 'forward'}, options) {
  const model = await verifyBundle(bundleRoot, options);
  const input = model.helpers.readRegularTree(installedRoot, [...model.original.keys()].sort());
  const transformed = transformVerifiedMap(input, model, direction);
  return {status: 'EXACT_THIRTY_MEMBER_LOCAL_PREIMAGES_VERIFIED_REVIEW_HELD', direction,
    checked_members: input.size, would_change_members: CHANGED.length,
    resulting_inventory_sha256: sha(json([...transformed].map(([p,b]) => row(p,b)))),
    installer_executed: false, input_writes: 0, ready_to_install: false, deployment_prohibited: true,
    capture_freshness_or_external_gates_verified: false};
}

export function writeReviewBundle(destination, model, {outputRoot} = {}) {
  need(typeof outputRoot === 'string' && outputRoot.length > 0, 'EXPLICIT_OUTPUT_ROOT_REQUIRED');
  const ownedRoot = resolve(outputRoot);
  const absolute = resolve(destination), parent = dirname(absolute);
  need(inside(ownedRoot, absolute) && existsSync(ownedRoot) && lstatSync(ownedRoot).isDirectory() && existsSync(parent) && !existsSync(absolute), 'NEW_OWNED_OUTPUT_REQUIRED');
  need(model.inputRoots.every(input => !overlaps(input, ownedRoot)), 'OUTPUT_INPUT_ROOT_OVERLAP');
  let at = parent;
  while (true) { need(!lstatSync(at).isSymbolicLink(), 'OUTPUT_PARENT_LINK'); const next = dirname(at); if(next === at) break; at = next; }
  need(realpathSync(parent).toLowerCase() === parent.toLowerCase(), 'OUTPUT_REDIRECTED');
  need(model.manifest.deployment_prohibited === true && model.manifest.ready_to_install === false, 'REVIEW_HOLDS_REQUIRED');
  const temporary = join(parent, '.measurement-review-' + randomUUID());
  need(inside(ownedRoot, temporary), 'OUTPUT_BOUNDARY');
  try {
    mkdirSync(temporary);
    for (const [path, bytes] of model.files) {
      const file = join(temporary, ...path.split('/'));
      need(inside(temporary, file), 'OUTPUT_MEMBER_OUTSIDE');
      mkdirSync(dirname(file), {recursive: true}); writeFileSync(file, bytes, {flag: 'wx'});
    }
    renameSync(temporary, absolute);
  } catch (error) {
    // Only this newly allocated, boundary-checked private temporary directory is eligible.
    if (inside(ownedRoot, temporary) && existsSync(temporary)) rmSync(temporary, {recursive: true});
    throw error;
  }
  return {status: 'PRIVATE_REVIEW_BUNDLE_WRITTEN', files: model.files.size, changed_plugin_members: 2,
    manifest_sha256: sha(model.files.get('MANIFEST.json')), ready_to_install: false, deployment_prohibited: true};
}

function argumentsFor(argv) {
  const [command, ...rest] = argv, values = {};
  need(['build', 'verify'].includes(command) && rest.length % 2 === 0, 'CLI_ARGUMENTS_INVALID');
  const inputs = ['--source-root','--raw-snapshot','--historical-receipt','--editor-audit','--extra-editor-audit','--bindings'];
  const allowed = [...inputs, ...(command === 'build' ? ['--output','--output-root'] : ['--bundle', '--installed-root', '--direction'])];
  for (let i = 0; i < rest.length; i += 2) {
    need(allowed.includes(rest[i]) && !Object.hasOwn(values, rest[i]) && rest[i+1] && !rest[i+1].startsWith('--'), 'CLI_ARGUMENTS_INVALID');
    values[rest[i]] = rest[i+1];
  }
  return {command, values};
}
if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  try {
    const {command, values} = argumentsFor(process.argv.slice(2));
    const options = {sourceRoot: values['--source-root'], captureRoot: values['--raw-snapshot'],
      historicalReceipt: values['--historical-receipt'], freshAudit: values['--editor-audit'],
      extraAudit: values['--extra-editor-audit'], bindings: values['--bindings']};
    let result;
    if (command === 'build') {
      need(values['--output'] && values['--output-root'], 'OUTPUT_REQUIRED');
      result = writeReviewBundle(values['--output'], await buildReviewModel(options), {outputRoot: values['--output-root']});
    } else {
      need(values['--bundle'] && values['--installed-root'], 'VERIFY_INPUTS_REQUIRED');
      result = await verifyInstalledRoot({bundleRoot: values['--bundle'], installedRoot: values['--installed-root'], direction: values['--direction'] || 'forward'}, options);
    }
    process.stdout.write(JSON.stringify(result) + '\n');
  } catch (error) {
    const code = typeof error?.message === 'string' && /^[A-Z][A-Z0-9_]{0,96}$/.test(error.message) ? error.message : 'REVIEW_BUNDLE_FAILED';
    process.stderr.write(JSON.stringify({status: 'REJECTED', code, ready_to_install: false}) + '\n'); process.exitCode = 1;
  }
}
