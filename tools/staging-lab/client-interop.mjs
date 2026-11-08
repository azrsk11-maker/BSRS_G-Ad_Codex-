// Pipe-only client integration. DOM and storage are doubles, all endpoint replies
// come from the real WordPress handlers in client-interop.php.
import {readFileSync} from 'node:fs';
import {createInterface} from 'node:readline';
import {buildAttributionClientCandidate} from '/opt/lab/tracking-system/build-attribution-client-candidate.mjs';
import {createClientPage} from './client-page.mjs';

const original = readFileSync('/opt/wordpress/wp-content/plugins/bsre-enquiries/assets/lead.js');
const client = buildAttributionClientCandidate(original);
const origin = 'https://blackswanrealestate.ae';
const pendingKey = 'BSRE_PENDING_ENQUIRY_V1';
const checks = {};
const upstreamMode = process.argv.includes('--upstream');
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

function page(options) {
  return createClientPage({client, origin, request: data => command({op: 'request', ...data}), ...options});
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
    const first = page({slug, role, timeline, csrf: setup.csrf, store, loseAcknowledgement: !upstreamMode});
    await first.submit();
    check(slug + (upstreamMode ? '_lost_upstream_ack_before_local_linkage' : '_lost_ack_after_real_acceptance'),
      (upstreamMode ? first.acceptedResponse?.status === 503 && first.acceptedResponse.body.accepted === false
        : first.acceptedResponse?.status === 200 && first.acceptedResponse.body.accepted === true)
      && first.status.dataset.state === 'error');
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
      && reloaded.status.textContent.includes(upstreamMode ? before.accepted_reference : first.acceptedResponse.body.lead_id));
    check(slug + '_recovery_request_uses_only_proof', reloaded.requests.length === 1
      && reloaded.requests[0].url.endsWith('/status')
      && JSON.stringify(JSON.parse(reloaded.requests[0].request.body)) === JSON.stringify({proof}));
    check(slug + '_recovery_clears_pending_marker', !store.has(pendingKey)
      && reloaded.button.dataset.complete === 'true');
    await reloaded.submit();
    const after = await command({op: 'stats'});
    check(slug + '_reload_never_replays_intake', before.lead_requests === after.lead_requests
      && before.receiver_calls === after.receiver_calls && reloaded.requests.length === 1
      && after.status_calls - before.status_calls === (upstreamMode ? 1 : 0));
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
