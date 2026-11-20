/** Explicit V2 engineering profile. Originals and existing frame builder remain untouched. */
import {createHash} from 'node:crypto';
export const NATIVE_FRAME_CONTRACT='bsre-native-page-context-v2';
export const ORIGINAL_RUNTIME_SHA256='459ab031d0bb3e0f079fdce5d2de36d266748f0c57f361c262e8ed5c03bfed4d';
const hash=value=>createHash('sha256').update(value).digest('hex');
function begin(value,expected) {
  if(typeof value!=='string'||typeof expected!=='string'||!/^[a-f0-9]{64}$/.test(expected)||hash(value)!==expected)throw new Error('G4_FRAME_PREIMAGE_MISMATCH');
  const edits=[];return {get value(){return value;},edits,replace(before,after){if(value.split(before).length!==2)throw new Error('G4_FRAME_ANCHOR_COUNT');value=value.replace(before,after);edits.push({before,after});},finish(){return{output:value,edits,preimage_sha256:expected,output_sha256:hash(value),contract:NATIVE_FRAME_CONTRACT};}};
}
export function buildNativeFrameParent(value,expected) {
  const c=begin(value,expected);
  // Caller first derives buildFrameDeliveryCandidate(original). Its queue/withdrawal/timeout logic is preserved.
  if(!value.includes('    const entry = {payload, expires: Date.now() + 30000};'))throw new Error('G4_FRAME_DELIVERY_PREREQUISITE');
  c.replace("  function pagePath() { const value = window.location.pathname; return /^\\/enquire\\/(?:(?:off-plan|resale|rent|sell|let)\\/)?$/.test(value) ? value : ''; }",
    "  function pagePath() { try { const value = window.BSRENativePageContext.current(); return value && value.page_path === window.location.pathname ? value.page_path : ''; } catch (_) { return ''; } }");
  c.replace("purpose: state.purpose, nonce: state.nonce, page_path: pagePath(), referrer_origin:","purpose: state.purpose, nonce: state.nonce, context_contract: '"+NATIVE_FRAME_CONTRACT+"', page_path: pagePath(), referrer_origin:");
  return c.finish();
}
const CHILD_GUARD=String.raw`
  // V2 binds to the same-origin parent's server-emitted native port, never message metadata or a URL query.
  const NATIVE_CONTRACT = 'bsre-native-page-context-v2';
  const NATIVE_FIELDS = ['campaign_key','landing_page_id','page_version','page_family','property_destination','property_segment','transaction_intent','language','property_id','project_id'];
  const NATIVE_ROLES = ['off_plan','resale','tenant','seller','landlord','unknown'];
  let nativeBound = null;
  function nativeCurrent() {
    let value;
    try { value = window.parent.BSRENativePageContext.current(); } catch (_) { return null; }
    if (!value || typeof value !== 'object' || Array.isArray(value)
        || Object.keys(value).sort().join(',') !== 'company,ctas,forms,page_context,page_path,registry_revision,role,schema'
        || value.schema !== 1 || value.company !== 'BlackSwan Real Estate'
        || typeof value.registry_revision !== 'string' || !/^[A-Za-z][A-Za-z0-9_-]{0,79}$/.test(value.registry_revision)
        || typeof value.page_path !== 'string' || value.page_path.length > 240 || !(value.page_path === '/' || /^\/(?:[a-z][a-z0-9-]{0,60}\/)+$/.test(value.page_path))
        || value.page_path !== window.parent.location.pathname || !NATIVE_ROLES.includes(value.role)
        || !value.page_context || typeof value.page_context !== 'object' || Array.isArray(value.page_context)) return null;
    for (const [key,item] of Object.entries(value.page_context)) {
      if (!NATIVE_FIELDS.includes(key) || typeof item !== 'string') return null;
      if (key === 'campaign_key' ? !/^BSRE-C[0-9]{4}$/.test(item)
        : key === 'landing_page_id' ? !/^BSRE-LP[0-9]{4}$/.test(item)
        : key === 'language' ? !/^[a-z]{2}(?:-[A-Z]{2})?$/.test(item)
        : key === 'page_version' ? !(/^[A-Za-z][A-Za-z0-9_-]{0,79}$/.test(item) || /^[0-9]{1,4}(?:\.[0-9]{1,4}){1,3}$/.test(item))
        : !/^[A-Za-z][A-Za-z0-9_-]{0,79}$/.test(item)) return null;
    }
    if (Object.hasOwn(value.page_context,'campaign_key') !== Object.hasOwn(value.page_context,'landing_page_id')) return null;
    return JSON.parse(JSON.stringify(value));
  }
  function nativeParameters() {
    const value=nativeCurrent();
    if (!nativeBound || !value || JSON.stringify(value) !== JSON.stringify(nativeBound) || value.page_path !== pagePath) return null;
    return Object.assign({schema_version:'1.0.0',site_scope:'BSRE_REAL_ESTATE',page_path:value.page_path,role:value.role,company:value.company},value.page_context);
  }
  function nativePayload(parameters) {
    const expected=nativeParameters();
    if (!expected || !parameters || typeof parameters !== 'object' || Array.isArray(parameters)) return false;
    const allowed=Object.keys(expected).concat('cta_location');
    if (Object.keys(parameters).some(key=>!allowed.includes(key)) || Object.keys(expected).some(key=>parameters[key] !== expected[key])) return false;
    return !Object.hasOwn(parameters,'cta_location') || ['header','hero','form','footer','sticky','other'].includes(parameters.cta_location);
  }
`;
export function buildNativeFrameChild(value,expected=ORIGINAL_RUNTIME_SHA256) {
  if(expected!==ORIGINAL_RUNTIME_SHA256)throw new Error('G4_FRAME_ORIGINAL_CHILD_REQUIRED');
  const c=begin(value,expected);
  c.replace('  function receive(payload) {',CHILD_GUARD+'\n  function receive(payload) {');
  c.replace("!['generate_lead','form_start','whatsapp_click','telephone_click'].includes(payload.event_name)","!['generate_lead','form_start','whatsapp_click','phone_click'].includes(payload.event_name)");
  c.replace("      if (!p || Object.keys(p).some(key => !['schema_version','site_scope','page_path','role','cta_location'].includes(key)) || p.schema_version !== '1.0.0' || p.site_scope !== 'BSRE_REAL_ESTATE' || p.page_path !== pagePath || !['off_plan','resale','tenant','seller','landlord','unknown'].includes(p.role) || Object.prototype.hasOwnProperty.call(p,'cta_location') && !['header','hero','form','footer','sticky','other'].includes(p.cta_location)) return;", "      if (!nativePayload(p)) return;");
  c.replace("      if (analytics && pageView) command('event','page_view',Object.assign({},privacy(),{ send_to:config.measurement_id }));", "      const native = nativeParameters();\n      if (!native) { revoke(); return; }\n      if (analytics && pageView) command('event','page_view',Object.assign({},privacy(),native,{ send_to:config.measurement_id }));");
  c.replace("      if (data.config_version !== config.config_version || typeof data.nonce !== 'string' || !/^[a-f0-9]{8}-[a-f0-9]{4}-4[a-f0-9]{3}-[89ab][a-f0-9]{3}-[a-f0-9]{12}$/.test(data.nonce) || typeof data.page_view !== 'boolean' || !/^\\/enquire\\/(?:(?:off-plan|resale|rent|sell|let)\\/)?$/.test(data.page_path || '')) return;", "      const native = nativeCurrent();\n      if (data.context_contract !== NATIVE_CONTRACT || !native || data.page_path !== native.page_path || data.config_version !== config.config_version || typeof data.nonce !== 'string' || !/^[a-f0-9]{8}-[a-f0-9]{4}-4[a-f0-9]{3}-[89ab][a-f0-9]{3}-[a-f0-9]{12}$/.test(data.nonce) || typeof data.page_view !== 'boolean') return;\n      nativeBound = native;");
  // Ads remains the existing exact accepted-enquiry path; reject stale/unreviewed parent context there too.
  c.replace("    } else {\n      if (Object.keys(payload).sort().join(',') !== 'event_name,page_path,role,transaction_id'", "    } else {\n      if (!nativeParameters()) return;\n      if (Object.keys(payload).sort().join(',') !== 'event_name,page_path,role,transaction_id'");
  return c.finish();
}
export function reverseNativeFrame(result) {
  let value=result.output;
  for(const {before,after}of[...result.edits].reverse()){if(value.split(after).length!==2)throw new Error('G4_FRAME_REVERSE_ANCHOR');value=value.replace(after,before);}
  if(hash(value)!==result.preimage_sha256)throw new Error('G4_FRAME_REVERSE_HASH');return value;
}
