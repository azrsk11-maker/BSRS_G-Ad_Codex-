/** Explicit V2: actual G2/G3 paths and independently bound G4-before-contact derivations.
 * V1 remains a separate unchanged profile. All output is inert and held. */
import {readFileSync,lstatSync,realpathSync} from 'node:fs';
import {resolve,join,sep,relative,isAbsolute} from 'node:path';
import {pathToFileURL} from 'node:url';
import {composeCoupledPackage,digest,memberMap,RECONCILIATION} from './compose.mjs';
import {prepareGuardCaptureCompatibilityView} from './capture-guard-policy-v2.mjs';

const readJson=name=>JSON.parse(readFileSync(new URL(name,import.meta.url),'utf8'));
const contract=readJson('./profile-contract-v2.json');
for(const value of Object.values(contract))if(value&&typeof value==='object')Object.freeze(value);
export const CONTRACT_V2=Object.freeze(contract);
const baseline=readJson('./baseline-pins.json');
const g3Raw=readFileSync(new URL('./g3-source-pins-v2.json',import.meta.url));
const G3_SOURCE_MANIFEST_SHA256='026cafda14b0808be2cbe1a5821483cbb524542f935fbcbf6c587731c465af24';
const g3Pins=JSON.parse(g3Raw);
const g4Raw=readFileSync(new URL('./g4-source-pins-v2.json',import.meta.url));
const G4_SOURCE_MANIFEST_SHA256='13d5fdbfa0c15bac52759b669983adf13bd0e4382d5793e4b70718ad9513a053';
const g4Pins=JSON.parse(g4Raw);
const need=(ok,code)=>{if(!ok)throw new Error(code);};
need(digest(g3Raw)===G3_SOURCE_MANIFEST_SHA256,'V2_G3_SOURCE_MANIFEST_CHANGED');
need(digest(g4Raw)===G4_SOURCE_MANIFEST_SHA256,'V2_G4_SOURCE_MANIFEST_CHANGED');
const hash=value=>typeof value==='string'&&/^[a-f0-9]{64}$/.test(value);
const sameKeys=(value,keys)=>value&&typeof value==='object'&&!Array.isArray(value)&&Object.keys(value).sort().join(',')===[...keys].sort().join(',');
const LEAD='plugin/assets/lead.js',PRESENTATION='plugin/includes/presentation.php';
const PARENT='plugin/assets/google-measurement.js',CHILD='plugin/assets/google-runtime.js';
const G3_BOOTSTRAP='plugin/includes/g3-profile/bootstrap.php',PORT='plugin/includes/candidate/tracking/NativePageContext.php';
const g3Module='tools/website-tracking/tracking-system/build-g3-profile-candidate.mjs';
const g4Module='tools/website-tracking/tracking-system/build-native-page-context-candidate.mjs';
const g4Frame='tools/website-tracking/tracking-system/build-native-frame-candidate.mjs';
const g4Port='tools/website-tracking/tracking-system/native-page-context/NativePageContext.php';
function regularFile(root,name,expected) {
  need(typeof name==='string'&&/^[a-zA-Z0-9_.\/-]+$/.test(name)&&!name.startsWith('/')&&name.split('/').every(p=>p&&p!=='.'&&p!=='..'),'V2_MODULE_PATH');
  const absolute=resolve(root),file=resolve(absolute,name),rel=relative(absolute,file);
  need(!rel.startsWith('..')&&!isAbsolute(rel)&&realpathSync(absolute).toLowerCase()===absolute.toLowerCase(),'V2_MODULE_ROOT_REDIRECTED');
  let at=absolute;need(lstatSync(at).isDirectory()&&!lstatSync(at).isSymbolicLink(),'V2_MODULE_ROOT_REDIRECTED');
  for(const part of rel.split(sep)){at=join(at,part);need(!lstatSync(at).isSymbolicLink(),'V2_MODULE_LINK');}
  const stat=lstatSync(file);need(stat.isFile()&&stat.size>0&&stat.size<=1048576,'V2_MODULE_SIZE');
  const bytes=readFileSync(file);need(hash(expected)&&digest(bytes)===expected,'V2_SOURCE_PIN_CHANGED');return {file,bytes};
}
function verifySource(root,pins) {for(const [path,sha]of Object.entries(pins.modules))regularFile(root,path,sha);}
function receipt(value,profile,sourceHash,manifestHash) {
  need(sameKeys(value,['schema','profile','source_manifest_sha256','manifest_sha256','deployment_prohibited'])&&
    value.schema==='bsre-coupled-selection-receipt-v2'&&value.profile===profile&&value.source_manifest_sha256===sourceHash&&
    value.manifest_sha256===manifestHash&&value.deployment_prohibited===true,'V2_SELECTION_RECEIPT_CHANGED');
}
function decodeG3(raw) {
  need(Buffer.isBuffer(raw)&&raw.length>0&&raw.length<=2097152,'V2_G3_MANIFEST_BYTES');
  const manifest=JSON.parse(raw.toString('utf8'));
  need(manifest.profile==='G3_ROUTE_CONTEXT_ADMISSION_CLIENT_ONLY'&&manifest.original_members===30&&
    manifest.deployment_prohibited===true&&manifest.complete_coupled_profile===false&&Array.isArray(manifest.files),'V2_G3_MANIFEST_FLAGS');
  const entries=manifest.files.map(row=>{need(sameKeys(row,['path','sha256','content_base64'])&&typeof row.content_base64==='string'&&
      row.content_base64.length<=1398104,'V2_G3_MEMBER_SHAPE');const bytes=Buffer.from(row.content_base64,'base64');
    need(bytes.toString('base64')===row.content_base64&&hash(row.sha256)&&digest(bytes)===row.sha256,'V2_G3_MEMBER_HASH');
    return {path:row.path,bytes};});
  return memberMap(entries);
}
function reverseBound(result,before,reverse,kind) {
  need(result&&result.preimage_sha256===digest(before)&&typeof result.output==='string'&&
    result.output_sha256===digest(result.output)&&Array.isArray(result.edits)&&result.edits.length>0,'V2_G4_RECEIPT_CHANGED');
  need(Buffer.from(reverse(result)).equals(before),'V2_G4_REVERSE_CHANGED');
  let intermediate=before.toString('utf8');const ranges=[];
  for(const edit of result.edits){need(typeof edit.before==='string'&&typeof edit.after==='string'&&intermediate.split(edit.before).length===2,'V2_G4_EDIT_ANCHOR');
    const at=intermediate.indexOf(edit.before);ranges.push({offset:Buffer.byteLength(intermediate.slice(0,at)),removed_bytes:Buffer.byteLength(edit.before),added_bytes:Buffer.byteLength(edit.after)});
    intermediate=intermediate.replace(edit.before,edit.after);}
  need(intermediate===result.output,'V2_G4_EDIT_SEQUENCE');
  return {kind,preimage_sha256:result.preimage_sha256,output_sha256:result.output_sha256,edit_count:result.edits.length,ordered_edit_ranges:ranges,reverse_verified:true};
}
function contactAfterG4(bytes,identity) {
  const prefix=Buffer.from(String.raw`/^https:\/\/wa\.me\/`),suffix=Buffer.from(String.raw`(?:\?|$)/.test(href)`);
  const anchor=bytes.indexOf(prefix),start=anchor+prefix.length,end=bytes.indexOf(suffix,start);
  need(anchor>=0&&bytes.indexOf(prefix,start)===-1&&end>start&&bytes.indexOf(suffix,end+suffix.length)===-1,'V2_G4_CONTACT_ANCHOR');
  const old=Buffer.from(identity.from_digits),current=Buffer.from(identity.to_digits);
  need(bytes.subarray(start,end).equals(old),'V2_G4_CONTACT_PREIMAGE');
  const out=Buffer.concat([bytes.subarray(0,start),current,bytes.subarray(end)]);
  need(Buffer.concat([out.subarray(0,start),old,out.subarray(start+current.length)]).equals(bytes),'V2_G4_CONTACT_REVERSE');
  return {bytes:out,range:{offset:start,removed_bytes:old.length,added_bytes:current.length,kind:'matcher'},reverse_verified:true};
}
function bootstrapPort(bytes) {
  const before="require_once __DIR__.'/route-context.php';";
  const include="require_once __DIR__.'/../candidate/tracking/NativePageContext.php';\n";
  const text=bytes.toString('utf8');need(text.split(before).length===2,'V2_G4_BOOTSTRAP_ANCHOR');
  const after=include+before,out=Buffer.from(text.replace(before,after));
  need(Buffer.from(out.toString().replace(after,before)).equals(bytes),'V2_G4_BOOTSTRAP_REVERSE');
  return {bytes:out,proof:{kind:'G4_NATIVE_PORT_BOOTSTRAP_INCLUDE',preimage_sha256:digest(bytes),output_sha256:digest(out),edit_count:1,reverse_verified:true}};
}
async function compose(input) {
  need(input&&typeof input==='object','V2_INPUT_REQUIRED');
  const identity={...input.identity};
  // Reuse V1 solely to revalidate the immutable30 and exact22/8 contact closure.
  const compatibility=prepareGuardCaptureCompatibilityView({...input,identity});
  const prior=await composeCoupledPackage({...compatibility.input,identity,selected_outputs:[],selected_output_pins:{},require_all_selected_outputs:false});
  if(compatibility.proof){const guard=prior.private_manifest.ancestry.find(r=>r.member==='includes/parent-isolation.php');
    guard.captured_compatibility_view_sha256=guard.captured_sha256;guard.captured_sha256=compatibility.proof.actual_guard_sha256;
    guard.raw_capture_transform_spans=compatibility.proof.capture_transform_spans;guard.raw_capture_reverse_verified=true;}
  verifySource(input.source_root,g3Pins);
  const audit=regularFile(input.source_root,g3Pins.audit_path,g3Pins.audit_sha256).bytes;
  receipt(input.g3_selection_receipt,'G3_ROUTE_CONTEXT_ADMISSION_CLIENT_ONLY',G3_SOURCE_MANIFEST_SHA256,digest(input.g3_base_manifest_bytes));
  const supplied=decodeG3(input.g3_base_manifest_bytes);
  const builder=await import(pathToFileURL(regularFile(input.source_root,g3Module,g3Pins.modules[g3Module]).file).href);
  const independent=builder.buildG3ProfileCandidate(audit);
  const expected=memberMap(independent.files.map(row=>({path:row.path,bytes:Buffer.from(row.content_base64,'base64')})));
  need(supplied.size===41&&expected.size===41&&[...expected].every(([p,b])=>supplied.has(p)&&supplied.get(p).equals(b)),'V2_G3_ANCESTRY_CHANGED');
  const files=new Map([...supplied].map(([p,b])=>['plugin/'+p,Buffer.from(b)]));
  const clientProof=prior.private_manifest.ancestry.find(r=>r.member==='assets/lead.js');
  need(digest(files.get(LEAD))===clientProof.precontact_sha256,'V2_G3_ADMISSION_CLIENT_CHANGED');
  for(const path of RECONCILIATION.filter(p=>p!=='assets/lead.js'))need(digest(files.get('plugin/'+path))===baseline.members[path],'V2_G3_CONTACT_BASE_CHANGED');
  for(const path of [...RECONCILIATION.map(p=>'plugin/'+p),PARENT,'companion/receiver/Code.gs'])files.set(path,Buffer.from(prior.files.get(path)));
  const stages=[];let g4Selected=false,g4ManifestHash=null;
  if(input.g4_selection_receipt!==undefined||input.g4_manifest_bytes!==undefined||input.g4_source_root!==undefined){
    need(typeof input.g4_source_root==='string'&&Buffer.isBuffer(input.g4_manifest_bytes)&&input.g4_manifest_bytes.length>0&&input.g4_manifest_bytes.length<=65536,'V2_G4_SELECTION_REQUIRED');
    receipt(input.g4_selection_receipt,'G4_NATIVE_CLIENT_PARENT_CHILD_V2',G4_SOURCE_MANIFEST_SHA256,digest(input.g4_manifest_bytes));
    const selected=JSON.parse(input.g4_manifest_bytes.toString('utf8'));
    need(sameKeys(selected,['schema','profile','source_manifest_sha256','preimages','outputs','deployment_prohibited'])&&
      selected.schema==='bsre-g4-composition-selection-v2'&&selected.profile==='G4_NATIVE_CLIENT_PARENT_CHILD_V2'&&
      selected.source_manifest_sha256===G4_SOURCE_MANIFEST_SHA256&&selected.deployment_prohibited===true,'V2_G4_MANIFEST_CHANGED');
    verifySource(input.g4_source_root,g4Pins);
    const context=await import(pathToFileURL(regularFile(input.g4_source_root,g4Module,g4Pins.modules[g4Module]).file).href);
    const frame=await import(pathToFileURL(regularFile(input.g4_source_root,g4Frame,g4Pins.modules[g4Frame]).file).href);
    const before=new Map([[LEAD,supplied.get('assets/lead.js')],[PRESENTATION,supplied.get('includes/presentation.php')],
      [PARENT,prior.files.get(PARENT)],[CHILD,supplied.get('assets/google-runtime.js')]]);
    need(sameKeys(selected.preimages,[...before.keys()]),'V2_G4_PREIMAGE_SET');
    for(const [p,b]of before)need(selected.preimages[p]===digest(b),'V2_G4_PREIMAGE_CHANGED');
    const derived=[
      [LEAD,context.buildNativePageContextClient(before.get(LEAD).toString(),digest(before.get(LEAD))),context.reverseNativePageContext],
      [PRESENTATION,context.buildNativePageContextPresentation(before.get(PRESENTATION).toString(),digest(before.get(PRESENTATION))),context.reverseNativePageContext],
      [PARENT,frame.buildNativeFrameParent(before.get(PARENT).toString(),digest(before.get(PARENT))),frame.reverseNativeFrame],
      [CHILD,frame.buildNativeFrameChild(before.get(CHILD).toString(),digest(before.get(CHILD))),frame.reverseNativeFrame],
    ];
    const port=regularFile(input.g4_source_root,g4Port,g4Pins.modules[g4Port]).bytes;
    const boot=bootstrapPort(supplied.get('includes/g3-profile/bootstrap.php'));
    const outputPaths=[...before.keys(),PORT,G3_BOOTSTRAP];need(sameKeys(selected.outputs,outputPaths),'V2_G4_OUTPUT_SET');
    for(const [path,result,reverse]of derived){stages.push({path,...reverseBound(result,before.get(path),reverse,'G4_BOUND_DERIVATION')});
      need(selected.outputs[path]===digest(result.output),'V2_G4_OUTPUT_CHANGED');files.set(path,Buffer.from(result.output));}
    need(selected.outputs[PORT]===digest(port)&&selected.outputs[G3_BOOTSTRAP]===digest(boot.bytes),'V2_G4_OUTPUT_CHANGED');
    files.set(PORT,port);files.set(G3_BOOTSTRAP,boot.bytes);stages.push({path:G3_BOOTSTRAP,...boot.proof});
    const precontact=files.get(LEAD),contact=contactAfterG4(precontact,identity);files.set(LEAD,contact.bytes);
    const ancestry=prior.private_manifest.ancestry.find(r=>r.member==='assets/lead.js');
    ancestry.precontact_sha256=digest(precontact);ancestry.output_sha256=digest(contact.bytes);
    ancestry.order=['immutable-original','reload','receipt','attribution','purpose','retention-admission','G4-native-context','typed-contact-overlay-v1'];
    ancestry.allowed_ranges=[contact.range];ancestry.reverse_verified=true;
    verifySource(input.g4_source_root,g4Pins);g4Selected=true;g4ManifestHash=digest(input.g4_manifest_bytes);
  }
  const extra=memberMap(input.selected_outputs||[]),protectedPaths=new Set([...files.keys(),PORT]);
  for(const [path,bytes]of extra){need(CONTRACT_V2.required_outputs.includes(path)&&!protectedPaths.has(path),'V2_OWNED_PATH_OVERRIDE');
    need(hash(input.selected_output_pins?.[path])&&input.selected_output_pins[path]===digest(bytes),'V2_EXTERNAL_PIN_CHANGED');files.set(path,bytes);}
  need(Object.keys(input.selected_output_pins||{}).length===extra.size,'V2_EXTERNAL_PIN_SET');
  const missing=CONTRACT_V2.required_outputs.filter(p=>!files.has(p));
  const unmet=g4Selected?[]:['G4_EXPLICIT_CLIENT_PRESENTATION_PARENT_CHILD_SELECTION'];
  if(input.require_all_selected_outputs===true)need(missing.length===0&&unmet.length===0,'V2_SELECTED_OUTPUTS_INCOMPLETE');
  verifySource(input.source_root,g3Pins);
  memberMap([...files].map(([path,bytes])=>({path,bytes})),CONTRACT_V2.required_outputs.filter(p=>files.has(p)));
  const holds=[...prior.public_summary.holds,'G4_DERIVED_CLIENT_PARENT_CHILD_RUNTIME_ACCEPTANCE','G5_OPERATIONAL_AUTHORITY_AND_CUSTODY_UNIMPLEMENTED'];
  const summary=Object.freeze({...prior.public_summary,schema:'bsre-coupled-public-summary-v2',profile:CONTRACT_V2.profile,
    status:!g4Selected?'PARTIAL_HELD_G4_DERIVATION_REQUIRED':missing.length?'PARTIAL_HELD':'STRUCTURAL_HELD',
    composition_contract_version:2,engineering_scope_changed:false,g3_base_files_independently_verified:41,g4_before_contact_verified:g4Selected,
    runtime_child_profile:g4Selected?'EXPLICIT_PINNED_G4_DERIVED_CHILD':'G4_DERIVATION_REQUIRED',output_count:files.size,
    required_output_count:CONTRACT_V2.required_outputs.length,missing_selected_outputs:Object.freeze(missing),unmet_composition_dependencies:Object.freeze(unmet),
    holds:Object.freeze([...new Set(holds)]),complete_profile_certified:false,deployment_prohibited:true});
  const publicSummary=Object.freeze({...summary,capture_guard_review_policy:compatibility.proof?'EXPLICIT_CAPTURE_ONLY_COMMENT_VIEW':'STRICT_CONSTANT_ONLY',
    actual_captured_bytes:compatibility.proof?.actual_raw_bytes??null,derived_compatibility_view_bytes:compatibility.proof?.compatibility_view_bytes??null,
    capture_guard_comment_delta_bytes:compatibility.proof?.comment_delta_bytes??0,actual_capture_preserved:true});
  return{files,public_summary:publicSummary,private_manifest:{...prior.private_manifest,schema:'bsre-coupled-private-manifest-v2',summary:publicSummary,
    capture_guard_compatibility:compatibility.proof,
    g3_base:{source_manifest_sha256:G3_SOURCE_MANIFEST_SHA256,manifest_sha256:digest(input.g3_base_manifest_bytes),independently_derived:true,
      members:[...supplied].map(([path,bytes])=>({path,sha256:digest(bytes)}))},
    g4_composition:{selected:g4Selected,source_manifest_sha256:G4_SOURCE_MANIFEST_SHA256,manifest_sha256:g4ManifestHash,stages},
    selected_input_hashes:{...(input.selected_output_pins||{})},outputs:[...files].map(([path,bytes])=>({path,bytes:bytes.length,sha256:digest(bytes)}))}};
}
export async function composeCoupledPackageV2(input){try{return await compose(input);}catch(error){throw new Error(typeof error?.message==='string'&&/^[A-Z][A-Z0-9_]{0,96}$/.test(error.message)?error.message:'V2_INPUT_OR_DERIVATION_FAILED');}}
