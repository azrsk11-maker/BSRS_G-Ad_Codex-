// Local pipe protocol only; never opens a network listener or real Google services.
import {createInterface} from 'node:readline';
import {lab} from './receiver-lab.mjs';
const l=lab(); l.properties.HMAC_SECRET='synthetic-key-'.repeat(4);
for await(const line of createInterface({input:process.stdin,crlfDelay:Infinity})) {
 const command=JSON.parse(line); let result;
 if(command.op==='post') result=l.postWire(command.raw);
 else if(command.op==='outbox') {l.context.processLeadOutbox();result={rows:l.rows.slice(1),mail:l.mail};}
 else throw Error('Unsupported synthetic bridge operation');
 process.stdout.write(JSON.stringify(result)+'\n');
}
