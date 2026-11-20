import {createHash} from 'node:crypto';
import {readFileSync, writeFileSync} from 'node:fs';
import {pathToFileURL} from 'node:url';
import {buildAttributionClientCandidate} from './build-attribution-client-candidate.mjs';

const pins = {
  plugin: '9a0bd37545bd0da326d592bae7ac78eff0a8b79085bd4b1542d65289d627855b',
  consent: '68c36328e2b660b6209320033cc7bc4b2857e4ecbf0261fdc5822d0e0708bead',
  store: '7ccb7fdf0d88a3d2b1d54832f61c71bfcc025554bebf3927d7f5ce0c72f12262',
};
function pinned(bytes, name) {
  if (createHash('sha256').update(bytes).digest('hex') !== pins[name]) throw new Error('PURPOSE_SOURCE_CHANGED');
  return Buffer.from(bytes).toString('utf8').replaceAll('\r\n', '\n');
}
function replace(source, before, after) {
  if (source.split(before).length !== 2) throw new Error('PURPOSE_ANCHOR_CHANGED');
  return source.replace(before, after);
}

// Source-derived storage retains the original transaction and receipt linking.
// The added values live in the same capture row, never in the receiver schema.
export function buildPurposeStoreCandidate(bytes) {
  let source = pinned(bytes, 'store');
  source = replace(source, 'namespace BSRE\\Enquiries;', 'namespace BSRE\\PurposeAttribution;\nuse const BSRE\\Enquiries\\CONSENT_PREFERENCE_SECONDS;');
  source = replace(source, 'interface ConsentRepository {', 'interface ConsentRepository extends \\BSRE\\Enquiries\\ConsentRepository {');
  source = replace(source, '    private function row(string $sql): ?array {', '    public function database() { return $this->db; }\n    private function row(string $sql): ?array {');
  source = replace(source, 'return $this->transaction(function () use ($capture) {', `return $this->transaction(function () use ($capture) {
            $capture += prepare_capture($this->db, $capture);`);
  source = replace(source, 'gclid_last_captured_ms,lead_id,event_id) VALUES', 'gclid_last_captured_ms,lead_id,event_id,purpose_version,purpose_hash,purpose_record_hash,purpose_json) VALUES');
  source = replace(source, "%d,%d,'','')\", $capture['request_id']", "%d,%d,'','',%d,%s,%s,%s)\", $capture['request_id']");
  source = replace(source, "$capture['gclid_last_captured_ms']));", "$capture['gclid_last_captured_ms'], $capture['purpose_version'], $capture['purpose_hash'], $capture['purpose_record_hash'], $capture['purpose_json']));");
  source = replace(source, "if (!hash_equals($row['fingerprint'], $capture['fingerprint']))", "if ((int) $row['purpose_version'] !== $capture['purpose_version'] || !hash_equals($row['purpose_hash'], $capture['purpose_hash']) || !hash_equals($row['fingerprint'], $capture['fingerprint']))");
  source = source.replaceAll("            return $row;", "            assert_record($row);\n            return $row;");
  source = replace(source, "            event_id varchar(64) NOT NULL,", `            event_id varchar(64) NOT NULL,
            purpose_version tinyint unsigned NOT NULL DEFAULT 0,
            purpose_hash char(64) NOT NULL DEFAULT '',
            purpose_record_hash char(64) NOT NULL DEFAULT '',
            purpose_json mediumtext NULL,`);
  source = replace(source, "foreach (['delivery_pending','click_capture_state','gclid_first','gclid_last','gclid_first_captured_ms','gclid_last_captured_ms'] as $column)", "foreach (['delivery_pending','click_capture_state','gclid_first','gclid_last','gclid_first_captured_ms','gclid_last_captured_ms','purpose_version','purpose_hash','purpose_record_hash','purpose_json'] as $column)");
  source = source.slice(0, source.indexOf('// Normal plugin file updates'));
  source = replace(source, "        update_option('bsre_consent_schema_version', '2', false);\n        return get_option('bsre_consent_schema_version') === '2';", '        return true;');
  return source;
}

export function buildPurposeIntakeCandidate(pluginBytes, consentBytes) {
  const plugin = pinned(pluginBytes, 'plugin');
  const consent = pinned(consentBytes, 'consent');
  const receiveStart = plugin.indexOf('function receive(');
  const receiveEnd = plugin.indexOf('\n/** Google Apps Script returns', receiveStart);
  const stageStart = consent.indexOf('function consent_stage_submission(');
  const stageEnd = consent.indexOf('\n/** Whole, immutable browser capture.', stageStart);
  if ([receiveStart, receiveEnd, stageStart, stageEnd].some(index => index < 0)) throw new Error('PURPOSE_INTAKE_ANCHOR_CHANGED');
  let receive = plugin.slice(receiveStart, receiveEnd).replace('function receive(', 'function receive_wire(');
  let stage = consent.slice(stageStart, stageEnd);
  stage = replace(stage, '$store = consent_repository($repository);', '$store = repository();');
  // The store resolves and binds the purpose data under its existing transaction.
  receive = replace(receive, 'consent_stage_submission(', 'stage_submission(');
  stage = replace(stage, 'function consent_stage_submission(', 'function stage_submission(');
  return `<?php\nnamespace BSRE\\PurposeAttribution;\nuse const BSRE\\Enquiries\\COOKIE;\nuse const BSRE\\Enquiries\\UUID_V4;\nuse const BSRE\\Enquiries\\CONSENT_NOTICE_VERSION;\nuse function BSRE\\Enquiries\\{ready,reply,same_origin_request,valid_csrf,client_address,limited,validate_payload,live_paths,consent_request_is_retry,consent_current,measurement_eligible,consent_capture_clicks,envelope,send_envelope,consent_mark_uncertain,receiver_result,consent_link_accepted,response};\n${stage}\n${receive}\n`;
}

export function buildPurposeClientCandidate(bytes) {
  let source = buildAttributionClientCandidate(bytes);
  source = replace(source, '    const url = new URL(endpoint);', `    const url = new URL(endpoint);
    if (url.pathname === '/wp-json/bsre/v1/purpose-lead') url.pathname = '/wp-json/bsre/v1/lead';`);
  source = replace(source, "const ATTR_PARAMS = ['utm_source', 'utm_medium', 'utm_campaign', 'utm_term', 'utm_content'];", "const ATTR_PARAMS = ['utm_source', 'utm_medium', 'utm_campaign', 'utm_id', 'utm_term', 'utm_content', 'google_campaign_id', 'ad_group_id', 'creative_id'];");
  source = replace(source, 'parameters: parameters, capture_id: captureId };', `parameters: parameters, capture_id: captureId,
      decision_version: currentSnapshot()?.decision_version || '', notice_version: currentSnapshot()?.notice_version || '' };`);
  source = replace(source, "? value.capture_id : '' };", "? value.capture_id : '', decision_version: typeof value.decision_version === 'string' ? value.decision_version : '', notice_version: typeof value.notice_version === 'string' ? value.notice_version : '' };");
  source = replace(source, "adAttribution = refreshTouch(AD_KEY, AD_PARAMS, false, allowed.advertising, 'advertising');", "adAttribution = refreshTouch(AD_KEY, AD_PARAMS.concat(ATTR_PARAMS), false, allowed.advertising, 'advertising');");
  source = replace(source, "purpose === 'advertising' && now && !Object.keys(now.parameters).length", "purpose === 'advertising' && now && !AD_PARAMS.some(key => Object.hasOwn(now.parameters, key))");
  source = replace(source, 'previous && Object.keys(previous.parameters).length', 'previous && AD_PARAMS.some(key => Object.hasOwn(previous.parameters, key))');
  source = replace(source, 'const base = ad && Object.keys(ad.parameters).length ? ad : analytics || ad;', 'const base = ad && AD_PARAMS.some(key => Object.hasOwn(ad.parameters, key)) ? ad : analytics || ad;');
  source = replace(source, '  function combinedAttribution() {', `  function purposeEndpoint() {
    try {
      const value = window.BSRELeadConfig && window.BSRELeadConfig.purposeAttributionEndpoint;
      if (typeof value !== 'string' || !value) return '';
      const url = new URL(value, window.location.href);
      return url.protocol === 'https:' && url.origin === window.location.origin && !url.username && !url.password
        && !url.search && !url.hash && url.pathname === '/wp-json/bsre/v1/purpose-lead' ? url.href : '';
    } catch (_) { return ''; }
  }
  function purposeAttribution() {
    const flags = permissions();
    const allowed = measurementEligible() && !syntheticForm();
    function history(value, permitted, analytics) {
      function touch(item) {
        if (!allowed || !permitted || !item || !/^[0-9a-f]{32}$/.test(item.decision_version || '')) return null;
        return {capture_id: item.capture_id, decision_version: item.decision_version,
          notice_version: item.notice_version, landing_page: item.landing_page,
          referrer: analytics ? item.referrer : '', timestamp: item.timestamp, parameters: item.parameters};
      }
      return {first: touch(value.first), last: touch(value.last)};
    }
    return {version: 1, analytics: history(attribution, flags.analytics, true), advertising: history(adAttribution, flags.advertising, false)};
  }
  function combinedAttribution() {`);
  source = replace(source, '    return result;\n  }\n  const dispatchRecords', `    // The receiver's preserved v1 projection accepts these original keys only.
    Object.values(result).forEach(touch => {
      if (touch) Object.keys(touch.parameters).forEach(key => {
        if (!['utm_source','utm_medium','utm_campaign','utm_term','utm_content','gclid','gbraid','wbraid'].includes(key)) delete touch.parameters[key];
      });
    });
    return result;
  }
  const dispatchRecords`);
  source = replace(source, "    let attemptBody = '';", "    let attemptBody = '';\n    let attemptPurposeBody = '';\n    let attemptEndpoint = '';");
  source = replace(source, '\n      const endpoint = safeEndpoint();', '\n      const endpoint = attemptEndpoint || purposeEndpoint() || safeEndpoint();');
  source = replace(source, '        attemptPermission = currentSnapshot();', `        attemptPermission = currentSnapshot();
        attemptEndpoint = endpoint;
        if (purposeEndpoint() === endpoint) {
          const purpose = purposeAttribution();
          attemptPurposeBody = JSON.stringify({version: 1, wire_body: attemptBody, attribution: purpose});
          attemptHadAttribution = Boolean(purpose.analytics.first || purpose.analytics.last);
          attemptHadAdIdentifiers = Boolean(purpose.advertising.first || purpose.advertising.last);
        }`);
  source = replace(source, "attemptHadAttribution = permissions().analytics && ['first', 'last']", "attemptHadAttribution = attemptHadAttribution || permissions().analytics && ['first', 'last']");
  source = replace(source, "attemptHadAdIdentifiers = ['first', 'last']", "attemptHadAdIdentifiers = attemptHadAdIdentifiers || ['first', 'last']");
  source = replace(source, 'body: attemptBody, signal: controller.signal', 'body: attemptPurposeBody || attemptBody, signal: controller.signal');
  source = source.replaceAll("attemptBody = ''; attemptFields = '';", "attemptBody = ''; attemptPurposeBody = ''; attemptEndpoint = ''; attemptFields = '';");
  return source;
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  const [mode, first, second, output] = process.argv.slice(2);
  if (mode === 'store') writeFileSync(second, buildPurposeStoreCandidate(readFileSync(first)));
  else if (mode === 'intake') writeFileSync(output, buildPurposeIntakeCandidate(readFileSync(first), readFileSync(second)));
  else throw new Error('PURPOSE_BUILD_MODE_REQUIRED');
}
