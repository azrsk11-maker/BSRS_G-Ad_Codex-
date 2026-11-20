/** Pure fixed-lab packet builder. It writes no file and provisions no provider. */
import {readFileSync} from 'node:fs';
import {digest} from './build-candidate.mjs';
export function buildReceiverRuntimeNativeLab(){
 const paths=[
  'build-candidate.mjs','runtime/control.gs','runtime/no-copy.gs',
  'candidate/plugin/includes/candidate/receiver/ReceiverContracts.php',
  'candidate/plugin/includes/candidate/receiver/NoMailCopyAlgebra.php',
  'candidate/plugin/includes/candidate/receiver/ActualRetirementPort.php',
  'candidate/plugin/includes/candidate/receiver/ReceiverOperationalEvidence.php',
  'candidate/plugin/includes/candidate/receiver/ActualReceiverWorkflow.php',
  'candidate/plugin/includes/candidate/closed-enquiry-retention/ActualReceiverJournal.php',
  'tests/control-fixture.mjs','tests/native-bridge.mjs','tests/receiver-runtime-native.php',
 ];
 const files=new Map(paths.map(path=>[path,readFileSync(new URL(path,import.meta.url))]));
 const manifest={schema:'bsre-receiver-runtime-synthetic-lab-v1',profile:'G5_ACTUAL_RECEIVER_ENGINEERING_ONLY',
  files:Object.fromEntries([...files].map(([path,bytes])=>[path,{sha256:digest(bytes),bytes:bytes.length}]))};
 files.set('CANDIDATE_BUILD.json',Buffer.from(JSON.stringify(manifest,null,2)+'\n'));
 return {files,manifest,synthetic_only:true,provider_accepted:false,production_authorized:false};
}
