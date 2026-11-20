/** Validate the current gate matrix without turning status into release authority. */
import {readFileSync} from 'node:fs';

const STATUSES = new Set(['PASS','PARTIAL','OPEN','HOLD']);
const REQUIRED = new Set([
  'ads_pause','budget_and_campaign_controls','native_service_destinations','form_contract_validation',
  '360_page_planning','positive_keyword_library','negative_keyword_library','consent_tracking_runtime',
  'staff_rehearsal_and_capacity','business_evidence_and_brand','restricted_qualified_imports',
  'retention_and_recovery_live','github_delivery_review','production_release'
]);

export function validateGateMatrix(matrix) {
  const errors = [];
  const gates = Array.isArray(matrix?.gates) ? matrix.gates : [];
  if (matrix?.schema_version !== 1) errors.push('schema_version must be 1');
  if (matrix?.release_authorized !== false) errors.push('release_authorized must remain false');
  if (matrix?.production_changed !== false) errors.push('production_changed must remain false');
  if (matrix?.ads_serving !== false) errors.push('ads_serving must remain false');
  const ids = new Set(gates.map(g => g?.id));
  if (gates.length !== REQUIRED.size || ids.size !== gates.length || [...REQUIRED].some(id => !ids.has(id))) errors.push('required gate IDs must be present exactly once');
  for (const gate of gates) {
    if (!STATUSES.has(gate?.status)) errors.push(`${gate?.id || 'unknown'}: invalid status`);
    if (!Array.isArray(gate?.evidence) || gate.evidence.length === 0) errors.push(`${gate?.id || 'unknown'}: evidence is required`);
  }
  if (gates.find(g => g.id === 'production_release')?.status !== 'HOLD') errors.push('production_release must remain HOLD');
  return {schema_version:1, valid:errors.length===0, errors, release_authorized:false};
}

if (process.argv[1] && process.argv[1].endsWith('validate_gate_matrix.mjs')) {
  const result = validateGateMatrix(JSON.parse(readFileSync(process.argv[2], 'utf8')));
  console.log(JSON.stringify(result));
  process.exitCode = result.valid ? 0 : 1;
}
