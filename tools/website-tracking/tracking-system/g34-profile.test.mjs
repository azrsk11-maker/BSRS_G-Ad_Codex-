import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {buildG3ProfileCandidate} from './build-g3-profile-candidate.mjs';
import {buildG34ProfileCandidate} from './build-g34-profile-candidate.mjs';
const audit=readFileSync(new URL('../../../docs/audit/INSTALLED_SOURCE_COMPARISON_2026-11-07.json',import.meta.url));
test('joined G34 tree preserves complete G3 back end and declares its narrower held scope',()=>{
  const parent=buildG3ProfileCandidate(audit),joined=buildG34ProfileCandidate(audit);
  const before=new Map(parent.files.map(r=>[r.path,r.content_base64])),after=new Map(joined.files.map(r=>[r.path,r.content_base64]));
  assert.equal(after.size,42);assert.equal(joined.deployment_prohibited,true);assert.equal(joined.complete_coupled_profile,false);assert.equal(joined.operational_g5_selected,false);
  const changed=['assets/lead.js','assets/google-measurement.js','assets/google-runtime.js','includes/presentation.php','includes/g3-profile/bootstrap.php'];
  for(const [path,content]of before)if(!changed.includes(path))assert.equal(after.get(path),content,path);
  const boot=Buffer.from(after.get('includes/g3-profile/bootstrap.php'),'base64').toString();
  assert.ok(boot.indexOf('/../candidate/tracking/NativePageContext.php')<boot.indexOf('boot();'));
  for(const path of ['assets/google-measurement.js','assets/google-runtime.js'])assert.ok(Buffer.from(after.get(path),'base64').toString().includes('bsre-native-page-context-v2'));
});
