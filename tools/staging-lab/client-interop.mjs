// Pipe-only client integration. DOM and storage are doubles, all endpoint replies
// come from the real WordPress handlers in client-interop.php.
import {readFileSync} from 'node:fs';
import {createInterface} from 'node:readline';
import {randomUUID} from 'node:crypto';
import {runInNewContext} from 'node:vm';
import {buildReceiptClientCandidate} from '/opt/lab/tracking-system/build-receipt-client-candidate.mjs';

const original = readFileSync('/opt/wordpress/wp-content/plugins/bsre-enquiries/assets/lead.js');
const client = buildReceiptClientCandidate(original);
const origin = 'https://blackswanrealestate.ae';
const pendingKey = 'BSRE_PENDING_ENQUIRY_V1';
const checks = {};
const input = createInterface({input: process.stdin, crlfDelay: Infinity});
let waiting;
input.on('line', line => {
  const request = waiting;
  waiting = null;
  if (!request) throw new Error('unexpected_pipe_reply');
  clearTimeout(request.timeout);
  try { request.resolve(JSON.parse(line)); }
  catch (_) { request.reject(new Error('invalid_pipe_reply')); }
});
input.on('close', () => {
  if (!waiting) return;
  clearTimeout(waiting.timeout);
  waiting.reject(new Error('pipe_closed_before_reply'));
  waiting = null;
});

function check(name, condition) {
  if (!condition) throw new Error(name);
  checks[name] = true;
}

function command(value) {
  return new Promise((resolve, reject) => {
    if (waiting) throw new Error('concurrent_pipe_request');
    waiting = {resolve, reject, timeout: setTimeout(() => {
      waiting = null;
      reject(new Error('pipe_reply_timeout'));
    }, 15000)};
    process.stdout.write(JSON.stringify(value) + '\n');
  });
}

function page({slug, role, timeline, csrf, store, blank = false, loseAcknowledgement = false}) {
  const handlers = new Map();
  const button = {dataset: {}, textContent: 'Submit'};
  const status = {dataset: {}};
  const requests = [];
  const measurement = [];
  let acceptedResponse;
  const values = blank ? {} : {
    name: 'TEST synthetic client ' + slug,
    phone: '+971500000000', email: 'fixture@example.invalid', country: 'UAE',
    area: 'Synthetic fixture', budget: 'To discuss', timeline, funding: 'To discuss',
    property_type: 'Apartment', property_details: 'SYNTHETIC NOT INVENTORY',
    authority: ['seller', 'landlord'].includes(role) ? 'owner' : '',
  };
  const form = {
    dataset: {role, landingPath: '/enquire/' + slug + '/', campaign: 'SYNTHETIC_LAB_ONLY'},
    elements: {namedItem(name) {
      if (name === 'contact_consent') return {checked: !blank};
      if (name === 'marketing_consent') return {checked: false};
      return {value: values[name] || ''};
    }},
    querySelector: selector => selector === '[data-bsre-status]' ? status : button,
    reportValidity: () => !blank,
    addEventListener: (type, listener) => handlers.set(type, listener),
  };
  const window = {
    location: new URL(origin + '/enquire/' + slug + '/'),
    crypto: {randomUUID},
    BSRELeadConfig: {endpoint: origin + '/wp-json/bsre/v1/lead', csrfToken: csrf, measurementEligible: false},
    BSREConsentBridge: {
      permissions: () => ({analytics: false, advertising: false}),
      measurementEligible: () => false,
      getSnapshot: () => null,
      normalizeSnapshot: value => value,
    },
    sessionStorage: {
      getItem: key => store.get(key) ?? null,
      setItem: (key, value) => store.set(key, value),
      removeItem: key => store.delete(key),
    },
    setTimeout, clearTimeout, addEventListener() {}, dispatchEvent() {}, CustomEvent: class {},
    async fetch(url, request) {
      requests.push({url, request});
      const result = await command({op: 'request', url, method: request.method,
        credentials: request.credentials, headers: request.headers, body: request.body});
      if (url.endsWith('/lead') && loseAcknowledgement) {
        acceptedResponse = result;
        loseAcknowledgement = false;
        throw new Error('synthetic_browser_acknowledgement_loss');
      }
      return {ok: result.status >= 200 && result.status < 300, status: result.status,
        json: async () => result.body};
    },
  };
  const document = {readyState: 'complete', referrer: '', querySelector: () => form,
    querySelectorAll: selector => selector === 'form[data-bsre-form]' ? [form] : []};
  runInNewContext(client, {window, document, URL, AbortController});
  window.BSREMeasurement.connect('ads', event => measurement.push(event));
  window.BSREMeasurement.connect('ga4', event => measurement.push(event));
  return {submit: () => handlers.get('submit')({preventDefault() {}}), requests, measurement,
    status, button, get acceptedResponse() { return acceptedResponse; }};
}

async function main() {
  const services = [
    ['off-plan', 'off_plan', 'Within 1 month'],
    ['resale', 'resale', 'Within 1 month'],
    ['rent', 'tenant', 'Immediate / move now'],
    ['sell', 'seller', 'As soon as practical'],
    ['let', 'landlord', 'Vacant / available to discuss now'],
  ];
  for (const [slug, role, timeline] of services) {
    const setup = await command({op: 'session'});
    const store = new Map();
    const first = page({slug, role, timeline, csrf: setup.csrf, store, loseAcknowledgement: true});
    await first.submit();
    check(slug + '_lost_ack_after_real_acceptance', first.acceptedResponse?.status === 200
      && first.acceptedResponse.body.accepted === true && first.status.dataset.state === 'error');
    const proofRequest = first.requests.find(item => item.url.endsWith('/proof'));
    const leadRequest = first.requests.find(item => item.url.endsWith('/lead'));
    const proof = store.get(pendingKey);
    check(slug + '_proof_issued_before_intake', first.requests.length === 2 && proofRequest === first.requests[0]
      && proofRequest.request.body === '{}' && leadRequest === first.requests[1]);
    check(slug + '_server_uuid_binds_intake', typeof proof === 'string'
      && JSON.parse(leadRequest.request.body).request_id === proof.split('.')[0]);
    check(slug + '_storage_contains_only_recovery_proof', store.size === 1 && !proof.includes('TEST')
      && /^[-0-9a-f]{36}\.[0-9]+\.[0-9a-f]{64}$/.test(proof));
    const before = await command({op: 'stats'});
    const reloaded = page({slug, role, timeline, csrf: setup.csrf, store, blank: true});
    await reloaded.submit();
    check(slug + '_blank_reload_recovers_real_reference', reloaded.status.dataset.state === 'success'
      && reloaded.status.textContent.includes(first.acceptedResponse.body.lead_id));
    check(slug + '_recovery_request_uses_only_proof', reloaded.requests.length === 1
      && reloaded.requests[0].url.endsWith('/status')
      && JSON.stringify(JSON.parse(reloaded.requests[0].request.body)) === JSON.stringify({proof}));
    check(slug + '_recovery_clears_pending_marker', !store.has(pendingKey)
      && reloaded.button.dataset.complete === 'true');
    await reloaded.submit();
    const after = await command({op: 'stats'});
    check(slug + '_reload_never_replays_intake', before.lead_requests === after.lead_requests
      && before.receiver_calls === after.receiver_calls && reloaded.requests.length === 1);
    check(slug + '_synthetic_recovery_emits_no_measurement', first.measurement.length + reloaded.measurement.length === 0);
  }
  await command({op: 'complete', checks});
  input.close();
}

main().catch(error => {
  process.stderr.write('Client integration failed at ' + error.message + '\n');
  input.close();
  process.exitCode = 1;
});
