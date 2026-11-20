/** Inert, offline composition. Actual captures, target identities and returned private
 * manifests must stay outside public source. This module never installs a package. */
import {createHash} from 'node:crypto';
import {readFileSync, lstatSync, readdirSync, realpathSync} from 'node:fs';
import {resolve, relative, sep, isAbsolute, join} from 'node:path';
import {pathToFileURL} from 'node:url';

const pins = JSON.parse(readFileSync(new URL('./baseline-pins.json', import.meta.url), 'utf8'));
const contract = JSON.parse(readFileSync(new URL('./profile-contract.json', import.meta.url), 'utf8'));
Object.freeze(contract.required_outputs); Object.freeze(contract.release_holds); Object.freeze(contract.canonical_action);
export const CONTRACT = Object.freeze(contract);
export const RECONCILIATION = Object.freeze(['assets/lead.js', 'templates/source/off-plan.html',
  'templates/source/resale.html', 'templates/source/rent.html', 'templates/source/sell.html',
  'templates/source/let.html', 'templates/source/hub.html', 'includes/parent-isolation.php']);
const CONTACT = RECONCILIATION.slice(0, -1), HUB = 'templates/source/hub.html', GUARD = 'includes/parent-isolation.php';
const LEAD = 'assets/lead.js', RENT = 'templates/source/rent.html';
const PREFIX = Buffer.from(String.raw`/^https:\/\/wa\.me\/`);
const SUFFIX = Buffer.from(String.raw`(?:\?|$)/.test(href)`);
const MAX_FILE = 1048576, MAX_TOTAL = 16777216;
const fail = code => { throw new Error(code); };
const need = (ok, code) => { if (!ok) fail(code); };
export const digest = value => createHash('sha256').update(value).digest('hex');
need(pins.original_zip_sha256 === 'f64910af55a72d5551d24ceb2cc7d2ffa666b7bd8579126d719463897bdf2443' &&
  pins.member_map_sha256 === '91e1be72d725b359a5c665022c5cc700aba9782bba7964115b19ab9ba34201d9' &&
  pins.receiver_sha256 === '6669cb28e5267a49e061427b736cdbdbad87bee6cbb946e99483d9439f61fa38' &&
  digest(JSON.stringify(Object.fromEntries(Object.keys(pins.members).sort().map(k=>[k,pins.members[k]])))) === pins.member_map_sha256,
  'PUBLIC_PROVENANCE_PIN_CHANGED');
const hash = value => typeof value === 'string' && /^[a-f0-9]{64}$/.test(value);
const utf8 = bytes => { need(Buffer.isBuffer(bytes), 'RAW_BYTES_REQUIRED'); const s = bytes.toString('utf8');
  need(Buffer.from(s, 'utf8').equals(bytes), 'INVALID_UTF8'); return s; };
function safePath(name) {
  need(typeof name === 'string' && name.length > 0 && name.length < 180 &&
    /^[a-zA-Z0-9_.\/-]+$/.test(name) && !name.includes('\\') && !name.startsWith('/') &&
    name.split('/').every(p => p !== '' && p !== '.' && p !== '..'), 'UNSAFE_MEMBER_PATH');
  return name;
}
export function memberMap(entries, exactNames = null) {
  need(Array.isArray(entries) && entries.length <= 100, 'MEMBER_LIST_REQUIRED');
  const map = new Map(), collision = new Set(); let total = 0;
  for (const row of entries) {
    need(row && typeof row === 'object', 'MEMBER_ROW_REQUIRED'); const name = safePath(row.path);
    need(!collision.has(name.toLowerCase()), 'DUPLICATE_MEMBER'); collision.add(name.toLowerCase());
    need(Buffer.isBuffer(row.bytes) && row.bytes.length > 0 && row.bytes.length <= MAX_FILE, 'MEMBER_SIZE_INVALID');
    total += row.bytes.length; need(total <= MAX_TOTAL, 'TOTAL_SIZE_INVALID'); map.set(name, Buffer.from(row.bytes));
  }
  if (exactNames) need(map.size === exactNames.length && exactNames.every(p => map.has(p)), 'MEMBER_SET_MISMATCH');
  return map;
}
function verifyHashes(map, expected, code) {
  need(expected && typeof expected === 'object' && !Array.isArray(expected), code);
  need(Object.keys(expected).length === map.size, code);
  for (const [name, bytes] of map) need(hash(expected[name]) && digest(bytes) === expected[name], code);
}
function literal(bytes) {
  const start = bytes.indexOf(PREFIX), from = start + PREFIX.length;
  need(start >= 0 && bytes.indexOf(PREFIX, from) === -1, 'CLIENT_MATCHER_ANCHOR');
  const end = bytes.indexOf(SUFFIX, from);
  need(end > from && bytes.indexOf(SUFFIX, end + SUFFIX.length) === -1, 'CLIENT_MATCHER_ANCHOR');
  const value = bytes.subarray(from, end).toString('ascii');
  need(/^[1-9][0-9]{6,14}$/.test(value), 'CLIENT_MATCHER_LITERAL'); return {from, end, value};
}
function identityShape(id) {
  need(id && typeof id === 'object', 'CONTACT_IDENTITY_REQUIRED');
  for (const field of ['from_digits', 'to_digits']) need(typeof id[field] === 'string' && /^[1-9][0-9]{6,14}$/.test(id[field]), 'CONTACT_IDENTITY_SHAPE');
  for (const [display, digits] of [['from_display','from_digits'], ['to_display','to_digits']])
    need(typeof id[display] === 'string' && /^\+[0-9 ]{7,22}$/.test(id[display]) && id[display].replace(/\D/g, '') === id[digits], 'CONTACT_DISPLAY_SHAPE');
  need(id.from_digits !== id.to_digits, 'CONTACT_TARGET_UNCHANGED');
}
function occurrences(bytes, needle) {
  const found = []; let at = 0;
  while ((at = bytes.indexOf(needle, at)) !== -1) { found.push(at); at += needle.length; }
  return found;
}
function edits(bytes, name, id) {
  utf8(bytes);
  if (name === LEAD) {
    const anchor = literal(bytes); need(anchor.value === id.from_digits, 'CLIENT_CONTACT_PREIMAGE');
    return [{start: anchor.from, before: Buffer.from(id.from_digits), after: Buffer.from(id.to_digits), kind: 'matcher'}];
  }
  const rules = [
    ['whatsapp', `https://wa.me/${id.from_digits}`, `https://wa.me/${id.to_digits}`],
    ['telephone', `tel:+${id.from_digits}`, `tel:+${id.to_digits}`],
    ['display', id.from_display, id.to_display],
  ];
  const result = [];
  for (const [kind, before, after] of rules) for (const start of occurrences(bytes, Buffer.from(before))) {
    if (kind !== 'display') need([34,39,63].includes(bytes[start + Buffer.byteLength(before)]), 'CONTACT_SUFFIX_CHANGED');
    result.push({start, before: Buffer.from(before), after: Buffer.from(after), kind});
  }
  need(result.length > 0, 'CONTACT_ANCHORS_MISSING'); return result.sort((a,b) => a.start - b.start);
}
function overlay(bytes, plan) {
  const out = []; let at = 0, delta = 0; const reversed = [];
  for (const edit of plan) {
    need(edit.start >= at && bytes.subarray(edit.start, edit.start + edit.before.length).equals(edit.before), 'OVERLAY_PREIMAGE');
    out.push(bytes.subarray(at, edit.start), edit.after);
    reversed.push({start: edit.start + delta, before: edit.after, after: edit.before, kind: edit.kind});
    delta += edit.after.length - edit.before.length; at = edit.start + edit.before.length;
  }
  out.push(bytes.subarray(at)); const result = Buffer.concat(out);
  const back = []; at = 0;
  for (const edit of reversed) { need(result.subarray(edit.start, edit.start + edit.before.length).equals(edit.before), 'OVERLAY_REVERSE_PREIMAGE');
    back.push(result.subarray(at, edit.start), edit.after); at = edit.start + edit.before.length; }
  back.push(result.subarray(at)); need(Buffer.concat(back).equals(bytes), 'OVERLAY_REVERSE_FAILED');
  return result;
}
const counts = plan => Object.fromEntries(['matcher','whatsapp','telephone','display'].map(kind => [kind, plan.filter(e => e.kind === kind).length]));
const sameCounts = (a,b) => a && Object.keys(a).length === 4 && Object.keys(b).every(k => Number.isSafeInteger(a[k]) && a[k] === b[k]);
function guardOverlay(bytes, before, after) {
  const source = utf8(bytes), anchors = [...source.matchAll(/const OWNED_HUB_SHA256 = '([a-f0-9]{64})';/g)];
  need(anchors.length === 1 && anchors[0][1] === before, 'HUB_GUARD_PREIMAGE');
  const start = Buffer.byteLength(source.slice(0, anchors[0].index) + "const OWNED_HUB_SHA256 = '");
  return overlay(bytes, [{start, before: Buffer.from(before), after: Buffer.from(after), kind: 'hub-binding'}]);
}
function rental(bytes) {
  need(digest(bytes) === pins.members[RENT], 'RENTAL_BASELINE_CHANGED');
  const source = utf8(bytes), first = 'Immediate rental enquiries are the priority for this campaign. Choose your actual move-in timeline so the team can understand your situation.';
  const second = source.match(/This preview form cannot send without JavaScript and a connected service\. Please call \+[0-9 ]+ or use WhatsApp\./g);
  need(source.split(first).length === 2 && second?.length === 1, 'RENTAL_COPY_ANCHOR');
  const out = Buffer.from(source.replace(first, 'Choose when you need to move so we can review your rental requirements against your timeline.')
    .replace(second[0], 'To send an online enquiry, JavaScript is required. You can also use the contact options on this page.'));
  need(digest(out) === '43632b26204bb898fffc36381726f895f76ee57df417aadffe0b7d07f89bd868', 'RENTAL_CANDIDATE_CHANGED'); return out;
}
function readTree(root, exactNames = null) {
  const absolute = resolve(root), rootStat = lstatSync(absolute);
  need(rootStat.isDirectory() && !rootStat.isSymbolicLink(), 'INPUT_ROOT_NOT_REGULAR');
  need(realpathSync(absolute).toLowerCase() === absolute.toLowerCase(), 'INPUT_ROOT_REDIRECTED');
  const entries = []; let visited = 0;
  function walk(dir, prefix = '') {
    for (const child of readdirSync(dir, {withFileTypes:true})) {
      need(++visited <= 200, 'INPUT_TREE_BOUND_EXCEEDED');
      const name = safePath(prefix + child.name), file = join(dir, child.name), stat = lstatSync(file);
      need(!stat.isSymbolicLink(), 'INPUT_LINK_PROHIBITED');
      if (stat.isDirectory()) walk(file, name + '/');
      else { need(stat.isFile(), 'INPUT_NOT_REGULAR'); need(stat.size > 0 && stat.size <= MAX_FILE, 'MEMBER_SIZE_INVALID');
        entries.push({path:name, bytes:readFileSync(file)}); need(entries.length <= 100, 'MEMBER_COUNT_INVALID'); }
    }
  }
  walk(absolute); return memberMap(entries, exactNames);
}
const safeError = error => new Error(typeof error?.message === 'string' && /^[A-Z][A-Z0-9_]{0,96}$/.test(error.message)
  ? error.message : 'INPUT_OR_DERIVATION_FAILED');
export function readRegularTree(root, exactNames = null) {
  try { return readTree(root,exactNames); } catch(error) { throw safeError(error); }
}
function sourceModule(root, name) {
  safePath(name); const file = resolve(root, name), rel = relative(resolve(root), file);
  need(!rel.startsWith('..') && !isAbsolute(rel), 'SOURCE_MODULE_OUTSIDE_ROOT');
  const parts = rel.split(sep); let at = resolve(root);
  for (const part of parts) { at = join(at,part); need(!lstatSync(at).isSymbolicLink(), 'SOURCE_MODULE_LINK'); }
  const value = readFileSync(file); need(digest(value) === pins.modules[name], 'SOURCE_MODULE_PIN_CHANGED'); return file;
}
async function composeBound(input) {
  // No arbitrary generator callback: selected immutable builder modules own derivation.
  need(input && typeof input === 'object', 'INPUT_REQUIRED'); identityShape(input.identity);
  need(input.provenance?.original_zip_sha256 === pins.original_zip_sha256 &&
    input.provenance?.member_map_sha256 === pins.member_map_sha256, 'ORIGINAL_PROVENANCE_CHANGED');
  if (input.original_zip_bytes !== undefined) need(Buffer.isBuffer(input.original_zip_bytes) &&
    digest(input.original_zip_bytes) === pins.original_zip_sha256, 'ORIGINAL_ARCHIVE_CHANGED');
  const names = Object.keys(pins.members), original = memberMap(input.original, names), captured = memberMap(input.captured, names);
  verifyHashes(original, pins.members, 'ORIGINAL_MEMBER_CHANGED');
  verifyHashes(captured, input.capture_binding?.members, 'CAPTURE_MEMBER_CHANGED');
  need(typeof input.capture_binding?.review_ref === 'string' && input.capture_binding.review_ref.length > 0 &&
    input.capture_binding.review_ref.length <= 256, 'PRIVATE_REVIEW_BINDING_REQUIRED');
  need(input.capture_binding?.reviewed_counts && Object.keys(input.capture_binding.reviewed_counts).length === 7, 'REVIEWED_COUNTS_REQUIRED');
  const changed = names.filter(name => !original.get(name).equals(captured.get(name)));
  need(changed.length === 8 && RECONCILIATION.every(p => changed.includes(p)), 'CAPTURE_CLASSIFICATION_CHANGED');
  const rawPlans = new Map();
  for (const name of CONTACT) {
    const plan = edits(original.get(name), name, input.identity); rawPlans.set(name,plan);
    need(sameCounts(input.capture_binding.reviewed_counts[name], counts(plan)), 'CAPTURE_EDIT_COUNTS_CHANGED');
    need(overlay(original.get(name),plan).equals(captured.get(name)), 'CAPTURE_UNRELATED_CHANGE');
  }
  need(guardOverlay(original.get(GUARD), digest(original.get(HUB)), digest(captured.get(HUB))).equals(captured.get(GUARD)), 'CAPTURE_GUARD_CHANGED');
  const sourceRoot = resolve(input.source_root); const modulePaths = Object.keys(pins.modules);
  need(lstatSync(sourceRoot).isDirectory() && !lstatSync(sourceRoot).isSymbolicLink() &&
    realpathSync(sourceRoot).toLowerCase() === sourceRoot.toLowerCase(), 'SOURCE_ROOT_REDIRECTED');
  for (const name of modulePaths) sourceModule(sourceRoot,name);
  const tracking = 'tools/website-tracking/tracking-system/';
  const admission = await import(pathToFileURL(sourceModule(sourceRoot,tracking+'build-retention-admission-candidate.mjs')).href);
  const contact = await import(pathToFileURL(sourceModule(sourceRoot,tracking+'build-contact-compatible-client-candidate.mjs')).href);
  const frame = await import(pathToFileURL(sourceModule(sourceRoot,tracking+'build-frame-delivery-candidate.mjs')).href);
  const receiver = await import(pathToFileURL(sourceModule(sourceRoot,'tools/closed-enquiry-retention/receiver-fence/build-candidate.mjs')).href);
  need(Buffer.isBuffer(input.receiver_original) && digest(input.receiver_original) === pins.receiver_sha256, 'RECEIVER_ORIGINAL_CHANGED');
  const files = new Map([...original].map(([name,bytes]) => ['plugin/'+name, Buffer.from(bytes)])), ancestry = [];
  for (const name of CONTACT) {
    let candidate = original.get(name), order = ['immutable-original'];
    if (name === LEAD) { candidate = Buffer.from(admission.buildRetentionAdmissionClient(candidate));
      order.push('reload','receipt','attribution','purpose','retention-admission'); }
    if (name === RENT) { candidate = rental(candidate); order.push('reviewed-rental-two-literal'); }
    const plan = edits(candidate,name,input.identity), final = overlay(candidate,plan), expectedCounts = {...counts(rawPlans.get(name))};
    if (name === RENT) expectedCounts.display -= 1;
    need(sameCounts(expectedCounts,counts(plan)), 'CANDIDATE_CONTACT_COUNTS_CHANGED');
    if (name === LEAD) {
      const independently = contact.buildContactCompatibleRetentionAdmissionClientCandidate(original.get(name),captured.get(name),
        {baseline_sha256:pins.members[name],target_sha256:digest(captured.get(name))});
      need(Buffer.from(independently.candidate).equals(final) && independently.original_candidate_sha256 === digest(candidate), 'ADMISSION_ANCESTRY_CHANGED');
    }
    files.set('plugin/'+name,final); ancestry.push({member:name,original_sha256:digest(original.get(name)),captured_sha256:digest(captured.get(name)),
      precontact_sha256:digest(candidate),output_sha256:digest(final),order:[...order,'typed-contact-overlay-v1'],
      edit_counts:counts(plan),allowed_ranges:plan.map(e => ({offset:e.start,removed_bytes:e.before.length,added_bytes:e.after.length,kind:e.kind})),reverse_verified:true});
  }
  const finalHub = digest(files.get('plugin/'+HUB));
  const finalGuard = guardOverlay(original.get(GUARD),digest(original.get(HUB)),finalHub); files.set('plugin/'+GUARD,finalGuard);
  const guardSource = utf8(original.get(GUARD));
  ancestry.push({member:GUARD,original_sha256:digest(original.get(GUARD)),captured_sha256:digest(captured.get(GUARD)),
    precontact_sha256:digest(original.get(GUARD)),output_sha256:digest(finalGuard),order:['immutable-original','paired-final-hub-hash-v1'],
    edit_counts:{hub_binding:1},allowed_ranges:[{offset:Buffer.byteLength(guardSource.slice(0,guardSource.indexOf("const OWNED_HUB_SHA256 = '"))+"const OWNED_HUB_SHA256 = '"),
      removed_bytes:64,added_bytes:64,kind:'hub-binding'}],reverse_verified:true});
  need(input.native_binding && input.native_binding.expected_body_sha256 === finalHub && input.native_binding.captured_body_sha256 === digest(captured.get(HUB)), 'NATIVE_HUB_EXPECTATION_CHANGED');
  files.set('plugin/assets/google-measurement.js',Buffer.from(frame.buildFrameDeliveryCandidate(original.get('assets/google-measurement.js'))));
  const receiverBytes = receiver.buildNoMailCopyReceiver(input.receiver_original);
  files.set('companion/receiver/Code.gs',receiverBytes);
  // External G1-G5 outputs are a composition dependency, never synthesized as successful stubs.
  const external = memberMap(input.selected_outputs || []), own = new Set(files.keys());
  const replaceable = new Set(['plugin/assets/wordpress.js','plugin/bsre-enquiries.php','plugin/includes/consent.php']);
  for (const [name,bytes] of external) {
    need(CONTRACT.required_outputs.includes(name) && (!own.has(name) || replaceable.has(name)), 'SELECTED_OUTPUT_COLLISION');
    need(hash(input.selected_output_pins?.[name]) && input.selected_output_pins[name] === digest(bytes), 'SELECTED_OUTPUT_PIN_CHANGED'); files.set(name,bytes);
  }
  need(Object.keys(input.selected_output_pins || {}).length === external.size, 'SELECTED_OUTPUT_PIN_SET_CHANGED');
  const missing = CONTRACT.required_outputs.filter(name => !files.has(name) || (replaceable.has(name) && !external.has(name)));
  if (input.require_all_selected_outputs === true) need(missing.length === 0, 'SELECTED_OUTPUTS_INCOMPLETE');
  for (const name of modulePaths) sourceModule(sourceRoot,name); // catch input mutation during derivation
  verifyHashes(original,pins.members,'ORIGINAL_MEMBER_CHANGED');
  const outputEntries = [...files].map(([path,bytes]) => ({path,bytes})); memberMap(outputEntries,CONTRACT.required_outputs.filter(p=>files.has(p)));
  const holds = [...CONTRACT.release_holds]; if (!input.original_zip_bytes) holds.push('ORIGINAL_ARCHIVE_BYTES_NOT_REHASHED');
  const summary = Object.freeze({schema:'bsre-coupled-public-summary-v1',status:missing.length?'PARTIAL_HELD':'STRUCTURAL_HELD',
    profile:CONTRACT.profile,original_members:30,captured_unchanged:22,captured_reconciled:8,reversible_contact_members:7,
    guard_pair_verified:true,rental_copy_precedes_contact:true,client_profile:'FULL_RETENTION_ADMISSION_ANCESTRY',
    output_count:files.size,required_output_count:CONTRACT.required_outputs.length,missing_selected_outputs:Object.freeze(missing),
    complete_profile_certified:false,diagnostic_only:true,deployment_prohibited:true,publication_authorized:false,
    ads_changes_authorized:false,network_calls:0,provider_calls:0,live_actions:0,holds:Object.freeze(holds)});
  return {files, public_summary:summary, private_manifest:{schema:'bsre-coupled-private-manifest-v1',classification:'PRIVATE_DO_NOT_PUBLISH',
    summary,original_member_map_sha256:pins.member_map_sha256,original_zip_sha256:pins.original_zip_sha256,
    capture_review_ref:input.capture_binding.review_ref,contact_scope:['CALLS','WHATSAPP'],
    receiver_original_sha256:pins.receiver_sha256,modules:{...pins.modules},ancestry,
    unchanged_capture_members:names.filter(p=>!RECONCILIATION.includes(p)).map(path=>({path,sha256:pins.members[path]})),
    selected_input_hashes:{...(input.selected_output_pins || {})},
    frame_derivation:'buildFrameDeliveryCandidate-v1',receiver_derivation:'receipt-status>retention-admission>no-mail-fence>runtime-once-v1',
    native_binding:{expected_body_sha256:finalHub,acceptance:'PENDING_NATIVE_ACCEPTANCE'},
    outputs:[...files].map(([path,bytes]) => ({path,bytes:bytes.length,sha256:digest(bytes)}))}};
}
export async function composeCoupledPackage(input) {
  try { return await composeBound(input); } catch(error) { throw safeError(error); }
}
