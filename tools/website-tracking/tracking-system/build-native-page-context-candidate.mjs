/** Additive G4 composer. Apply AFTER selected client/presentation derivations. Never edit fixture inputs. */
import {readFileSync} from 'node:fs';
import {createHash} from 'node:crypto';
const runtime=readFileSync(new URL('./native-page-context/client.js',import.meta.url),'utf8');
export const sha256=value=>createHash('sha256').update(value).digest('hex');
function once(value,before,after) {
  if (value.split(before).length !== 2) throw new Error('G4_ANCHOR_COUNT');
  return value.replace(before,after);
}
function bound(value,expected) {
  if (typeof value !== 'string' || typeof expected !== 'string' || !/^[a-f0-9]{64}$/.test(expected) || sha256(value) !== expected) throw new Error('G4_PREIMAGE_MISMATCH');
}
export function buildNativePageContextClient(value,expectedSha256) {
  bound(value,expectedSha256);
  const edits=[];
  function change(before,after) { value=once(value,before,after); edits.push({before,after}); }
  change("  function safeCanonical(event) {",runtime+"\n  function safeCanonical(event) {");
  change("!/^\\/enquire\\/(?:(?:off-plan|resale|rent|sell|let)\\/)?$/.test(event.page_path)","(!/^\\/enquire\\/(?:(?:off-plan|resale|rent|sell|let)\\/)?$/.test(event.page_path) && !window.BSRENativePageContext.matches(event.page_path,event.role))");
  change("  function mapGA4(event) {\n    const safe = safeCanonical(event);", "  function mapGA4(event) {\n    const native = window.BSRENativePageContext.mapLegacy(safeCanonical(event));\n    if (native) return native;\n    const safe = safeCanonical(event);");
  change("page_path: /^\\/enquire\\/(off-plan|resale|rent|sell|let)\\/$/.test(pagePath) ? pagePath : '/enquire/'", "page_path: window.BSRENativePageContext.matches(pagePath,role) ? pagePath : /^\\/enquire\\/(off-plan|resale|rent|sell|let)\\/$/.test(pagePath) ? pagePath : '/enquire/'");
  change("  function pageContext() {\n    const form = document.querySelector('form[data-bsre-form]');", "  function pageContext() {\n    const native = window.BSRENativePageContext.current();\n    if (native) return {role:native.role,path:native.page_path};\n    const form = document.querySelector('form[data-bsre-form]');");
  return {output:value,edits,preimage_sha256:expectedSha256,output_sha256:sha256(value)};
}
export function buildNativePageContextPresentation(value,expectedSha256) {
  bound(value,expectedSha256); const edits=[];
  function change(before,after) { value=once(value,before,after); edits.push({before,after}); }
  change("    $flags = JSON_HEX_TAG | JSON_HEX_AMP | JSON_HEX_APOS | JSON_HEX_QUOT;", "    // Optional tracking fails closed independently of enquiry acceptance.\n    $native_context = null;\n    try { $native_context = \\BSRE\\NativeTracking\\NativePageContext::wordpress()->current(); } catch (\\Throwable $ignored) {}\n    $flags = JSON_HEX_TAG | JSON_HEX_AMP | JSON_HEX_APOS | JSON_HEX_QUOT;");
  change("        . ';window.BSREGoogleConfig='", "        . ';window.BSRENativePageContextConfig=' . wp_json_encode($native_context, $flags)\n        . ';window.BSREGoogleConfig='");
  return {output:value,edits,preimage_sha256:expectedSha256,output_sha256:sha256(value)};
}
export function reverseNativePageContext(result) {
  let value=result.output;
  for (const edit of [...result.edits].reverse()) value=once(value,edit.after,edit.before);
  if (sha256(value) !== result.preimage_sha256) throw new Error('G4_REVERSE_MISMATCH');
  return value;
}
