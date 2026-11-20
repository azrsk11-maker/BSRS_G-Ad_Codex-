// Actual enquiry client with WordPress-origin consent snapshots and local pipes.
// The VM browser and provider destinations are doubles; no Google request exists.
import {readFileSync} from 'node:fs';
import {createInterface} from 'node:readline';
import {buildAttributionClientCandidate} from '/opt/lab/tracking-system/build-attribution-client-candidate.mjs';
import {createClientPage} from './client-page.mjs';

const client = buildAttributionClientCandidate(readFileSync('/opt/wordpress/wp-content/plugins/bsre-enquiries/assets/lead.js'));
const origin = 'https://blackswanrealestate.ae';
const checks = {};
const input = createInterface({input: process.stdin, crlfDelay: Infinity});
let waiting;
input.on('line', line => {
  const pending = waiting;
  waiting = null;
  if (!pending) throw new Error('unexpected_pipe_reply');
  clearTimeout(pending.timeout);
  try { pending.resolve(JSON.parse(line)); }
  catch (_) { pending.reject(new Error('invalid_pipe_reply')); }
});
input.on('close', () => {
  if (!waiting) return;
  clearTimeout(waiting.timeout);
  waiting.reject(new Error('pipe_closed_before_reply'));
  waiting = null;
});

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

function check(name, condition) {
  if (!condition) throw new Error(name);
  checks[name] = true;
}

function acceptChecks(prefix, value) {
  check(prefix + '_server_checks_present', value && Object.keys(value).length > 0);
  for (const [name, passed] of Object.entries(value)) check(prefix + '_' + name, passed === true);
}

async function main() {
  const services = [
    ['off-plan', 'off_plan', 'Within 1 month'],
    ['resale', 'resale', 'Within 1 month'],
    ['rent', 'tenant', 'Immediate / move now'],
    ['sell', 'seller', 'As soon as practical'],
    ['let', 'landlord', 'Vacant / available to discuss now'],
  ];
  const purposes = [
    ['denied', false, false], ['analytics', true, false],
    ['advertising', false, true], ['both', true, true],
  ];
  for (const [slug, role, timeline] of services) {
    for (const [label, analytics, advertising] of purposes) {
      const prefix = slug + '_' + label;
      const setup = await command({op: 'session', scenario: {slug, role, timeline, analytics, advertising}});
      check(prefix + '_server_choice_matches', setup.snapshot?.known === true
        && setup.snapshot.acknowledged === true && setup.snapshot.measurement_eligible === true
        && setup.snapshot.preferences.analytics === analytics
        && setup.snapshot.preferences.ad_measurement === advertising
        && setup.snapshot.preferences.personalization === false);
      check(prefix + '_synthetic_source_values', setup.utm_source === 'SYNTHETIC_SOURCE'
        && setup.gclid === 'Synthetic_Click_Ab9');
      const store = new Map();
      const options = {client, origin, request: data => command({op: 'request', ...data}),
        slug, role, timeline, csrf: setup.csrf, store, analytics, advertising, eligible: true,
        snapshot: setup.snapshot, name: 'SYNTHETIC consent lab ' + slug};
      const parameters = new URLSearchParams({utm_source: setup.utm_source, gclid: setup.gclid});
      createClientPage({...options, formPresent: false, locationPath: '/enquire/?' + parameters});
      const service = createClientPage(options);
      await service.submit();
      check(prefix + '_durable_receipt_accepted', service.acceptedResponse?.status === 200
        && service.acceptedResponse.body.accepted === true && service.status.dataset.state === 'success');
      const intake = service.requests.filter(item => item.url.endsWith('/lead'));
      check(prefix + '_one_intake', intake.length === 1);
      const payload = JSON.parse(intake[0].request.body);
      check(prefix + '_original_decision_header', intake[0].request.headers['X-BSRE-Consent-Decision'] === setup.snapshot.decision_version);
      check(prefix + '_current_service_page', payload.landing_page === origin + '/enquire/' + slug + '/');
      check(prefix + '_private_capture_id_not_transmitted', !intake[0].request.body.includes('capture_id'));
      if (analytics || advertising) {
        for (const touch of ['first', 'last']) {
          const value = payload.attribution[touch];
          check(prefix + '_' + touch + '_hub_acquisition', value?.landing_page === origin + '/enquire/');
          check(prefix + '_' + touch + '_purpose_parameters',
            (analytics ? value.parameters.utm_source === setup.utm_source : !Object.hasOwn(value.parameters, 'utm_source'))
            && (advertising ? value.parameters.gclid === setup.gclid : !Object.hasOwn(value.parameters, 'gclid')));
        }
      } else {
        check(prefix + '_refusal_omits_attribution', payload.attribution.first === null && payload.attribution.last === null);
      }
      check(prefix + '_permitted_destinations_only', service.measurement.length === Number(analytics) + Number(advertising)
        && service.measurement.filter(value => value.destination === 'ga4').length === Number(analytics)
        && service.measurement.filter(value => value.destination === 'ads').length === Number(advertising));
      const publicPayload = JSON.stringify(service.measurement);
      check(prefix + '_public_payload_privacy', !['fixture@example.invalid', '+971500000000',
        'SYNTHETIC consent lab', setup.gclid, setup.utm_source, 'capture_id', 'decision_version', 'notice_version']
        .some(value => publicPayload.includes(value)));
      const sentRequests = service.requests.length;
      await service.submit();
      check(prefix + '_repeat_submit_sends_nothing', service.requests.length === sentRequests
        && service.measurement.length === Number(analytics) + Number(advertising));
      const inspected = await command({op: 'inspect', request_id: payload.request_id,
        expected_gclid: setup.gclid, expected_utm_source: setup.utm_source});
      acceptChecks(prefix + '_inspect', inspected.checks);
      const withdrawn = await command({op: 'withdraw', request_id: payload.request_id});
      acceptChecks(prefix + '_withdraw', withdrawn.checks);
    }
  }
  await command({op: 'complete', scenarios: services.length * purposes.length, checks});
  input.close();
}

main().catch(error => {
  process.stderr.write('Consented client integration failed at ' + error.message + '\n');
  input.close();
  process.exitCode = 1;
});
