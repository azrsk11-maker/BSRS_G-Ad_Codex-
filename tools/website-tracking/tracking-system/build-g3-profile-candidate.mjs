// Separate fixed route/context candidate; immutable G2 and original source remain intact.
import {readFileSync} from 'node:fs';
import {createHash} from 'node:crypto';
import {buildG2ProfileCandidate} from './build-g2-profile-candidate.mjs';
import {buildRetentionAdmissionClient} from './build-retention-admission-candidate.mjs';
const sha=b=>createHash('sha256').update(b).digest('hex');
const WORDPRESS='dd85e87e930e449136887af826e91aefffa9af429b39fe30c610621b101cef18';
function change(text,before,after) {
  const nl=text.includes('\r\n')?'\r\n':'\n';before=before.replaceAll('\n',nl);after=after.replaceAll('\n',nl);
  if(text.split(before).length!==2)throw new Error('G3_TRANSPORT_ANCHOR_CHANGED');
  return text.replace(before,after);
}
export function buildG3WordPressCandidate(bytes) {
  if(!Buffer.isBuffer(bytes)||sha(bytes)!==WORDPRESS)throw new Error('G3_WORDPRESS_SOURCE_CHANGED');
  let text=bytes.toString('utf8');
  text=change(text,'function safe(value) {',"function safe(value, expectedPath) {\n    if (typeof value !== 'string' || value.length > 512) return '';");
  text=change(text,"return url.protocol === 'https:' && url.origin === window.location.origin && !url.username && !url.password ? url.href : '';",
    "return url.protocol === 'https:' && url.origin === window.location.origin && !url.username && !url.password && !url.search && !url.hash && url.pathname === expectedPath ? url.href : '';");
  text=change(text,'safe(config.contextEndpoint);',"safe(config.contextEndpoint, '/wp-json/bsre/v1/context');");
  text=change(text,'safe(config.leadEndpoint);',"safe(config.leadEndpoint, '/wp-json/bsre/v1/lead');");
  const guard="        if (!response.ok || !/^[0-9]{10}\\.[a-f0-9]{64}$/.test(result.csrf_token || '') || result.expires_in !== 7200 || result.minimum_delay_ms !== 2100) return;";
  text=change(text,guard,guard+`
        const transport = result.transport;
        if (!transport || typeof transport !== 'object' || Array.isArray(transport)
          || Object.keys(transport).sort().join(',') !== 'admission_required,contract,purpose_endpoint'
          || transport.contract !== 'bsre-profile-transport-v1' || transport.admission_required !== true) return;
        const purposeEndpoint = safe(transport.purpose_endpoint, '/wp-json/bsre/v1/purpose-lead');
        if (!purposeEndpoint) return;`);
  text=change(text,"window.BSRELeadConfig = { endpoint: leadEndpoint, csrfToken: result.csrf_token, csrfHeader: 'X-BSRE-CSRF', measurementEligible: result.measurement_eligible === true };",
    "window.BSRELeadConfig = { endpoint: leadEndpoint, csrfToken: result.csrf_token, csrfHeader: 'X-BSRE-CSRF', measurementEligible: result.measurement_eligible === true, purposeAttributionEndpoint: purposeEndpoint, retentionAdmissionRequired: true };");
  return Object.freeze({candidate:text,original_sha256:WORDPRESS,candidate_sha256:sha(text),deployment_prohibited:true});
}
export function buildG3ProfileCandidate(auditBytes) {
  const parent=buildG2ProfileCandidate(auditBytes);
  const files=new Map(parent.files.map(r=>[r.path,Buffer.from(r.content_base64,'base64')]));
  let plugin=files.get('bsre-enquiries.php').toString('utf8');
  // Independent include: selected G3 still owns held routes when G2 is disabled/missing.
  plugin=change(plugin,"require_once __DIR__ . '/includes/g2-profile/bootstrap.php';",
    "require_once __DIR__ . '/includes/g2-profile/bootstrap.php';\nrequire_once __DIR__ . '/includes/g3-profile/bootstrap.php';");
  files.set('bsre-enquiries.php',Buffer.from(plugin));
  files.set('assets/wordpress.js',Buffer.from(buildG3WordPressCandidate(files.get('assets/wordpress.js')).candidate));
  files.set('assets/lead.js',Buffer.from(buildRetentionAdmissionClient(files.get('assets/lead.js'))));
  files.set('includes/g3-profile/bootstrap.php',readFileSync(new URL('./g3-bootstrap.php',import.meta.url)));
  files.set('includes/g3-profile/route-context.php',readFileSync(new URL('./g3-route-context.php',import.meta.url)));
  return Object.freeze({profile:'G3_ROUTE_CONTEXT_ADMISSION_CLIENT_ONLY',status:'HELD_NATIVE_ACCEPTANCE_REQUIRED',
    original_members:30,deployment_prohibited:true,complete_coupled_profile:false,
    files:Object.freeze([...files].sort(([a],[b])=>a.localeCompare(b)).map(([path,bytes])=>Object.freeze({path,sha256:sha(bytes),content_base64:bytes.toString('base64')})))});
}
