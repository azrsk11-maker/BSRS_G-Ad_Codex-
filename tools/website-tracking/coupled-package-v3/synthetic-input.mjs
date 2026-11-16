/** Public test helper. All replacement identities/approval records are explicitly synthetic. */
import {readFileSync} from 'node:fs';
import {resolve,join} from 'node:path';
import {fileURLToPath,pathToFileURL} from 'node:url';
import {digest} from './compose-v3.mjs';
export const SOURCE_ROOT=resolve(process.env.BSRE_SOURCE_ROOT||fileURLToPath(new URL('../../../',import.meta.url)));
export async function syntheticInput({source_root=SOURCE_ROOT,digits='19995550123',display='+1 999 555 0123',comment=false}={}){
  const root=resolve(source_root),dir=join(root,'tools/website-tracking/coupled-package'),track=join(root,'tools/website-tracking/tracking-system');
  const pins=JSON.parse(readFileSync(join(dir,'baseline-pins.json'))),g3Pins=readFileSync(join(dir,'g3-source-pins-v2.json')),g4Pins=readFileSync(join(dir,'g4-source-pins-v2.json'));
  const {readRegularTree,RECONCILIATION}=await import(pathToFileURL(join(dir,'compose.mjs')).href);
  const original=readRegularTree(join(root,'tools/staging-lab/fixtures/bsre-enquiries'),Object.keys(pins.members));
  const captured=new Map([...original].map(([p,b])=>[p,Buffer.from(b)])),counts={};
  const old=original.get('assets/lead.js').toString().match(/wa\\\.me\\\/([1-9][0-9]+)/)[1];
  const oldDisplay=original.get('templates/source/rent.html').toString().match(/<small>Speak with Black Swan<\/small>(\+[0-9 ]+)/)[1];
  const count=(s,v)=>s.split(v).length-1;
  for(const path of RECONCILIATION.slice(0,-1)){
    const source=original.get(path).toString();counts[path]={matcher:path==='assets/lead.js'?1:0,
      whatsapp:path==='assets/lead.js'?0:count(source,'https://wa.me/'+old),telephone:path==='assets/lead.js'?0:count(source,'tel:+'+old),display:path==='assets/lead.js'?0:count(source,oldDisplay)};
    captured.set(path,Buffer.from(source.replaceAll(old,digits).replaceAll(oldDisplay,display)));
  }
  const hub=digest(captured.get('templates/source/hub.html'));
  captured.set('includes/parent-isolation.php',Buffer.from(original.get('includes/parent-isolation.php').toString().replace(pins.members['templates/source/hub.html'],hub)));
  const {buildG3ProfileCandidate}=await import(pathToFileURL(join(track,'build-g3-profile-candidate.mjs')).href);
  const {buildG34ProfileCandidate}=await import(pathToFileURL(join(track,'build-g34-profile-candidate.mjs')).href);
  const {buildFrameDeliveryCandidate}=await import(pathToFileURL(join(track,'build-frame-delivery-candidate.mjs')).href);
  const audit=readFileSync(join(root,'docs/audit/INSTALLED_SOURCE_COMPARISON_2026-11-07.json'));
  const g3=buildG3ProfileCandidate(audit),g34=buildG34ProfileCandidate(audit);
  const base=new Map(g3.files.map(r=>['plugin/'+r.path,Buffer.from(r.content_base64,'base64')]));
  const joined=new Map(g34.files.map(r=>['plugin/'+r.path,Buffer.from(r.content_base64,'base64')]));
  const before=new Map([['plugin/assets/lead.js',base.get('plugin/assets/lead.js')],['plugin/includes/presentation.php',base.get('plugin/includes/presentation.php')],
    ['plugin/assets/google-measurement.js',Buffer.from(buildFrameDeliveryCandidate(original.get('assets/google-measurement.js')))],['plugin/assets/google-runtime.js',base.get('plugin/assets/google-runtime.js')]]);
  const g4={schema:'bsre-g4-composition-selection-v2',profile:'G4_NATIVE_CLIENT_PARENT_CHILD_V2',source_manifest_sha256:digest(g4Pins),
    preimages:Object.fromEntries([...before].map(([p,b])=>[p,digest(b)])),outputs:Object.fromEntries([...before.keys(),
      'plugin/includes/candidate/tracking/NativePageContext.php','plugin/includes/g3-profile/bootstrap.php'].map(p=>[p,digest(joined.get(p))])),deployment_prohibited:true};
  const g3Bytes=Buffer.from(JSON.stringify(g3)),g4Bytes=Buffer.from(JSON.stringify(g4));
  const selection=(profile,pin,bytes)=>({schema:'bsre-coupled-selection-receipt-v2',profile,source_manifest_sha256:digest(pin),manifest_sha256:digest(bytes),deployment_prohibited:true});
  const entries=map=>[...map].map(([path,bytes])=>({path,bytes:Buffer.from(bytes)}));
  const v2={source_root:root,original:entries(original),captured:entries(captured),identity:{from_digits:old,to_digits:digits,from_display:oldDisplay,to_display:display},
    provenance:{original_zip_sha256:pins.original_zip_sha256,member_map_sha256:pins.member_map_sha256},
    receiver_original:readFileSync(join(root,'tools/staging-lab/fixtures/receiver-v2/Code.gs')),
    capture_binding:{review_ref:'SYNTHETIC_SOURCE_ONLY_V3_TEST',members:Object.fromEntries([...captured].map(([p,b])=>[p,digest(b)])),reviewed_counts:counts},
    native_binding:{expected_body_sha256:hub,captured_body_sha256:hub},g3_base_manifest_bytes:g3Bytes,
    g3_selection_receipt:selection(g3.profile,g3Pins,g3Bytes),g4_source_root:root,g4_manifest_bytes:g4Bytes,
    g4_selection_receipt:selection(g4.profile,g4Pins,g4Bytes)};
  if(comment){
    const path='includes/parent-isolation.php',row=v2.captured.find(r=>r.path===path);
    const oldLine='// Exact native serialization reviewed on 22 October. No normalization or CMS writes.';
    const template='// Exact native serialization reviewed on 11 November (phone number updated to +<CURRENT_CONTACT_DISPLAY_WITHOUT_PLUS>). No normalization or CMS writes.';
    const next=template.replace('<CURRENT_CONTACT_DISPLAY_WITHOUT_PLUS>',display.slice(1));row.bytes=Buffer.from(row.bytes.toString().replace(oldLine,next));v2.capture_binding.members[path]=digest(row.bytes);
    const review=Buffer.from(JSON.stringify({schema:'bsre-private-capture-comment-engineering-review-v1',original_guard_sha256:pins.members[path],original_comment:oldLine+'\n',captured_comment_template:template+'\n',
      original_offset:64,original_length:Buffer.byteLength(oldLine),captured_length:Buffer.byteLength(next),comment_delta:Buffer.byteLength(next)-Buffer.byteLength(oldLine),
      original_capture_preserved:true,no_baseline_repin:true,no_normalization:true,engineering_exception_authorized:true,
      human_approval:false,native_acceptance:false,provider_acceptance:false,production_authorized:false,ads_authorized:false,complete_profile_certified:false}));
    const owner=Buffer.from(JSON.stringify({authority:'owner_confirmed_business_destination',canonical_destination_sha256:digest(digits),permitted_channels:['telephone','WhatsApp']}));
    v2.capture_guard_comment_review={review_record_bytes:review,review_record_sha256:digest(review),review_ref:'SYNTHETIC_V3_COMMENT_REVIEW',owner_authority_record_bytes:owner,
      owner_authority_record_sha256:digest(owner),captured_comment_sha256:digest(next),captured_guard_sha256:digest(row.bytes)};
  }
  return {source_root:root,v2_input:v2};
}
