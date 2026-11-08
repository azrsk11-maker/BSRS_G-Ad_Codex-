import assert from 'node:assert/strict';
import {spawn} from 'node:child_process';
import {request} from 'node:http';

const host = '127.0.0.1';
const port = 18763;
const origin = 'https://blackswanrealestate.ae';
const server = spawn('php', ['-d', 'sendmail_path=/bin/false', '-S', host + ':' + port,
  '/opt/lab/consent-http-router.php'], {stdio: ['ignore', 'ignore', 'pipe']});
const exited = new Promise(resolve => server.once('close', resolve));

function post(path, body, headers = {}) {
  return new Promise((resolve, reject) => {
    const req = request({host, port, path, method: 'POST',
      headers: {origin, 'sec-fetch-site': 'same-origin', 'content-type': 'application/json', ...headers}},
    response => {
      let data = '';
      response.setEncoding('utf8');
      response.on('data', chunk => {
        data += chunk;
        if (data.length > 8192) req.destroy(new Error('Consent response too large'));
      });
      response.on('error', reject);
      response.on('end', () => {
        try {
          resolve({status: response.statusCode, body: JSON.parse(data), cookies: response.headers['set-cookie'] ?? []});
        } catch { reject(new Error('Expected JSON consent response')); }
      });
    });
    req.setTimeout(3000, () => req.destroy(new Error('Consent request timed out')));
    req.on('error', reject);
    req.end(JSON.stringify(body));
  });
}

function cookie(response, name) {
  const values = response.cookies.filter(value => value.startsWith(name + '='));
  assert.equal(values.length, 1, 'Expected one ' + name + ' cookie');
  const [pair, ...attributes] = values[0].split(';').map(value => value.trim());
  for (const flag of ['path=/', 'secure', 'httponly', 'samesite=strict']) {
    assert.ok(attributes.some(value => value.toLowerCase() === flag), name + ' missing ' + flag);
  }
  assert.ok(!attributes.some(value => /^domain=/i.test(value)), 'Expected a host-only cookie');
  return pair;
}

try {
  await new Promise((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error('Loopback PHP startup timed out')), 5000);
    server.once('error', error => { clearTimeout(timer); reject(error); });
    server.once('exit', () => { clearTimeout(timer); reject(new Error('Loopback PHP exited')); });
    server.stderr.on('data', chunk => {
      if (chunk.toString().includes('Development Server (http://' + host + ':' + port + ') started')) {
        clearTimeout(timer);
        resolve();
      }
    });
  });
  const first = await post('/context', {});
  assert.equal(first.status, 200);
  assert.equal(first.body.known, false);
  const session = cookie(first, '__Host-bsre_consent_session');
  const headers = {cookie: session, 'x-bsre-consent-csrf': first.body.csrf_token};
  const granted = {analytics: false, ad_measurement: true, personalization: false,
    notice_version: first.body.notice_version};
  const foreign = await post('/update', granted, {...headers, origin: 'https://example.invalid'});
  assert.equal(foreign.status, 403);
  assert.equal(foreign.body.code, 'CONSENT_ORIGIN_FAILED');
  const missing = await post('/update', granted, {cookie: session});
  assert.equal(missing.status, 403);
  assert.equal(missing.body.code, 'CONSENT_CSRF_FAILED');
  const update = await post('/update', granted, headers);
  assert.equal(update.status, 200);
  const preference = cookie(update, '__Host-bsre_consent');
  const both = session + '; ' + preference;
  const read = await post('/context', {}, {cookie: both});
  assert.equal(read.status, 200);
  assert.equal(read.body.known, true);
  assert.deepEqual(read.body.preferences, {analytics: false, ad_measurement: true, personalization: false});
  const withdrawn = await post('/update', {...granted, ad_measurement: false}, {...headers, cookie: both});
  assert.equal(withdrawn.status, 200);
  const fresh = cookie(withdrawn, '__Host-bsre_consent');
  const after = await post('/context', {}, {cookie: session + '; ' + fresh});
  assert.equal(after.status, 200);
  assert.equal(after.body.known, true);
  assert.deepEqual(after.body.preferences, {analytics: false, ad_measurement: false, personalization: false});
  console.log(JSON.stringify({phase: 'consent_loopback_http', status: 'PASS',
    checks: ['cookie_attributes', 'foreign_origin_denied', 'csrf_required', 'advertising_only_round_trip', 'withdrawal_round_trip'],
    client: 'Node HTTP with explicit cookie replay', tls: 'simulated termination flag', browser_verified: false}));
} finally {
  server.kill('SIGKILL');
  await exited;
}
