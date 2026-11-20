/** Private source manifest only; no activation/provider/native execution/source mutation. */
import{readFileSync,writeFileSync}from'node:fs';
import{createHash}from'node:crypto';
import{join,dirname}from'node:path';
import{fileURLToPath,pathToFileURL}from'node:url';
const here=dirname(fileURLToPath(import.meta.url));
export const folder=join(here,'candidate/plugin/includes/candidate/retention');
export const names=['ActualPreferenceRetention.php','PreferenceAlgebra.php','PreferenceAtomicStore.php','PreferenceContracts.php','PreferenceCustody.php'];
export const sha=b=>createHash('sha256').update(b).digest('hex');
export function buildManifest(){
 const files=Object.fromEntries([...names].sort().map(name=>[name,sha(readFileSync(join(folder,name)))]));
 const bytes=Buffer.from(JSON.stringify({contract:'bsre-preference-runtime-v1',files})+'\n');
 return{bytes,sha256:sha(bytes),files};
}
if(process.argv[1]&&import.meta.url===pathToFileURL(process.argv[1]).href){
 const m=buildManifest();writeFileSync(join(folder,'preference-source.json'),m.bytes);
 writeFileSync(join(here,'RUNTIME_SOURCE_PROGRESS.json'),JSON.stringify({status:'PRIVATE_EARLY_DRAFT_NATIVE_UNEXECUTED',source_manifest_sha256:m.sha256,files:m.files,
  operational_acceptance:false,source_or_git_changed:false,unresolved_gates:['independent code review','actual PHP/SQL both-profile acceptance','real G2 concurrency schedules','genuine provider enrollment/keys/evidence','per-subject and partition scale acceptance','production and human release gates']},null,2)+'\n');
 process.stdout.write(JSON.stringify({source_manifest_sha256:m.sha256,files:5,native_execution:false})+'\n');
}
