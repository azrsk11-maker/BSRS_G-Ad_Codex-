/** Explicit capture-only comment compatibility. Never changes or repins actual raw bytes. */
import {readFileSync} from 'node:fs';
import {memberMap,digest} from './compose.mjs';
const pins=JSON.parse(readFileSync(new URL('./baseline-pins.json',import.meta.url)));
const GUARD='includes/parent-isolation.php',HUB='templates/source/hub.html';
const OLD='// Exact native serialization reviewed on 22 October. No normalization or CMS writes.';
const TEMPLATE='// Exact native serialization reviewed on 11 November (phone number updated to +<CURRENT_CONTACT_DISPLAY_WITHOUT_PLUS>). No normalization or CMS writes.';
const need=(ok,code)=>{if(!ok)throw new Error(code);};
const keys=(value,expected)=>value&&typeof value==='object'&&!Array.isArray(value)&&Object.keys(value).sort().join(',')===[...expected].sort().join(',');
const isHash=value=>typeof value==='string'&&/^[a-f0-9]{64}$/.test(value);
function rawJSON(bytes,sha){need(Buffer.isBuffer(bytes)&&bytes.length>0&&bytes.length<=65536&&isHash(sha)&&digest(bytes)===sha,'V2_CAPTURE_REVIEW_HASH');return JSON.parse(bytes.toString('utf8'));}
export function prepareGuardCaptureCompatibilityView(input){
  if(input.capture_guard_comment_review===undefined)return {input,proof:null};
  const policy=input.capture_guard_comment_review;
  need(keys(policy,['review_record_bytes','review_record_sha256','review_ref','owner_authority_record_bytes','owner_authority_record_sha256','captured_comment_sha256','captured_guard_sha256'])&&
    typeof policy.review_ref==='string'&&policy.review_ref.length>0&&policy.review_ref.length<=256,'V2_CAPTURE_REVIEW_SHAPE');
  const review=rawJSON(policy.review_record_bytes,policy.review_record_sha256),authority=rawJSON(policy.owner_authority_record_bytes,policy.owner_authority_record_sha256);
  const denied=['human_approval','native_acceptance','provider_acceptance','production_authorized','ads_authorized','complete_profile_certified'];
  need(review.schema==='bsre-private-capture-comment-engineering-review-v1'&&review.engineering_exception_authorized===true&&
    review.original_capture_preserved===true&&review.no_baseline_repin===true&&review.no_normalization===true&&denied.every(k=>review[k]===false)&&
    review.original_guard_sha256===pins.members[GUARD]&&review.original_comment===OLD+'\n'&&review.captured_comment_template===TEMPLATE+'\n','V2_CAPTURE_REVIEW_UNAUTHORIZED');
  const digits=input.identity?.to_digits,display=input.identity?.to_display;
  need(typeof digits==='string'&&/^[1-9][0-9]{6,14}$/.test(digits)&&authority.authority==='owner_confirmed_business_destination'&&
    typeof display==='string'&&/^\+[0-9 ]{7,22}$/.test(display)&&display.replace(/\D/g,'')===digits&&
    authority.canonical_destination_sha256===digest(digits)&&Array.isArray(authority.permitted_channels)&&authority.permitted_channels.length===2&&
    authority.permitted_channels.map(s=>String(s).toLowerCase()).sort().join(',')==='telephone,whatsapp','V2_CAPTURE_COMMENT_AUTHORITY');
  const original=memberMap(input.original,Object.keys(pins.members)),actual=memberMap(input.captured,Object.keys(pins.members));
  need(input.capture_binding?.members&&Object.keys(input.capture_binding.members).length===30,'V2_CAPTURE_RAW_BINDING');
  for(const [path,bytes]of actual)need(isHash(input.capture_binding.members[path])&&input.capture_binding.members[path]===digest(bytes),'V2_CAPTURE_RAW_BINDING');
  const before=original.get(GUARD),captured=actual.get(GUARD),next=TEMPLATE.replace('<CURRENT_CONTACT_DISPLAY_WITHOUT_PLUS>',display.slice(1));
  need(digest(before)===pins.members[GUARD]&&digest(captured)===policy.captured_guard_sha256&&
    digest(next)===policy.captured_comment_sha256,'V2_CAPTURE_COMMENT_BINDING');
  const text=before.toString('utf8'),at=text.indexOf(OLD),offset=Buffer.byteLength(text.slice(0,at));
  need(Buffer.from(text).equals(before)&&at>=0&&text.split(OLD).length===2&&offset===64&&before[offset-1]===10&&
    before[offset+Buffer.byteLength(OLD)]===10&&review.original_offset===offset&&review.original_length===Buffer.byteLength(OLD)&&
    review.captured_length===Buffer.byteLength(next)&&review.comment_delta===Buffer.byteLength(next)-Buffer.byteLength(OLD)&&
    !/[\r\n\x00]|<\?|\?>/.test(next)&&/^[\x20-\x7e]+$/.test(next),'V2_CAPTURE_COMMENT_SPAN');
  const oldHash=digest(original.get(HUB)),newHash=digest(actual.get(HUB));
  const oldConstant="const OWNED_HUB_SHA256 = '"+oldHash+"';",newConstant="const OWNED_HUB_SHA256 = '"+newHash+"';";
  need(text.split(oldConstant).length===2,'V2_CAPTURE_GUARD_CONSTANT');
  const expected=Buffer.from(text.replace(OLD,next).replace(oldConstant,newConstant));
  need(expected.equals(captured),'V2_CAPTURE_GUARD_UNRELATED_CHANGE');
  const capturedText=captured.toString('utf8');need(capturedText.split(next).length===2,'V2_CAPTURE_COMMENT_ANCHOR');
  const derived=Buffer.from(capturedText.replace(next,OLD));
  need(derived.equals(Buffer.from(text.replace(oldConstant,newConstant))),'V2_CAPTURE_COMPATIBILITY_VIEW');
  const view=new Map(actual);view.set(GUARD,derived);
  const members={...input.capture_binding.members,[GUARD]:digest(derived)};
  const actualBytes=[...actual.values()].reduce((n,b)=>n+b.length,0),viewBytes=[...view.values()].reduce((n,b)=>n+b.length,0);
  return {input:{...input,captured:[...view].map(([path,bytes])=>({path,bytes})),capture_binding:{...input.capture_binding,members}},proof:{
    classification:'PRIVATE_DO_NOT_PUBLISH',kind:'EXPLICIT_CAPTURE_ONLY_PROVENANCE_COMMENT_POLICY',review_ref:policy.review_ref,
    review_record_sha256:policy.review_record_sha256,owner_authority_record_sha256:policy.owner_authority_record_sha256,
    actual_raw_members:[...actual].map(([path,bytes])=>({path,bytes:bytes.length,sha256:digest(bytes)})),actual_raw_bytes:actualBytes,
    compatibility_view_label:'DERIVED_EXACT_INVERSE_COMMENT_VIEW_NOT_RAW_CAPTURE',compatibility_view_bytes:viewBytes,
    actual_guard_sha256:digest(captured),derived_guard_sha256:digest(derived),original_guard_sha256:digest(before),
    captured_comment_sha256:policy.captured_comment_sha256,comment_delta_bytes:actualBytes-viewBytes,comment_identity_representation:'EXACT_CAPTURED_DISPLAY_WITH_CANONICAL_AUTHORITY_BINDING',
    capture_transform_spans:[{offset,removed_bytes:Buffer.byteLength(OLD),added_bytes:Buffer.byteLength(next),kind:'EXACT_REVIEWED_PROVENANCE_COMMENT'},
      {offset:Buffer.byteLength(text.slice(0,text.indexOf(oldConstant))+"const OWNED_HUB_SHA256 = '"),removed_bytes:64,added_bytes:64,kind:'PAIRED_HUB_DIGEST'}],
    capture_reverse_verified:true,all_other_capture_members_identical:true,actual_capture_rewritten:false,baseline_repinned:false,normalization_performed:false,
    candidate_guard_policy:'IMMUTABLE_ORIGINAL_PLUS_FINAL_HUB_CONSTANT_ONLY',complete_profile_certified:false,deployment_prohibited:true}};
}
