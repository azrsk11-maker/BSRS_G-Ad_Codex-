// Local synthetic receiver process. No network, credentials or real mail capability.
import {createInterface} from 'node:readline';
import {readFileSync} from 'node:fs';
import {lab} from '/opt/lab/receiver-lab.mjs';
import {buildRetentionAdmissionReceiver} from '/opt/lab/tracking-system/build-retention-admission-candidate.mjs';

const receiver = lab(buildRetentionAdmissionReceiver(readFileSync('/opt/lab/fixtures/receiver-v2/Code.gs')));
receiver.properties.HMAC_SECRET = 'synthetic-key-'.repeat(4);
for await (const line of createInterface({input: process.stdin, crlfDelay: Infinity})) {
  const request = JSON.parse(line);
  let result;
  if (request.op === 'configure') {
    Object.assign(receiver.properties, request.properties);
    result = receiver.context.retentionAdmissionDescriptor_();
  } else if (request.op === 'post') result = receiver.postWire(request.raw);
  else if (request.op === 'outbox') result = receiver.context.processLeadOutbox();
  else if (request.op === 'snapshot') result = {rows: receiver.rows.length - 1, mail: receiver.mail.length, columns: receiver.context.LEAD_HEADERS.length};
  else if (request.op === 'delivery_audit') {
    const rows=receiver.rows.slice(1),messages=receiver.mail;
    result={rows:rows.length,mail:messages.length,columns:receiver.context.LEAD_HEADERS.length,
      exact_once_identity:rows.length===messages.length && new Set(rows.map(row=>row[1])).size===rows.length
        && new Set(rows.map(row=>row[2])).size===rows.length
        && rows.every(row=>row.length===26 && row[6]==='SENT' && row[7]===1
          && messages.filter(message=>message.body.includes('Lead ID: '+row[1]+'\nEvent ID: '+row[2]+'\n')).length===1)};
  }
  else if (request.op === 'purge_synthetic') {
    const matches = receiver.rows.map((row, index) => row[0] === request.request_id ? index : -1).filter(index => index > 0);
    if (matches.length !== 1) throw new Error('SYNTHETIC_PURGE_REQUIRES_ONE_ROW');
    receiver.rows.splice(matches[0], 1);
    result = {removed: 1};
  } else throw new Error('Unsupported synthetic admission operation');
  process.stdout.write(JSON.stringify(result) + '\n');
}
