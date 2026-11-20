import {readFileSync} from 'node:fs';
import {createHash} from 'node:crypto';
import {buildG34ProfileCandidate} from '../tracking-system/build-g34-profile-candidate.mjs';
import {buildG5RuntimeCandidate} from '../g5-runtime-ports/build-candidate.mjs';
import {buildCanonicalCaptureProducer,verifyCanonicalProducerSources} from './build-canonical-capture-producer.mjs';
export const sha256=value=>createHash('sha256').update(value).digest('hex');
const producerPath='includes/candidate/runtime/CanonicalCaptureProducer.php';
const manifestPath='includes/candidate/runtime/canonical-source.json';
const DROPIN_TEMPLATE_SHA256='ce8ab6c83445efdbdb126a5927e93162cc7b81ea8f877ba03504997fa92f9cb9';
const include=Buffer.from("\n// Explicit G35 code guard only; no operational authority or activation.\nrequire_once __DIR__.'/"+producerPath+"';\n");
function once(text,marker,value){if(text.split(marker).length!==2)throw new Error('CANONICAL_TEMPLATE_ANCHOR_CHANGED');return text.replace(marker,value);}
export function buildCanonicalLeaseCandidate(auditBytes){
  const base=buildG34ProfileCandidate(auditBytes),files=new Map(base.files.map(row=>[row.path,Buffer.from(row.content_base64,'base64')]));
  const partial=buildG5RuntimeCandidate();
  for(const [path,bytes]of Object.entries(partial.outputs)){
    const relative=path.replace(/^plugin\//,'');if(relative===path||files.has(relative))throw new Error('CANONICAL_DUPLICATE_PATH');
    files.set(relative,bytes);
  }
  if(files.size!==55)throw new Error('CANONICAL_BASE_SET_CHANGED');
  const main=files.get('bsre-enquiries.php');
  if(/\?>\s*$/.test(main.toString('utf8')))throw new Error('CANONICAL_MAIN_CLOSING_TAG');
  const next=Buffer.concat([main,include]);
  if(!next.subarray(0,-include.length).equals(main)||!next.subarray(-include.length).equals(include))throw new Error('CANONICAL_MAIN_REVERSE_FAILED');
  files.set('bsre-enquiries.php',next);
  const sourceManifest={schema:'bsre-canonical-lease-source-v1',profile:'G35_CANONICAL_LEASE_CODE_ONLY',
    files:Object.fromEntries([...files].sort(([a],[b])=>a.localeCompare(b)).map(([path,bytes])=>[path,sha256(bytes)])),deployment_prohibited:true};
  const manifest=Buffer.from(JSON.stringify(sourceManifest,null,2)+'\n'),manifestHash=sha256(manifest);
  verifyCanonicalProducerSources(manifest,path=>files.get(path));
  const rendered=buildCanonicalCaptureProducer(manifest),producer=rendered.producer,producerHash=rendered.producer_sha256;
  if(rendered.manifest_sha256!==manifestHash||producerHash!==sha256(producer))throw new Error('CANONICAL_PRODUCER_DERIVATION_CHANGED');
  files.set(producerPath,producer);files.set(manifestPath,manifest);
  const dropinBytes=readFileSync(new URL('./db.php',import.meta.url));
  if(sha256(dropinBytes)!==DROPIN_TEMPLATE_SHA256)throw new Error('CANONICAL_DROPIN_TEMPLATE_CHANGED');
  let dropin=dropinBytes.toString('utf8');
  for(const [marker,value]of [['__BSRE_CODE_MANIFEST_SHA256__',manifestHash],['__BSRE_BOUND_MANIFEST_SHA256__',manifestHash],
    ['__BSRE_PRODUCER_SHA256__',producerHash],['__BSRE_BOUND_PRODUCER_SHA256__',producerHash]])dropin=once(dropin,marker,value);
  const site=new Map([...files].map(([path,bytes])=>['wp-content/plugins/bsre-enquiries/'+path,bytes]));site.set('wp-content/db.php',Buffer.from(dropin));
  return Object.freeze({profile:'G35_CANONICAL_LEASE_CODE_ONLY',status:'HELD',deployment_prohibited:true,production_authorized:false,
    full_profile_complete:false,provider_accepted:false,default_enabled:false,source_manifest_sha256:manifestHash,producer_sha256:producerHash,
    files:Object.freeze([...site].sort(([a],[b])=>a.localeCompare(b)).map(([path,bytes])=>Object.freeze({path,sha256:sha256(bytes),content_base64:bytes.toString('base64')})))});
}
