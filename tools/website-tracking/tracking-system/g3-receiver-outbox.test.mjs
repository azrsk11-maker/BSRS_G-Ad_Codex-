import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {createHmac} from 'node:crypto';
import {spawnSync} from 'node:child_process';
import {lab} from '../../staging-lab/receiver-lab.mjs';

test('admission bridge snapshots never drain mail; explicit bounded outbox preserves ten identities once',()=>{
  let source=readFileSync(new URL('./retention-admission-bridge.mjs',import.meta.url),'utf8');
  for(const [before,after] of [
    ['/opt/lab/receiver-lab.mjs',new URL('../../staging-lab/receiver-lab.mjs',import.meta.url).href],
    ['/opt/lab/tracking-system/build-retention-admission-candidate.mjs',new URL('./build-retention-admission-candidate.mjs',import.meta.url).href],
    ["readFileSync('/opt/lab/fixtures/receiver-v2/Code.gs')","readFileSync(new URL("+JSON.stringify(new URL('../../staging-lab/fixtures/receiver-v2/Code.gs',import.meta.url).href)+"))"],
  ]){assert.equal(source.split(before).length,2);source=source.replace(before,after);}
  const receiver=lab(),commands=[];
  for(let i=0;i<10;i++){
    const body=JSON.stringify(receiver.payload()),timestamp=String(Date.now());
    const signature=createHmac('sha256','synthetic-key-'.repeat(4)).update(`v1\n${timestamp}\n${body}`).digest('hex');
    commands.push({op:'post',raw:JSON.stringify({version:1,timestamp,body,signature})});
  }
  commands.push({op:'snapshot'},{op:'snapshot'},{op:'outbox'},{op:'outbox'},{op:'outbox'},{op:'snapshot'},{op:'delivery_audit'});
  const process=spawnSync(globalThis.process.execPath,['--input-type=module','-e',source],{input:commands.map(row=>JSON.stringify(row)).join('\n')+'\n',encoding:'utf8',timeout:10000,maxBuffer:1024*1024});
  assert.equal(process.status,0,process.stderr);
  const rows=process.stdout.trim().split('\n').map(line=>JSON.parse(line));
  assert.equal(rows.length,17);assert.ok(rows.slice(0,10).every(row=>row.accepted===true));
  assert.deepEqual(rows[10],{rows:10,mail:0,columns:26});assert.deepEqual(rows[11],rows[10]);
  assert.deepEqual(rows.slice(12,15),[{sent:5},{sent:5},{sent:0}]);
  assert.deepEqual(rows[15],{rows:10,mail:10,columns:26});
  assert.deepEqual(rows[16],{rows:10,mail:10,columns:26,exact_once_identity:true});
});
