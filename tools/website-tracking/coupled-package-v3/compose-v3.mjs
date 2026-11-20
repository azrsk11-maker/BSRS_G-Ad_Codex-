/** Fixed G36 offline composition. No installer, source override, provider or release authority. */
import {readFileSync,lstatSync,realpathSync} from 'node:fs';
import {resolve,relative,isAbsolute,join,sep} from 'node:path';
import {pathToFileURL} from 'node:url';
import {createHash} from 'node:crypto';
export const digest=bytes=>createHash('sha256').update(bytes).digest('hex');
const need=(ok,code)=>{if(!ok)throw new Error(code);};
const contractBytes=readFileSync(new URL('./profile-contract-v3.json',import.meta.url));
const pinBytes=readFileSync(new URL('./source-pins-v3.json',import.meta.url));
need(digest(contractBytes)==='99e5fabd1793d71ac0522d413111d6f34f0f39c2dbeba79e82e6c541fe19441f','V3_CONTRACT_CHANGED');
need(digest(pinBytes)==='9d13a6ee815dd81be7ee53076c437284f9299e27294e00b25277ee7f229d142b','V3_SOURCE_PIN_MANIFEST_CHANGED');
const contract=JSON.parse(contractBytes),pins=JSON.parse(pinBytes);
Object.freeze(pins.files);Object.freeze(pins);
for(const value of Object.values(contract))if(value&&typeof value==='object')Object.freeze(value);
export const CONTRACT_V3=Object.freeze(contract);
const V2='tools/website-tracking/coupled-package/';
const G35='tools/website-tracking/canonical-lease/';
const TRACKING='tools/website-tracking/tracking-system/';
const MAIN_SUFFIX=Buffer.from("\n// Explicit G35 code guard only; no operational authority or activation.\nrequire_once __DIR__.'/includes/candidate/runtime/CanonicalCaptureProducer.php';\n");
const genuineResults=new WeakMap();
// Caller-owned Maps, Buffers and metadata remain reviewable. Authority is held only in
// these unexposed immutable digests, registered after every final composition mutation.
function metadataJSON(value){
  const active=new Set();let nodes=0;
  function encode(item,depth){
    need(++nodes<=100000&&depth<=64,'V3_METADATA_BOUND');
    if(item===null||typeof item==='string'||typeof item==='boolean')return JSON.stringify(item);
    if(typeof item==='number'){need(Number.isFinite(item),'V3_METADATA_VALUE');return JSON.stringify(item);}
    need(item&&typeof item==='object'&&!active.has(item),'V3_METADATA_VALUE');active.add(item);
    const array=Array.isArray(item),proto=Object.getPrototypeOf(item),keys=Reflect.ownKeys(item);
    need(array?proto===Array.prototype:proto===Object.prototype||proto===null,'V3_METADATA_OBJECT');
    let text;
    if(array){
      need(keys.length===item.length+1&&keys.at(-1)==='length','V3_METADATA_ARRAY');const values=[];
      for(let i=0;i<item.length;i++){
        const d=Object.getOwnPropertyDescriptor(item,String(i));need(d&&Object.hasOwn(d,'value')&&d.enumerable,'V3_METADATA_DATA_REQUIRED');values.push(encode(d.value,depth+1));
      }
      text='['+values.join(',')+']';
    }else{
      const values=[];for(const key of keys){
        const d=Object.getOwnPropertyDescriptor(item,key);need(typeof key==='string'&&d&&Object.hasOwn(d,'value')&&d.enumerable,'V3_METADATA_DATA_REQUIRED');
        values.push(JSON.stringify(key)+':'+encode(d.value,depth+1));
      }
      text='{'+values.join(',')+'}';
    }
    active.delete(item);return text;
  }
  return encode(value,0);
}
function resultSnapshot(result,source){
  need(result&&Object.getPrototypeOf(result)===Object.prototype&&Reflect.ownKeys(result).sort().join(',')==='files,private_manifest,public_summary','V3_RESULT_DATA_REQUIRED');
  const data={};for(const key of ['files','public_summary','private_manifest']){
    const d=Object.getOwnPropertyDescriptor(result,key);need(d&&Object.hasOwn(d,'value')&&d.enumerable,'V3_RESULT_DATA_REQUIRED');data[key]=d.value;
  }
  need(data.files instanceof Map&&Object.getPrototypeOf(data.files)===Map.prototype&&Reflect.ownKeys(data.files).length===0,'V3_RESULT_MAP_REQUIRED');
  const files=[];for(const [path,bytes]of Map.prototype.entries.call(data.files)){
    need(Buffer.isBuffer(bytes),'V3_OUTPUT_BYTES');files.push(Object.freeze({path,bytes:bytes.length,sha256:digest(bytes)}));
  }
  const publicJSON=metadataJSON(data.public_summary),privateJSON=metadataJSON(data.private_manifest);
  return Object.freeze({source_root:source,files:Object.freeze(files),public_json:publicJSON,private_json:privateJSON,
    public_sha256:digest(publicJSON),private_sha256:digest(privateJSON)});
}
function assertGenuineResult(result){
  const expected=genuineResults.get(result);need(expected,'V3_GENUINE_COMPOSE_RESULT_REQUIRED');
  const actual=resultSnapshot(result,expected.source_root);
  need(JSON.stringify(actual.files)===JSON.stringify(expected.files)&&actual.public_sha256===expected.public_sha256&&actual.private_sha256===expected.private_sha256,'V3_COMPOSE_RESULT_MUTATED');
  return expected;
}
const V2_INPUT_FIELDS=['source_root','original','captured','identity','provenance','original_zip_bytes','receiver_original','capture_binding','native_binding',
  'g3_base_manifest_bytes','g3_selection_receipt','g4_source_root','g4_manifest_bytes','g4_selection_receipt','capture_guard_comment_review'];
const safeError=error=>new Error(typeof error?.message==='string'&&/^[A-Z][A-Z0-9_]{0,96}$/.test(error.message)?error.message:'V3_INPUT_OR_DERIVATION_FAILED');
function safePath(path){need(typeof path==='string'&&path.length>0&&path.length<=240&&/^[A-Za-z0-9_.\/-]+$/.test(path)&&!path.startsWith('/')&&
  path.split('/').every(p=>p&&p!=='.'&&p!=='..'),'V3_UNSAFE_PATH');return path;}
function pinned(root,path){
  safePath(path);need(Object.hasOwn(pins.files,path),'V3_UNSELECTED_SOURCE');
  const base=resolve(root),file=resolve(base,path),rel=relative(base,file);
  need(rel!=='..'&&!rel.startsWith('..'+sep)&&!isAbsolute(rel)&&realpathSync(base).toLowerCase()===base.toLowerCase()&&!lstatSync(base).isSymbolicLink(),'V3_SOURCE_ROOT');
  let cursor=base;for(const part of rel.split(sep)){cursor=join(cursor,part);need(!lstatSync(cursor).isSymbolicLink(),'V3_SOURCE_LINK');}
  const stat=lstatSync(file);need(stat.isFile()&&stat.size>0&&stat.size<=2097152,'V3_SOURCE_SIZE');
  const bytes=readFileSync(file);need(digest(bytes)===pins.files[path],'V3_SOURCE_PIN_CHANGED');return {file,bytes};
}
function verifySources(root){for(const path of Object.keys(pins.files))pinned(root,path);}
function exactEntries(files,names){
  need(files instanceof Map&&files.size===names.length&&names.every(p=>files.has(p)),'V3_OUTPUT_SET');
  let total=0;for(const [path,bytes]of files){safePath(path);need(Buffer.isBuffer(bytes)&&bytes.length>0&&bytes.length<=2097152,'V3_OUTPUT_BYTES');total+=bytes.length;}
  need(total<=16777216,'V3_OUTPUT_TOTAL_SIZE');
}
function change(text,before,after,kind,edits){
  need(text.split(before).length===2,'V3_TEMPLATE_ANCHOR');const offset=Buffer.byteLength(text.slice(0,text.indexOf(before)));
  edits.push({before,after,kind,offset});return text.replace(before,after);
}
function reverse(text,edits){let value=Buffer.from(text);for(const edit of [...edits].reverse()){
  const after=Buffer.from(edit.after);need(value.subarray(edit.offset,edit.offset+after.length).equals(after),'V3_REVERSE_ANCHOR');
  value=Buffer.concat([value.subarray(0,edit.offset),Buffer.from(edit.before),value.subarray(edit.offset+after.length)]);}return value.toString('utf8');}
const spans=edits=>edits.map(e=>({kind:e.kind,offset:e.offset,removed_bytes:Buffer.byteLength(e.before),added_bytes:Buffer.byteLength(e.after),
  before_sha256:digest(e.before),after_sha256:digest(e.after)}));
async function domainOutputs(root){
  const {buildG5RuntimeCandidate}=await import(pathToFileURL(pinned(root,'tools/website-tracking/g5-runtime-ports/build-candidate.mjs').file).href);
  const g5=buildG5RuntimeCandidate();need(g5.manifest.output_count===13&&Object.keys(g5.outputs).length===13,'V3_G5_OUTPUT_COUNT');
  const files=new Map(Object.entries(g5.outputs).map(([path,bytes])=>[path,Buffer.from(bytes)]));
  const proof=[...files].map(([path,bytes])=>({path,derivation:'PINNED_G5_RUNTIME_BUILDER',output_sha256:digest(bytes)}));
  for(const name of ['Cleanup.php','OwnerClosure.php','OwnerCollection.php','OwnerMailReview.php','OwnerRetirement.php','WordPress.php']){
    const source='tools/owner-mail-review/'+name,bytes=pinned(root,source).bytes,path='plugin/includes/candidate/owner-mail-review/'+name;
    files.set(path,bytes);proof.push({path,source,derivation:'EXACT_PINNED_DOMAIN_SOURCE',output_sha256:digest(bytes)});
  }
  const {buildPurposeRetention}=await import(pathToFileURL(pinned(root,TRACKING+'build-purpose-retention-candidate.mjs').file).href);
  const helper=pinned(root,TRACKING+'purpose-retention.php').bytes;files.set('plugin/includes/candidate/purpose-retention/purpose-retention.php',helper);
  proof.push({path:'plugin/includes/candidate/purpose-retention/purpose-retention.php',derivation:'EXACT_PINNED_PURPOSE_HELPER',output_sha256:digest(helper)});
  for(const name of ['PreferenceRetirement','RetirementLedger']){
    const original=pinned(root,'tools/consent-retention/'+name+'.php').bytes,intermediate=buildPurposeRetention(original,name),edits=[];
    let output=intermediate;
    if(name==='PreferenceRetirement')for(const [before,after]of [
      ["require_once '/opt/lab/consent-retention/RetentionInventory.php';","require_once __DIR__ . '/../consent-retention/RetentionInventory.php';"],
      ["require_once '/opt/lab/purpose-retention/purpose-retention.php';","require_once __DIR__ . '/purpose-retention.php';"]])
      output=change(output,before,after,'EXACT_REQUIRE_RELOCATION',edits);
    need(reverse(output,edits)===intermediate,'V3_PURPOSE_RELOCATION_REVERSE');
    const path='plugin/includes/candidate/purpose-retention/'+name+'.php';files.set(path,Buffer.from(output));
    proof.push({path,derivation:'PINNED_PURPOSE_RETENTION_THEN_EXACT_RELOCATION',original_sha256:digest(original),intermediate_sha256:digest(intermediate),
      output_sha256:digest(output),ordered_edits:spans(edits),reverse_verified:true,lab_authority_guards_preserved:true});
  }
  need(files.size===22,'V3_SELECTED_DOMAIN_SET');return {files,proof};
}
function renderBindings(root,manifestBytes){
  const manifest=JSON.parse(manifestBytes);
  need(Object.keys(manifest).sort().join(',')==='deployment_prohibited,files,profile,schema'&&manifest.schema===CONTRACT_V3.runtime_manifest_schema&&
    manifest.profile===CONTRACT_V3.profile&&manifest.deployment_prohibited===true&&Object.keys(manifest.files).length===64,'V3_MANIFEST_SHAPE');
  const originalProducer=pinned(root,G35+'CanonicalCaptureProducer.template.php').bytes,originalDropin=pinned(root,G35+'db.php').bytes;
  const profileEdits=[],dropinEdits=[];let producerTemplate=originalProducer.toString('utf8'),dropinTemplate=originalDropin.toString('utf8');
  producerTemplate=change(producerTemplate,"MANIFEST_PROFILE='G35_CANONICAL_LEASE_CODE_ONLY'","MANIFEST_PROFILE='G36_COUPLED_CANONICAL_LEASE_V3'",'FIXED_G35_TO_G36_PROFILE',profileEdits);
  producerTemplate=change(producerTemplate,"count($manifest['files'])!==55","count($manifest['files'])!==64",'FIXED_55_TO_64_MEMBER_COUNT',profileEdits);
  dropinTemplate=change(dropinTemplate,"$bsreManifest['profile'] !== 'G35_CANONICAL_LEASE_CODE_ONLY'","$bsreManifest['profile'] !== 'G36_COUPLED_CANONICAL_LEASE_V3'",'FIXED_G35_TO_G36_PROFILE',dropinEdits);
  dropinTemplate=change(dropinTemplate,"count($bsreManifest['files']) !== 55","count($bsreManifest['files']) !== 64",'FIXED_55_TO_64_MEMBER_COUNT',dropinEdits);
  need(Buffer.from(reverse(producerTemplate,profileEdits)).equals(originalProducer)&&Buffer.from(reverse(dropinTemplate,dropinEdits)).equals(originalDropin),'V3_PROFILE_COUNT_REVERSE');
  const M=digest(manifestBytes),producerBindings=[];
  const producer=Buffer.from(change(producerTemplate,'__BSRE_CODE_MANIFEST_SHA256__',M,'EXACT_SOURCE_MANIFEST_DIGEST',producerBindings)),P=digest(producer);
  const dropinBindings=[];let dropin=dropinTemplate;
  for(const [marker,value]of [['__BSRE_CODE_MANIFEST_SHA256__',M],['__BSRE_BOUND_MANIFEST_SHA256__',M],['__BSRE_PRODUCER_SHA256__',P],['__BSRE_BOUND_PRODUCER_SHA256__',P]])
    dropin=change(dropin,marker,value,'EXACT_M_P_BINDING',dropinBindings);
  need(reverse(producer.toString(),producerBindings)===producerTemplate&&reverse(dropin,dropinBindings)===dropinTemplate,'V3_BINDING_REVERSE');
  const coreStart='    private function noInterceptors(): void',coreEnd='    /** Inspection only:';
  const core=value=>value.slice(value.indexOf(coreStart),value.indexOf(coreEnd));
  need(core(originalProducer.toString())===core(producer.toString()),'V3_CORE_WHITELIST_CHANGED');
  return {producer,dropin:Buffer.from(dropin),M,P,proof:{
    accepted_producer_template_sha256:digest(originalProducer),accepted_dropin_template_sha256:digest(originalDropin),
    profile_count_edits:{producer:spans(profileEdits),dropin:spans(dropinEdits)},hash_binding_edits:{producer:spans(producerBindings),dropin:spans(dropinBindings)},
    producer_template_v3_sha256:digest(producerTemplate),dropin_template_v3_sha256:digest(dropinTemplate),
    all_template_bytes_reverse_to_accepted_G35:true,core_query_whitelist_sha256:digest(core(producer.toString())),core_query_whitelist_byte_identical:true}};
}
async function compose(input){
  need(input&&typeof input==='object'&&Object.keys(input).sort().join(',')==='source_root,v2_input','V3_CLOSED_INPUT_SHAPE');
  const root=resolve(input.source_root),v2input=input.v2_input;
  need(v2input&&typeof v2input==='object'&&Object.keys(v2input).every(k=>V2_INPUT_FIELDS.includes(k)),'V3_EXTERNAL_SOURCE_OVERRIDE_FORBIDDEN');
  need(typeof v2input.source_root==='string'&&typeof v2input.g4_source_root==='string'&&resolve(v2input.source_root)===root&&resolve(v2input.g4_source_root)===root,'V3_SHARED_SOURCE_ROOT_REQUIRED');
  need(v2input.g4_manifest_bytes&&v2input.g4_selection_receipt,'V3_G4_SELECTION_REQUIRED');verifySources(root);
  const selected=await domainOutputs(root);
  const {composeCoupledPackageV2}=await import(pathToFileURL(pinned(root,V2+'compose-v2.mjs').file).href);
  const v2=await composeCoupledPackageV2({...v2input,selected_outputs:[...selected.files].map(([path,bytes])=>({path,bytes})),
    selected_output_pins:Object.fromEntries([...selected.files].map(([path,bytes])=>[path,digest(bytes)]))});
  need(v2.public_summary.profile===CONTRACT_V3.closed_v2_profile&&v2.files.size===65&&v2.public_summary.required_output_count===67&&
    v2.public_summary.complete_profile_certified===false&&v2.public_summary.deployment_prohibited===true&&v2.public_summary.g4_before_contact_verified===true,'V3_V2_PROFILE_UNREADY');
  const requiredV2=JSON.parse(pinned(root,V2+'profile-contract-v2.json').bytes);
  const missingV2=requiredV2.g5_hard_unimplemented;
  need(v2.public_summary.missing_selected_outputs.length===2&&missingV2.every(p=>v2.public_summary.missing_selected_outputs.includes(p)),'V3_ONLY_TWO_REAL_PORTS_MAY_BE_MISSING');
  const sourceMembers=new Map([...v2.files].filter(([p])=>p.startsWith('plugin/')).map(([p,b])=>[p.slice(7),Buffer.from(b)]));need(sourceMembers.size===64,'V3_FINAL_PLUGIN_64_REQUIRED');
  const mainBefore=sourceMembers.get('bsre-enquiries.php');need(mainBefore&&!/\?>\s*$/.test(mainBefore.toString()),'V3_MAIN_CLOSING_TAG');
  const main=Buffer.concat([mainBefore,MAIN_SUFFIX]);need(main.subarray(0,-MAIN_SUFFIX.length).equals(mainBefore)&&main.subarray(-MAIN_SUFFIX.length).equals(MAIN_SUFFIX),'V3_MAIN_INCLUDE_REVERSE');
  sourceMembers.set('bsre-enquiries.php',main);
  // Independent actual G35 source builder proves the critical55 member set and unchanged guards.
  const {buildCanonicalLeaseCandidate}=await import(pathToFileURL(pinned(root,G35+'build-candidate.mjs').file).href);
  const accepted=buildCanonicalLeaseCandidate(pinned(root,'docs/audit/INSTALLED_SOURCE_COMPARISON_2026-11-07.json').bytes);
  const oldFiles=new Map(accepted.files.map(row=>[row.path,Buffer.from(row.content_base64,'base64')]));
  const oldPrefix='wp-content/plugins/bsre-enquiries/',oldManifest=JSON.parse(oldFiles.get(oldPrefix+'includes/candidate/runtime/canonical-source.json'));
  need(Object.keys(oldManifest.files).length===55,'V3_G35_CRITICAL_SET_CHANGED');
  const contactPaths=new Set(v2.private_manifest.ancestry.map(row=>row.member));need(contactPaths.size===8,'V3_CONTACT_ANCESTRY_REQUIRED');
  for(const path of Object.keys(oldManifest.files)){
    need(sourceMembers.has(path),'V3_DROPPED_CRITICAL_SOURCE');const old=oldFiles.get(oldPrefix+path);need(old&&digest(old)===oldManifest.files[path],'V3_G35_CRITICAL_SOURCE_CHANGED');
    if(!contactPaths.has(path))need(sourceMembers.get(path).equals(old),'V3_UNREVIEWED_CRITICAL_SOURCE_CHANGE');
    else {const proof=v2.private_manifest.ancestry.find(row=>row.member===path);
      need(proof.reverse_verified===true&&(path==='assets/lead.js'?proof.precontact_sha256:proof.original_sha256)===digest(old),'V3_CONTACT_BASELINE_ANCESTRY_CHANGED');}
  }
  const added=[...sourceMembers.keys()].filter(p=>!Object.hasOwn(oldManifest.files,p));
  const nine=[...['Cleanup.php','OwnerClosure.php','OwnerCollection.php','OwnerMailReview.php','OwnerRetirement.php','WordPress.php'].map(n=>'includes/candidate/owner-mail-review/'+n),
    ...['PreferenceRetirement.php','RetirementLedger.php','purpose-retention.php'].map(n=>'includes/candidate/purpose-retention/'+n)];
  need(added.length===9&&nine.every(p=>added.includes(p)),'V3_EXTRA_SOURCE_NINE_SET');
  // The accepted receipt guard allows generic opaque-looking strings. Do not
  // disclose a phone-like or free-text value as an Ads transaction identifier.
  // Tighten only the final selected child after proving its unchanged ancestry;
  // original runtime/G4/V2 bytes and their frozen source pins remain intact.
  const childPath='assets/google-runtime.js',childBefore=sourceMembers.get(childPath);
  const broadId="!/^[A-Za-z0-9._:-]{1,64}$/.test(payload.transaction_id)";
  const opaqueId="!/^(?:bsre-event-|evt_)[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/.test(payload.transaction_id)";
  const childText=childBefore.toString('utf8');need(childText.split(broadId).length===2,'V3_ADS_ID_GUARD_ANCHOR');
  const childAfter=Buffer.from(childText.replace(broadId,opaqueId));
  need(childAfter.toString().split(opaqueId).length===2&&Buffer.from(childAfter.toString().replace(opaqueId,broadId)).equals(childBefore),'V3_ADS_ID_GUARD_REVERSE');
  sourceMembers.set(childPath,childAfter);
  const adsIdGuard={member:childPath,input_sha256:digest(childBefore),output_sha256:digest(childAfter),
    before:broadId,after:opaqueId,reverse_verified:true,invalid_id_policy:'DROP_OPTIONAL_ADS_DISPATCH_NO_REWRITE'};
  const sourceMap=Object.fromEntries([...sourceMembers].sort(([a],[b])=>a.localeCompare(b)).map(([path,bytes])=>[path,digest(bytes)]));
  const manifest=Buffer.from(JSON.stringify({schema:CONTRACT_V3.runtime_manifest_schema,profile:CONTRACT_V3.profile,files:sourceMap,deployment_prohibited:true},null,2)+'\n');
  const rendered=renderBindings(root,manifest);
  const files=new Map([...sourceMembers].map(([p,b])=>[CONTRACT_V3.plugin_prefix+p,b]));
  files.set(CONTRACT_V3.receiver_path,Buffer.from(v2.files.get(CONTRACT_V3.receiver_path)));
  files.set(CONTRACT_V3.producer_path,rendered.producer);files.set(CONTRACT_V3.manifest_path,manifest);files.set(CONTRACT_V3.dropin_path,rendered.dropin);
  exactEntries(files,CONTRACT_V3.available_paths);verifySources(root);
  const summary=Object.freeze({schema:'bsre-coupled-canonical-public-summary-v3',profile:CONTRACT_V3.profile,status:'STRUCTURAL_68_OF_70_HELD',
    final_source_manifest_members:64,critical_G35_members_preserved:55,additional_selected_domain_members:9,available_outputs:68,required_outputs:70,
    missing_real_ports:Object.freeze([...CONTRACT_V3.known_missing_real_ports]),original_members:30,captured_unchanged:22,captured_reconciled:8,
    actual_capture_preserved:v2.public_summary.actual_capture_preserved,receiver_bytes_preserved:true,main_class_include_reverse_verified:true,
    G35_template_profile_count_reverse_verified:true,G35_core_query_whitelist_preserved:true,complete_profile_certified:false,deployment_prohibited:true,
    default_enabled:false,native_v3_accepted:false,operational_provider_human_or_production_authority:false,network_calls:0,provider_calls:0,live_actions:0,
    holds:Object.freeze([...new Set([...v2.public_summary.holds,...CONTRACT_V3.release_holds])])});
  const result={files,public_summary:summary,private_manifest:{schema:'bsre-coupled-canonical-private-manifest-v3',classification:'PRIVATE_DO_NOT_PUBLISH',summary,
    v2_private_manifest:v2.private_manifest,v2_source_composer_sha256:pins.files[V2+'compose-v2.mjs'],source_pin_manifest_sha256:digest(pinBytes),
    source_files:{...pins.files},selected_domain_derivations:selected.proof,critical_G35_source_members:Object.keys(oldManifest.files),additional_nine_source_members:added,
    ads_transaction_id_guard:adsIdGuard,
    main_include:{input_sha256:digest(mainBefore),output_sha256:digest(main),appended_bytes:MAIN_SUFFIX.length,reverse_verified:true,class_only:true},
    bindings:{M:rendered.M,P:rendered.P,dropin_sha256:digest(rendered.dropin),source_manifest_members:64,profile:CONTRACT_V3.profile},
    template_derivation:rendered.proof,receiver_sha256:digest(files.get(CONTRACT_V3.receiver_path)),
    outputs:[...files].map(([path,bytes])=>({path,bytes:bytes.length,sha256:digest(bytes)}))}};
  assertStructuralCandidate(result);genuineResults.set(result,resultSnapshot(result,realpathSync(root)));return result;
}
/** Source-root provenance is private process state, never a caller supplied certificate. */
export function assertWriterDestinationV3(result,destination){
  assertHeldCandidateV3(result);const source=assertGenuineResult(result).source_root;
  verifySources(source);
  const target=resolve(destination).toLowerCase(),base=source.toLowerCase();
  const within=(a,b)=>{const p=relative(a,b);return p===''||(p!=='..'&&!p.startsWith('..'+sep)&&!isAbsolute(p));};
  need(!within(base,target)&&!within(target,base),'V3_COMPOSE_SOURCE_OVERLAP');return true;
}
function assertStructuralCandidate(result){
  need(result?.public_summary?.profile===CONTRACT_V3.profile&&result.public_summary.complete_profile_certified===false&&
    result.public_summary.deployment_prohibited===true&&result.private_manifest?.classification==='PRIVATE_DO_NOT_PUBLISH','V3_HELD_RESULT_REQUIRED');
  exactEntries(result.files,CONTRACT_V3.available_paths);
  need(result.private_manifest.outputs?.length===68,'V3_PRIVATE_OUTPUT_MANIFEST');
  for(const row of result.private_manifest.outputs)need(result.files.has(row.path)&&digest(result.files.get(row.path))===row.sha256&&result.files.get(row.path).length===row.bytes,'V3_OUTPUT_HASH_CHANGED');
  const manifestBytes=result.files.get(CONTRACT_V3.manifest_path),manifest=JSON.parse(manifestBytes),bindings=result.private_manifest.bindings;
  const sources=CONTRACT_V3.available_paths.filter(p=>p.startsWith(CONTRACT_V3.plugin_prefix)&&![CONTRACT_V3.producer_path,CONTRACT_V3.manifest_path].includes(p));
  need(manifest.schema===CONTRACT_V3.runtime_manifest_schema&&manifest.profile===CONTRACT_V3.profile&&manifest.deployment_prohibited===true&&
    Object.keys(manifest).sort().join(',')==='deployment_prohibited,files,profile,schema'&&Object.keys(manifest.files).length===64&&sources.length===64,'V3_SOURCE_MANIFEST_CLOSED_SET');
  for(const path of sources)need(manifest.files[path.slice(CONTRACT_V3.plugin_prefix.length)]===digest(result.files.get(path)),'V3_FINAL_SOURCE_BINDING_CHANGED');
  need(bindings.M===digest(manifestBytes)&&bindings.P===digest(result.files.get(CONTRACT_V3.producer_path))&&bindings.dropin_sha256===digest(result.files.get(CONTRACT_V3.dropin_path)),'V3_M_P_BINDING_CHANGED');
  return true;
}
export function assertHeldCandidateV3(result){assertStructuralCandidate(result);assertGenuineResult(result);return true;}
/** Final write plan uses detached bytes and original metadata; no caller object is serialized after authorization. */
export function prepareHeldWriteV3(result,destination){
  assertWriterDestinationV3(result,destination);const expected=assertGenuineResult(result),files=new Map();
  for(const row of expected.files){
    const bytes=Buffer.from(Map.prototype.get.call(result.files,row.path));
    need(bytes.length===row.bytes&&digest(bytes)===row.sha256,'V3_COMPOSE_RESULT_MUTATED');files.set(row.path,bytes);
  }
  return {files,public_summary:JSON.parse(expected.public_json),private_manifest:JSON.parse(expected.private_json)};
}
export async function composeCoupledCanonicalLeaseV3(input){try{return await compose(input);}catch(error){throw safeError(error);}}
