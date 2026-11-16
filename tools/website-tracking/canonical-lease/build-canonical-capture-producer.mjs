import {readFileSync} from 'node:fs';
import {createHash} from 'node:crypto';
const sha=bytes=>createHash('sha256').update(bytes).digest('hex');
const TEMPLATE_SHA256='04ba401f8bcaa28f1c36baaf15558a0493bcfb46ad4452743b59f6308cd75e7c';
const MARKER='__BSRE_CODE_MANIFEST_SHA256__';
const SELF='includes/candidate/runtime/CanonicalCaptureProducer.php';
const MANIFEST='includes/candidate/runtime/canonical-source.json';
const required=['bsre-enquiries.php','includes/consent.php','includes/consent-store.php','includes/protocol.php',
 'includes/g2-profile/purpose-store.php','includes/g2-profile/purpose-attribution.php','includes/g2-profile/purpose-intake.php',
 'includes/g2-profile/shared-repository.php','includes/g2-profile/retention-admission.php','includes/g2-profile/receipt-recovery.php','includes/g2-profile/receipt-recovery-wordpress.php',
 'includes/g3-profile/route-context.php','includes/candidate/runtime/G5Contracts.php',
 'includes/candidate/closed-enquiry-retention/Workflow.php','includes/candidate/closed-enquiry-retention/LeaseBoundWpdb.php'];
function manifest(bytes){
 if(!Buffer.isBuffer(bytes)||bytes.length>65536)throw new Error('CANONICAL_MANIFEST_BYTES_REQUIRED');
 let value;try{value=JSON.parse(bytes.toString('utf8'));}catch{throw new Error('CANONICAL_MANIFEST_INVALID');}
 if(!value||Array.isArray(value)||typeof value!=='object'||Object.keys(value).sort().join(',')!=='deployment_prohibited,files,profile,schema'
  ||value.schema!=='bsre-canonical-lease-source-v1'||value.profile!=='G35_CANONICAL_LEASE_CODE_ONLY'||value.deployment_prohibited!==true
  ||!value.files||Array.isArray(value.files)||typeof value.files!=='object'||Object.keys(value.files).length!==55)throw new Error('CANONICAL_MANIFEST_INVALID');
 for(const [path,pin]of Object.entries(value.files))if(!/^[A-Za-z0-9_./-]{1,240}$/.test(path)||path.startsWith('/')||path.split('/').some(p=>['','.','..'].includes(p))
  ||[SELF,MANIFEST].includes(path)||typeof pin!=='string'||!/^[a-f0-9]{64}$/.test(pin))throw new Error('CANONICAL_MANIFEST_PATH_OR_HASH_INVALID');
 if(required.some(p=>!Object.hasOwn(value.files,p)))throw new Error('CANONICAL_MANIFEST_SOURCE_SET_INCOMPLETE');
 return value;
}
/** Build-time verification against actual G34+G5+class-only-main output bytes. No certificate input at runtime. */
export function verifyCanonicalProducerSources(bytes,readMember){
 const value=manifest(bytes);
 if(typeof readMember!=='function')throw new Error('CANONICAL_SOURCE_READER_REQUIRED');
 for(const [path,pin]of Object.entries(value.files)){
  let body;try{body=readMember(path);}catch{throw new Error('CANONICAL_SOURCE_UNAVAILABLE:'+path);}
  if(!Buffer.isBuffer(body)||sha(body)!==pin)throw new Error('CANONICAL_SOURCE_CHANGED:'+path);
 }
 return true;
}
/** Root's G35 builder supplies raw manifest bytes derived from the actual 55 output members. */
export function buildCanonicalCaptureProducer(bytes){
 const value=manifest(bytes),template=readFileSync(new URL('./CanonicalCaptureProducer.template.php',import.meta.url));
 if(sha(template)!==TEMPLATE_SHA256)throw new Error('CANONICAL_PRODUCER_TEMPLATE_CHANGED');
 const text=template.toString('utf8');if(text.split(MARKER).length!==2)throw new Error('CANONICAL_PRODUCER_MARKER_COUNT');
 const digest=sha(bytes),producer=Buffer.from(text.replace(MARKER,digest));
 return Object.freeze({producer,manifest_sha256:digest,producer_sha256:sha(producer),profile:value.profile,
  deployment_prohibited:true,provider_authority:false,operational_retention_accepted:false});
}
