// Local pipe protocol only; never opens a network listener or real Google services.
import {createInterface} from 'node:readline';
import {lab} from './receiver-lab.mjs';
import {readFileSync} from 'node:fs';
const candidateArgument = process.argv.indexOf('--receipt-status');
let candidate;
if (candidateArgument !== -1) {
  const {buildReceiptStatusCandidate} = await import(process.argv[candidateArgument + 1]);
  candidate = Buffer.from(buildReceiptStatusCandidate(readFileSync(new URL('./fixtures/receiver-v2/Code.gs', import.meta.url))));
}
const l=lab(candidate); l.properties.HMAC_SECRET='synthetic-key-'.repeat(4);
for await(const line of createInterface({input:process.stdin,crlfDelay:Infinity})) {
 const command=JSON.parse(line); let result;
 if(command.op==='post') result=l.postWire(command.raw);
 else if(command.op==='outbox') {l.context.processLeadOutbox();result={headers:l.context.LEAD_HEADERS,rows:l.rows.slice(1),mail:l.mail};}
 else throw Error('Unsupported synthetic bridge operation');
 process.stdout.write(JSON.stringify(result)+'\n');
}
