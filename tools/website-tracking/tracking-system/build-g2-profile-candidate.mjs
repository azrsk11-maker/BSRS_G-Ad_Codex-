// Separate inert G2 tree: fixed public originals/dependencies, no caller paths or settings.
import {readFileSync,lstatSync} from 'node:fs';
import {fileURLToPath} from 'node:url';
import {dirname} from 'node:path';
import {createHash} from 'node:crypto';
import {buildG2SharedRepositorySources} from './build-g2-shared-repository-candidate.mjs';
import {buildG1RetentionStoreCandidate} from './build-g1-retention-store-candidate.mjs';
import {buildRetentionAdmissionIntake} from './build-retention-admission-candidate.mjs';
const sha=b=>createHash('sha256').update(b).digest('hex');
const fixture=new URL('../../staging-lab/fixtures/bsre-enquiries/',import.meta.url);
export function buildG2ProfileCandidate(receiptBytes) {
  if(!Buffer.isBuffer(receiptBytes))throw new Error('G2_MAP_BYTES_REQUIRED');
  if(sha(receiptBytes)!=='271c3687d63d4801b274d34dcba6833908169d1349b4caadbbc46b6d33ef60c3')throw new Error('G2_ORIGINAL_MAP_CHANGED');
  const receipt=JSON.parse(receiptBytes.toString('utf8'));
  const expected=Object.fromEntries(receipt.results.map(r=>[r.path,r.target_sha256]));
  const canonical=Object.fromEntries(Object.keys(expected).sort().map(k=>[k,expected[k]]));
  if(receipt.results.length!==30 || Object.keys(expected).length!==30
    || sha(JSON.stringify(canonical))!=='91e1be72d725b359a5c665022c5cc700aba9782bba7964115b19ab9ba34201d9'
    || receipt.target_zip_sha256!=='f64910af55a72d5551d24ceb2cc7d2ffa666b7bd8579126d719463897bdf2443')throw new Error('G2_ORIGINAL_MAP_CHANGED');
  const files=new Map();
  for(const path of Object.keys(expected)) {
    if(path.startsWith('/') || path.split('/').some(p=>p==='..'||p==='.'||!p) || path.includes('\\'))throw new Error('G2_ORIGINAL_PATH_INVALID');
    const file=fileURLToPath(new URL(path,fixture)),root=fileURLToPath(fixture).replace(/[\\/]$/,'');
    if(!lstatSync(file).isFile() || lstatSync(file).isSymbolicLink())throw new Error('G2_ORIGINAL_PATH_INVALID');
    let parent=dirname(file);
    for(;;){if(lstatSync(parent).isSymbolicLink())throw new Error('G2_ORIGINAL_PATH_INVALID');if(parent===root)break;const next=dirname(parent);if(next===parent)throw new Error('G2_ORIGINAL_PATH_INVALID');parent=next;}
    const b=readFileSync(file);
    if(sha(b)!==expected[path])throw new Error('G2_ORIGINAL_MEMBER_CHANGED');
    files.set(path,b);
  }
  const purpose=readFileSync(new URL('./purpose-attribution.php',import.meta.url));
  const recovery=readFileSync(new URL('./receipt-recovery-wordpress.php',import.meta.url));
  const transformed=buildG2SharedRepositorySources(files.get('bsre-enquiries.php'),files.get('includes/consent.php'),purpose,recovery);
  files.set('bsre-enquiries.php',Buffer.from(transformed.plugin));files.set('includes/consent.php',Buffer.from(transformed.consent));
  const folder='includes/g2-profile/';
  files.set(folder+'purpose-store.php',Buffer.from(buildG1RetentionStoreCandidate(files.get('includes/consent-store.php')).candidate));
  files.set(folder+'purpose-attribution.php',Buffer.from(transformed.purpose));
  // Original inputs, never the already modified main/consent texts.
  files.set(folder+'purpose-intake.php',Buffer.from(buildRetentionAdmissionIntake(readFileSync(new URL('bsre-enquiries.php',fixture)),readFileSync(new URL('includes/consent.php',fixture)))));
  files.set(folder+'receipt-recovery-wordpress.php',Buffer.from(transformed.recovery));
  for(const name of ['retention-admission.php','receipt-recovery.php','receipt-status.php'])files.set(folder+name,readFileSync(new URL('./'+name,import.meta.url)));
  files.set(folder+'bootstrap.php',readFileSync(new URL('./g2-shared-bootstrap.php',import.meta.url)));
  files.set(folder+'shared-repository.php',readFileSync(new URL('./g2-shared-repository.php',import.meta.url)));
  const rows=[...files.entries()].sort(([a],[b])=>a.localeCompare(b)).map(([path,b])=>Object.freeze({path,sha256:sha(b),content_base64:b.toString('base64')}));
  return Object.freeze({profile:'G2_SHARED_REPOSITORY_ONLY',status:'PRIVATE_UNACCEPTED_CANDIDATE',deployment_prohibited:true,
    original_members:30,files:Object.freeze(rows),g3_routes_or_transport_selected:false});
}
