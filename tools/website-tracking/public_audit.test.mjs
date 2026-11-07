import test from 'node:test';
import assert from 'node:assert/strict';
import {safeTarget, inspectHtml, auditRoute} from './public_audit.mjs';

test('allowlist rejects analytics, query strings, credentials, external hosts and unplanned routes', () => {
  for (const value of ['https://google-analytics.com/collect','/?email=private@example.test',
    'https://x:y@blackswanrealestate.ae/','https://other.example/','/wp-admin/', '/lp/bsre-c0001/']) {
    assert.throws(() => safeTarget(value), /OUTSIDE_EXPLICIT_AUDIT_SCOPE/);
  }
  assert.equal(safeTarget('/enquire/rent/').pathname, '/enquire/rent/');
});

test('redacted parsing preserves technology and noindex without retaining entered or hidden content', () => {
  const html = `<meta name="robots" content="noindex, follow"><meta name="generator" content="WordPress 6.8">
    <link rel="canonical" href="https://blackswanrealestate.ae/enquire/rent/?email=secret@example.test">
    <script src="/wp-content/plugins/bsre-enquiries/assets.js?ver=0.2.12&nonce=SECRETVALUE"></script>
    <script src="https://www.googletagmanager.com/gtm.js?id=GTM-ABC12345&email=secret@example.test"></script>
    <link href="/wp-content/themes/houzez/a.css"><form id="bsre-form"><input name="phone" value="PRIVATEPHONE">
    <input type="hidden" value="CSRFSECRET"></form><a data-cta-id="private-input">Contact</a>`;
  const result = inspectHtml(html);
  assert.deepEqual(result.meta_robots, ['follow','noindex']);
  assert.deepEqual(result.themes, ['houzez']);
  assert.deepEqual(result.bsre_public_asset_versions, ['0.2.12']);
  assert.deepEqual(result.public_google_ids, ['GTM-ABC12345']);
  assert.equal(result.bsre_form_count, 1);
  assert.equal(result.canonical[0], 'https://blackswanrealestate.ae/enquire/rent/');
  assert.deepEqual(result.stable_context_attribute_names, ['data-cta-id']);
  assert.doesNotMatch(JSON.stringify(result), /secret@example|SECRETVALUE|PRIVATEPHONE|CSRFSECRET|private-input/);
});

test('external redirect is refused before contacting external destination', async () => {
  let calls = 0;
  const result = await auditRoute('/', async () => {
    calls++; return {status:302,headers:{location:'https://google-analytics.com/collect'}};
  });
  assert.equal(calls, 1); assert.equal(result.error, 'OUTSIDE_EXPLICIT_AUDIT_SCOPE');
});

test('redirect loops have a fixed request limit', async () => {
  const result = await auditRoute('/', async () => ({status:302,headers:{location:'/'}}));
  assert.equal(result.http_calls, 4); assert.equal(result.error, 'REDIRECT_LIMIT_EXCEEDED');
});

test('raw headers, cookies and CSP nonces are excluded', async () => {
  const result = await auditRoute('/', async () => ({status:200,bytes:20,elapsed_ms:1,
    headers:{'set-cookie':'token=SECRETCOOKIE', 'content-security-policy': "default-src 'self'; script-src 'nonce-SECRETNONCE'"},
    body:'<h1>Safe</h1>'}));
  assert.deepEqual(result.headers.csp_directive_names, ['default-src','script-src']);
  assert.doesNotMatch(JSON.stringify(result), /SECRETCOOKIE|SECRETNONCE|set-cookie/);
});
