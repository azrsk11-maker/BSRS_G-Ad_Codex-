// Actual composed client over local test IPC. DOM, storage and Google remain doubles.
import {readFileSync} from 'node:fs';
import {createInterface} from 'node:readline';
import {createClientPage} from '/opt/lab/client-page.mjs';
import {buildRetentionAdmissionClient} from '/opt/lab/tracking-system/build-retention-admission-candidate.mjs';

const input = createInterface({input: process.stdin, crlfDelay: Infinity});
let pending;
input.on('line', line => {
  const request = pending; pending = null;
  if (!request) throw new Error('Unexpected admission test reply');
  clearTimeout(request.timer); request.resolve(JSON.parse(line));
});
function command(value) {
  return new Promise((resolve, reject) => {
    if (pending) throw new Error('Concurrent admission test call');
    pending = {resolve, reject, timer: setTimeout(() => reject(new Error('Admission IPC timeout')), 10000)};
    process.stdout.write(JSON.stringify(value) + '\n');
  });
}
async function main() {
  const setup = await command({op: 'setup'});
  const client = 'window.BSRELeadConfig.retentionAdmissionRequired = true;\n'
    + buildRetentionAdmissionClient(readFileSync('/opt/wordpress/wp-content/plugins/bsre-enquiries/assets/lead.js'));
  const page = createClientPage({client, origin: 'https://blackswanrealestate.ae', slug: 'rent', role: 'tenant',
    timeline: 'Immediate / move now', csrf: setup.csrf, store: new Map(), name: 'SYNTHETIC admission client',
    request: request => command({op: 'request', ...request})});
  await page.submit();
  if (page.acceptedResponse?.body?.accepted !== true) throw new Error('Actual admission client did not receive a receipt');
  const intake = page.requests.find(request => request.url.endsWith('/lead'));
  if (!intake || !intake.request.headers['X-BSRE-Admission']) throw new Error('Admission proof header missing');
  if (JSON.stringify(page.events).includes('session_hash')) throw new Error('Admission proof escaped into public event');
  await command({op: 'complete', request_id: JSON.parse(intake.request.body).request_id});
  input.close();
}
main().catch(error => {process.stderr.write(error.stack + '\n'); process.exitCode = 1; input.close();});
