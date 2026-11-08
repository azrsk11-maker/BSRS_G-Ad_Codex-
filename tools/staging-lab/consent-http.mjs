import assert from 'node:assert/strict';
import {execFileSync, spawn} from 'node:child_process';
import {mkdtempSync, readFileSync, rmSync, writeFileSync} from 'node:fs';
import {request} from 'node:https';
import {connect} from 'node:net';
import {join} from 'node:path';
import {createServer} from 'node:tls';
import {setTimeout as delay} from 'node:timers/promises';

const host = '127.0.0.1';
const port = 18763;
const tlsPort = 18764;
const origin = 'https://blackswanrealestate.ae';
const temporary = mkdtempSync('/tmp/bsre-consent-tls-');
let key, cert;
try {
  const keyPath = join(temporary, 'key.pem');
  const certPath = join(temporary, 'cert.pem');
  execFileSync('openssl', ['req', '-x509', '-newkey', 'rsa:2048', '-nodes', '-days', '1',
    '-subj', '/CN=BSRE Synthetic Loopback', '-addext', 'subjectAltName=IP:127.0.0.1',
    '-keyout', keyPath, '-out', certPath], {timeout: 10000, stdio: 'ignore'});
  key = readFileSync(keyPath);
  cert = readFileSync(certPath);
} finally {
  rmSync(temporary, {recursive: true});
}
const sockets = new Set();
const tls = createServer({key, cert, minVersion: 'TLSv1.2'}, client => {
  const upstream = connect({host, port});
  sockets.add(client);
  client.on('error', () => upstream.destroy());
  upstream.on('error', () => client.destroy());
  client.on('close', () => { sockets.delete(client); upstream.destroy(); });
  upstream.on('close', () => client.destroy());
  client.pipe(upstream).pipe(client);
});
const server = spawn('php', ['-d', 'sendmail_path=/bin/false', '-S', host + ':' + port,
  '/opt/lab/consent-http-router.php'], {stdio: ['ignore', 'ignore', 'pipe']});
const exited = new Promise(resolve => server.once('close', resolve));

function post(path, body, headers = {}, ca = cert) {
  return new Promise((resolve, reject) => {
    const req = request({host, port: tls.address().port, path, method: 'POST', ca, agent: false,
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

async function browserConsent() {
  const profile = mkdtempSync('/tmp/bsre-firefox-');
  const db = 'sql:' + profile;
  const certificate = join(profile, 'lab-cert.pem');
  const resultPath = '/tmp/bsre-consent-browser-result.json';
  let browser, closed, diagnostics = '';
  try {
    rmSync(resultPath, {force: true});
    writeFileSync(certificate, cert);
    execFileSync('certutil', ['-N', '-d', db, '--empty-password'], {timeout: 5000});
    execFileSync('certutil', ['-A', '-d', db, '-n', 'BSRE lab only', '-t', 'C,,', '-i', certificate], {timeout: 5000});
    browser = spawn('firefox-esr', ['-headless', '-no-remote', '-profile', profile,
      'https://' + host + ':' + tlsPort + '/browser'], {
      env: {...process.env, HOME: profile}, stdio: ['ignore', 'ignore', 'pipe'],
    });
    let stopped = false;
    closed = new Promise(resolve => browser.once('close', () => { stopped = true; resolve(); }));
    browser.once('error', error => { diagnostics = error.code; stopped = true; });
    browser.stderr.on('data', chunk => { diagnostics = (diagnostics + chunk.toString()).slice(-1600); });
    const deadline = Date.now() + 25000;
    while (!stopped && Date.now() < deadline) {
      let result;
      try { result = JSON.parse(readFileSync(resultPath, 'utf8')); }
      catch (error) { if (error.code !== 'ENOENT' && !(error instanceof SyntaxError)) throw error; }
      if (result) {
        assert.equal(result.status, 'PASS', 'Browser consent check failed: ' + result.check);
        console.log(JSON.stringify({phase: 'consent_firefox', status: 'PASS',
          checks: ['secure_context', 'native_dom', 'fresh_default_denied', 'advertising_only',
            'cookie_across_navigation', 'httponly', 'synchronous_withdrawal',
            'scoped_cookie_and_storage_cleanup', 'withdrawal_readback'],
          real_wordpress: true, synthetic_origin_translation: true}));
        return;
      }
      await delay(100);
    }
    throw new Error('Firefox consent fixture did not complete: ' + diagnostics);
  } finally {
    if (browser) {
      browser.kill('SIGTERM');
      await Promise.race([closed, delay(2000)]);
      browser.kill('SIGKILL');
    }
    rmSync(resultPath, {force: true});
    rmSync(profile, {recursive: true, force: true});
  }
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
  await new Promise((resolve, reject) => {
    tls.once('error', reject);
    tls.listen(tlsPort, host, resolve);
  });
  await assert.rejects(post('/context', {}, {}, null), {code: 'DEPTH_ZERO_SELF_SIGNED_CERT'});
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
  console.log(JSON.stringify({phase: 'consent_loopback_https', status: 'PASS',
    checks: ['untrusted_certificate_rejected', 'trusted_loopback_tls', 'cookie_attributes', 'foreign_origin_denied',
      'csrf_required', 'advertising_only_round_trip', 'withdrawal_round_trip'],
    client: 'Node HTTPS with explicit cookie replay', tls: 'loopback TLS termination', browser_verified: false}));
  await browserConsent();
} finally {
  for (const socket of sockets) socket.destroy();
  tls.close();
  server.kill('SIGKILL');
  await exited;
}
