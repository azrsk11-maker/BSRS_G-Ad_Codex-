// Joined engineering slice; no contact change, receiver override or operational G5 authority.
import {readFileSync} from 'node:fs';
import {createHash} from 'node:crypto';
import {buildG3ProfileCandidate} from './build-g3-profile-candidate.mjs';
import {buildNativePageContextClient,buildNativePageContextPresentation,reverseNativePageContext} from './build-native-page-context-candidate.mjs';
import {buildNativeFrameParent,buildNativeFrameChild,reverseNativeFrame} from './build-native-frame-candidate.mjs';
import {buildFrameDeliveryCandidate} from './build-frame-delivery-candidate.mjs';
const sha=value=>createHash('sha256').update(value).digest('hex');
export function buildG34ProfileCandidate(auditBytes){
  const parent=buildG3ProfileCandidate(auditBytes),files=new Map(parent.files.map(r=>[r.path,Buffer.from(r.content_base64,'base64')]));
  const lead=files.get('assets/lead.js').toString('utf8'),presentation=files.get('includes/presentation.php').toString('utf8');
  const client=buildNativePageContextClient(lead,sha(lead)),render=buildNativePageContextPresentation(presentation,sha(presentation));
  if(reverseNativePageContext(client)!==lead||reverseNativePageContext(render)!==presentation)throw new Error('G34_NATIVE_REVERSE_FAILED');
  files.set('assets/lead.js',Buffer.from(client.output));files.set('includes/presentation.php',Buffer.from(render.output));
  const frame=buildFrameDeliveryCandidate(files.get('assets/google-measurement.js'));
  const paired=buildNativeFrameParent(frame,sha(frame)),childSource=files.get('assets/google-runtime.js').toString('utf8');
  const child=buildNativeFrameChild(childSource,sha(childSource));
  if(reverseNativeFrame(paired)!==frame||reverseNativeFrame(child)!==childSource)throw new Error('G34_FRAME_REVERSE_FAILED');
  files.set('assets/google-measurement.js',Buffer.from(paired.output));files.set('assets/google-runtime.js',Buffer.from(child.output));
  files.set('includes/candidate/tracking/NativePageContext.php',readFileSync(new URL('./native-page-context/NativePageContext.php',import.meta.url)));
  const bootstrap=files.get('includes/g3-profile/bootstrap.php').toString('utf8'),anchor="require_once __DIR__.'/route-context.php';";
  if(bootstrap.split(anchor).length!==2)throw new Error('G34_BOOTSTRAP_ANCHOR_CHANGED');
  const insertion="require_once __DIR__.'/../candidate/tracking/NativePageContext.php';\n"+anchor;
  const next=bootstrap.replace(anchor,insertion);
  if(next.split(insertion).length!==2 || next.replace(insertion,anchor)!==bootstrap)throw new Error('G34_BOOTSTRAP_REVERSE_FAILED');
  files.set('includes/g3-profile/bootstrap.php',Buffer.from(next));
  return Object.freeze({profile:'G34_NATIVE_CONTEXT_FRAME_V2',status:'HELD_COMPOUND_NATIVE_ACCEPTANCE_REQUIRED',deployment_prohibited:true,
    original_members:30,complete_coupled_profile:false,operational_g5_selected:false,
    files:Object.freeze([...files].sort(([a],[b])=>a.localeCompare(b)).map(([path,bytes])=>Object.freeze({path,sha256:sha(bytes),content_base64:bytes.toString('base64')})))});
}
