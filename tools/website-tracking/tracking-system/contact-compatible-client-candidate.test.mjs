import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {createHash} from 'node:crypto';
import {runInNewContext} from 'node:vm';
import {buildContactCompatibleClientCandidate as build} from './build-contact-compatible-client-candidate.mjs';
import {buildPurposeClientCandidate} from './build-purpose-attribution-candidate.mjs';

const baseline = readFileSync(new URL('../../staging-lab/fixtures/bsre-enquiries/assets/lead.js', import.meta.url));
const prefix = String.raw`/^https:\/\/wa\.me\/`;
const suffix = String.raw`(?:\?|$)/.test(href)`;
const raw = baseline.toString('utf8'), start = raw.indexOf(prefix) + prefix.length;
const oldDigits = raw.slice(start, raw.indexOf(suffix, start));
const syntheticDigits = '999999999991'; // Synthetic matcher only; no provider or navigation executes.
const sha = bytes => createHash('sha256').update(bytes).digest('hex');
const targetFor = digits => Buffer.from(raw.slice(0, start) + digits + raw.slice(start + oldDigits.length));
const target = targetFor(syntheticDigits);
const bindingFor = bytes => ({baseline_sha256: sha(baseline), target_sha256: sha(bytes)});

function page(code, href, {analytics = true, eligible = true, name = '', kind = 'whatsapp', marked = true} = {}) {
  const measurements = [], handlers = new Map(), storage = new Map();
  let navigationMutated = false;
  const link = {dataset: {bsreContact: kind, ctaLocation: 'hero'},
    getAttribute: key => key === 'href' ? href : null,
    setAttribute() { navigationMutated = true; throw new Error('Link mutation prohibited'); },
    addEventListener: (event, fn) => handlers.set(event, fn)};
  Object.defineProperty(link, 'href', {get: () => href, set() { navigationMutated = true; }});
  const form = name ? {dataset: {role: 'tenant', landingPath: '/enquire/rent/'},
    elements: {namedItem: key => ({value: key === 'name' ? name : ''})}} : null;
  const snapshot = {known: true, acknowledged: true, measurement_eligible: eligible,
    preferences: {analytics, ad_measurement: false}, decision_version: 'test-choice', notice_version: 'test-notice'};
  const window = {
    location: new URL('https://example.invalid/enquire/rent/'),
    BSRELeadConfig: {measurementEligible: eligible},
    BSREConsentBridge: {permissions: () => ({analytics, advertising: false}), measurementEligible: () => eligible,
      getSnapshot: () => snapshot, normalizeSnapshot: value => value},
    crypto: {randomUUID: () => '00000000-0000-4000-8000-000000000001'},
    sessionStorage: {getItem: key => storage.get(key) ?? null, setItem: (key, value) => storage.set(key, value), removeItem: key => storage.delete(key)},
    addEventListener() {}, dispatchEvent() {}, setTimeout() {}, clearTimeout() {},
    CustomEvent: class { constructor(type, options) { this.type = type; this.detail = options.detail; } },
    fetch() { throw new Error('No network in diagnostic fixture'); },
  };
  const document = {readyState: 'complete', referrer: '', querySelector: () => form,
    querySelectorAll: selector => selector === 'a[data-bsre-contact]' && marked ? [link] : []};
  runInNewContext(code, {window, document, URL, AbortController}, {timeout: 1000});
  window.BSREMeasurement.connect('ga4', event => { measurements.push(event); return true; });
  return {click: () => handlers.get('click')?.(), listenerAttached: () => handlers.has('click'), measurements, href: () => link.href,
    mutated: () => navigationMutated};
}

test('exact diagnostic overlay preserves the complete original purpose-client chain', () => {
  const originalBytes = Buffer.from(baseline), targetBytes = Buffer.from(target);
  const result = build(baseline, target, bindingFor(target));
  const expected = buildPurposeClientCandidate(baseline).replace(prefix + oldDigits + suffix, prefix + syntheticDigits + suffix);
  assert.equal(result.candidate, expected);
  assert.equal(result.candidate_sha256, sha(Buffer.from(expected)));
  assert.equal(result.original_candidate_sha256, sha(Buffer.from(buildPurposeClientCandidate(baseline))));
  assert.equal(result.diagnostic_only, true); assert.equal(result.deployment_prohibited, true);
  assert.ok(result.holds.includes('COUPLED_PACKAGE_REVIEW_REQUIRED'));
  assert.ok(baseline.equals(originalBytes) && target.equals(targetBytes));
});

test('generated client recognizes only exact target WhatsApp hrefs, preserving navigation', () => {
  const code = build(baseline, target, bindingFor(target)).candidate;
  for (const [href, expected] of [
    [`https://wa.me/${syntheticDigits}`, 1], [`https://wa.me/${syntheticDigits}?text=synthetic`, 1],
    [`https://wa.me/${oldDigits}`, 0], [`https://wa.me/${syntheticDigits}1`, 0],
    [`https://wa.me/${syntheticDigits}/`, 0], [`https://wa.me.evil.invalid/${syntheticDigits}`, 0],
    [`http://wa.me/${syntheticDigits}`, 0], [`https://wa.me/${syntheticDigits}#fragment`, 0],
  ]) {
    const f = page(code, href); f.click();
    assert.equal(f.measurements.length, expected); assert.equal(f.href(), href); assert.equal(f.mutated(), false);
    if (expected) assert.equal(f.measurements[0].event_name, 'whatsapp_click');
  }
});

test('consent denial, ineligible QA and TEST forms still suppress diagnostic measurement', () => {
  const code = build(baseline, target, bindingFor(target)).candidate;
  for (const options of [{analytics: false}, {eligible: false}, {name: 'TEST synthetic fixture'}]) {
    const f = page(code, `https://wa.me/${syntheticDigits}`, options); f.click();
    assert.equal(f.measurements.length, 0); assert.equal(f.mutated(), false);
  }
});

test('existing generic telephone recognition and unmarked-anchor limitation remain unchanged', () => {
  const code = build(baseline, target, bindingFor(target)).candidate;
  const tel = page(code, 'tel:+999999999991', {kind: 'telephone'}); tel.click();
  assert.equal(tel.measurements.length, 1); assert.equal(tel.measurements[0].event_name, 'telephone_click');
  assert.equal(tel.mutated(), false);
  const unmarked = page(code, `https://wa.me/${syntheticDigits}`, {marked: false});
  unmarked.click(); assert.equal(unmarked.listenerAttached(), false); assert.equal(unmarked.measurements.length, 0);
});

test('target hash, original pin, unknown authority fields and accessor descriptors fail closed', () => {
  assert.throws(() => build(baseline, target, {...bindingFor(target), target_sha256: '0'.repeat(64)}), /TARGET_HASH/);
  assert.throws(() => build(Buffer.concat([baseline, Buffer.from(' ')]), target, bindingFor(target)), /BASELINE_CHANGED/);
  assert.throws(() => build(baseline, target, {...bindingFor(target), approved: true}), /BINDING_SHAPE/);
  let called = false;
  const accessor = {baseline_sha256: sha(baseline)};
  Object.defineProperty(accessor, 'target_sha256', {get() { called = true; return sha(target); }});
  assert.throws(() => build(baseline, target, accessor), /BINDING_HASH/); assert.equal(called, false);
});

test('unrelated bytes, absent/duplicate matcher anchors and unchanged targets are rejected', () => {
  const changes = [Buffer.concat([target, Buffer.from('\n// unrelated')]),
    Buffer.from(target.toString().replace(prefix, 'unrelated-prefix')),
    Buffer.concat([target, Buffer.from('\n' + prefix + syntheticDigits + suffix)])];
  for (const bytes of changes) assert.throws(() => build(baseline, bytes, bindingFor(bytes)));
  assert.throws(() => build(baseline, baseline, bindingFor(baseline)), /TARGET_UNCHANGED/);
});

test('raw bounds, invalid UTF8 and malformed or injected matcher literals fail closed', () => {
  for (const digits of ['0123456789', '1', '1'.repeat(16), '99999|.*', '9999999\n', '9999999/evil']) {
    const bytes = targetFor(digits); assert.throws(() => build(baseline, bytes, bindingFor(bytes)), /MATCHER_LITERAL/);
  }
  assert.throws(() => build(baseline, target.toString(), bindingFor(target)), /RAW_BYTES/);
  const huge = Buffer.alloc(262145); assert.throws(() => build(baseline, huge, bindingFor(huge)), /RAW_BYTES/);
  const invalid = Buffer.concat([target, Buffer.from([0xff])]);
  assert.throws(() => build(baseline, invalid, bindingFor(invalid)), /INVALID_UTF8/);
});
