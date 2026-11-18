/** Compile reviewed current inputs into hashes only. No retained packets or file writes. */
import {readFileSync} from 'node:fs';
import {resolve,join} from 'node:path';
import {pathToFileURL} from 'node:url';
import {createHash} from 'node:crypto';
const hash=raw=>createHash('sha256').update(raw).digest('hex');
const pin=raw=>({bytes:raw.length,sha256:hash(raw)});
const need=(ok,code)=>{if(!ok)throw new Error(code);};
const [sourceArg,scopeArg,composerArg]=process.argv.slice(2);
need(sourceArg&&scopeArg,'CURRENT_DERIVATION_ARGUMENTS');
const source=resolve(sourceArg),scope=JSON.parse(readFileSync(scopeArg,'utf8'));
const composer=resolve(composerArg||join(source,scope.composer.path));
need(JSON.stringify(pin(readFileSync(composer)))===JSON.stringify(scope.composer.after),'CURRENT_COMPOSER_PIN');
const {syntheticInput}=await import(pathToFileURL(join(source,'tools/website-tracking/coupled-package-v3/synthetic-input.mjs')));
const {composeCoupledCanonicalLeaseV3}=await import(pathToFileURL(composer));
const {buildG36Native}=await import(pathToFileURL(join(source,'tools/website-tracking/coupled-package-v3/build-native.mjs')));
const result=await composeCoupledCanonicalLeaseV3(await syntheticInput({source_root:source})),native=await buildG36Native({source_root:source});
const site=[...result.files].filter(([path])=>path.startsWith('site/')).map(([path,raw])=>[path.slice(5),raw]);
need(site.length===67&&result.files.size===68,'CURRENT_DERIVATION_COUNTS');
const build=Buffer.from(JSON.stringify({profile:result.public_summary.profile,files:[...site].sort(([a],[b])=>a.localeCompare(b)).map(([path,raw])=>({path,sha256:hash(raw)}))},null,2)+'\n');
const nativeBuild=Buffer.from(JSON.stringify({schema:'bsre-g36-native-derivation-v1',profile:result.public_summary.profile,
  synthetic_only:true,deployment_prohibited:true,source_bindings:result.private_manifest.bindings,site_files:67,source_members:64,
  inherited_checks:native.inherited_checks,receipts:native.receipts,runtime_checks_executed:false,
  contact_modes:['hub','off-plan','resale','rent','sell','let']},null,2)+'\n');
const base='wp-content/plugins/bsre-enquiries/',four=[base+'assets/google-runtime.js',base+'includes/candidate/runtime/CanonicalCaptureProducer.php',base+'includes/candidate/runtime/canonical-source.json','wp-content/db.php'];
const files=new Map(site),bindings=result.private_manifest.bindings;
const context=scope.retention_context?{descriptor:pin(readFileSync(join(source,scope.retention_context.descriptor_source))),source_queue_alias:pin(readFileSync(join(source,scope.retention_context.queue_source)))}:null;
const expected={schema:'bsre-current-g36-physical-identity-v1',phase:'current_g36_physical_identity',profile:bindings.profile,site_files:67,source_members:64,
  files:Object.fromEntries(four.map(path=>[path,pin(files.get(path))])),build:pin(build),native_build:pin(nativeBuild),
  bindings:{M:bindings.M,P:bindings.P,dropin_sha256:bindings.dropin_sha256},retention_context:context,
  all_site_files_readback_verified:true,all_manifest_sources_readback_verified:true,synthetic_only:true,
  wordpress_started_by_receipt:false,database_started_by_receipt:false,network_calls:0,provider_events:0,production_authorized:false};
console.log(JSON.stringify({scope:'DERIVED_HASHES_ONLY_NOT_NATIVE_ACCEPTANCE',expected_receipt:expected,
  composer:pin(readFileSync(composer)),guard:result.private_manifest.ads_transaction_id_guard,
  input_manifest_sha256:result.private_manifest.source_pin_manifest_sha256,
  receiver:pin(result.files.get('companion/receiver/Code.gs'))}));
