/** Fixed synthetic native readback. No WordPress, database, network or writes. */
import {readFileSync,lstatSync,realpathSync,existsSync} from 'node:fs';
import {join,resolve} from 'node:path';
import {createHash} from 'node:crypto';
import {pathToFileURL} from 'node:url';
const need=(ok,code)=>{if(!ok)throw new Error(code);};
const hash=raw=>createHash('sha256').update(raw).digest('hex');
export const PHASE='current_g36_physical_identity';
export const PROFILE='G36_COUPLED_CANONICAL_LEASE_V3';
export const BASE='wp-content/plugins/bsre-enquiries/';
export const FOUR=[BASE+'assets/google-runtime.js',BASE+'includes/candidate/runtime/CanonicalCaptureProducer.php',
  BASE+'includes/candidate/runtime/canonical-source.json','wp-content/db.php'];
export const CONTEXT_DESCRIPTOR='/opt/lab/website-tracking/g5-local-history-runtime/CURRENT_INPUT_CONTEXT.json';
export const CONTEXT_ALIAS='/opt/lab/g39-inputs/tools/qualified-export-source/source_queue.py';
const pin=raw=>({bytes:raw.length,sha256:hash(raw)});
function regular(root,path){
  need(typeof path==='string'&&/^[A-Za-z0-9_./-]+$/.test(path)&&!path.startsWith('/')&&path.split('/').every(p=>p&&p!=='.'&&p!=='..'),'CURRENT_IDENTITY_PATH');
  let at=resolve(root);need(realpathSync(at)===at&&lstatSync(at).isDirectory()&&!lstatSync(at).isSymbolicLink(),'CURRENT_IDENTITY_ROOT');
  for(const part of path.split('/')){at=join(at,part);need(!lstatSync(at).isSymbolicLink(),'CURRENT_IDENTITY_SYMLINK');}
  need(lstatSync(at).isFile()&&lstatSync(at).size<=1048576,'CURRENT_IDENTITY_REGULAR_BOUND');
  return readFileSync(at);
}
export function physicalIdentity(root,{context=null}={}){
  const build=regular(root,'BUILD.json'),nativeBuild=regular(root,'NATIVE_BUILD.json');
  const descriptor=JSON.parse(build),native=JSON.parse(nativeBuild);
  need(descriptor.profile===PROFILE&&Array.isArray(descriptor.files)&&descriptor.files.length===67,'CURRENT_IDENTITY_SITE67');
  need(new Set(descriptor.files.map(row=>row.path)).size===67,'CURRENT_IDENTITY_DUPLICATE_SITE_PATH');
  const files=new Map();
  for(const row of descriptor.files){const raw=regular(root,row.path);need(hash(raw)===row.sha256,'CURRENT_IDENTITY_SITE_HASH');files.set(row.path,raw);}
  need(FOUR.every(path=>files.has(path)),'CURRENT_IDENTITY_FOUR_FILES');
  const manifest=JSON.parse(files.get(FOUR[2]));
  need(manifest.profile===PROFILE&&manifest.schema==='bsre-canonical-lease-source-v1'&&manifest.deployment_prohibited===true&&Object.keys(manifest.files).length===64,'CURRENT_IDENTITY_SOURCE64');
  for(const [path,digest]of Object.entries(manifest.files))need(files.has(BASE+path)&&hash(files.get(BASE+path))===digest,'CURRENT_IDENTITY_SOURCE_HASH');
  const M=hash(files.get(FOUR[2])),P=hash(files.get(FOUR[1])),dropin=hash(files.get(FOUR[3]));
  need(native.profile===PROFILE&&native.site_files===67&&native.source_members===64&&native.synthetic_only===true&&native.deployment_prohibited===true
    &&native.source_bindings.M===M&&native.source_bindings.P===P&&native.source_bindings.dropin_sha256===dropin,'CURRENT_IDENTITY_NATIVE_BINDINGS');
  const guard="!/^(?:bsre-event-|evt_)[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/.test(payload.transaction_id)";
  need(files.get(FOUR[0]).toString('utf8').split(guard).length===2,'CURRENT_IDENTITY_OPAQUE_ADS_GUARD');
  return {schema:'bsre-current-g36-physical-identity-v1',phase:PHASE,profile:PROFILE,site_files:67,source_members:64,
    files:Object.fromEntries(FOUR.map(path=>[path,pin(files.get(path))])),build:pin(build),native_build:pin(nativeBuild),
    bindings:{M,P,dropin_sha256:dropin},retention_context:context,
    all_site_files_readback_verified:true,all_manifest_sources_readback_verified:true,
    synthetic_only:true,wordpress_started_by_receipt:false,database_started_by_receipt:false,network_calls:0,provider_events:0,production_authorized:false};
}
if(process.argv[1]&&import.meta.url===pathToFileURL(process.argv[1]).href){
  need(process.argv.length===2,'CURRENT_IDENTITY_FIXED_CLI_ONLY');
  let context=null;
  if(existsSync(CONTEXT_DESCRIPTOR)){
    for(const path of [CONTEXT_DESCRIPTOR,CONTEXT_ALIAS])need(lstatSync(path).isFile()&&!lstatSync(path).isSymbolicLink(),'CURRENT_CONTEXT_REGULAR');
    context={descriptor:pin(readFileSync(CONTEXT_DESCRIPTOR)),source_queue_alias:pin(readFileSync(CONTEXT_ALIAS))};
  }
  console.log(JSON.stringify(physicalIdentity('/opt/lab/g36',{context})));
}
