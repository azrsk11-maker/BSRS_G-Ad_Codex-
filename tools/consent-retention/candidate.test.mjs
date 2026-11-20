import {test} from 'node:test';
import assert from 'node:assert/strict';
import {mkdtempSync,readFileSync,writeFileSync,rmSync,existsSync} from 'node:fs';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {fileURLToPath} from 'node:url';
import {spawnSync} from 'node:child_process';
const generator=fileURLToPath(new URL('./build-candidate.mjs',import.meta.url));
const baseline=readFileSync(new URL('../staging-lab/fixtures/bsre-enquiries/includes/consent-store.php',import.meta.url));
for(const tamper of [false,true])test(tamper?'changed store cannot generate a candidate':'pinned store derives isolated candidate without changing input',()=>{
 const dir=mkdtempSync(join(tmpdir(),'bsre-retention-'));
 try {
  const input=join(dir,'baseline.php'),output=join(dir,'candidate.php');
  const bytes=tamper?Buffer.concat([baseline,Buffer.from('\n// changed')]):baseline;
  writeFileSync(input,bytes);
  const run=spawnSync(process.execPath,[generator,input,output],{encoding:'utf8',timeout:5000});
  assert.deepEqual(readFileSync(input),bytes);
  if(tamper){assert.notEqual(run.status,0);assert.equal(existsSync(output),false);}
  else {assert.equal(run.status,0,run.stderr);const generated=readFileSync(output,'utf8');assert.match(generated,/namespace BSRE\\RetentionCandidate/);assert.match(generated,/Consent evidence retired/);}
 } finally {rmSync(dir,{recursive:true,force:true});}
});
