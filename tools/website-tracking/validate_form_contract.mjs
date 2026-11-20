/** Validate the bounded, read-only native enquiry form contract receipt. */
import {readFileSync} from 'node:fs';

const expected = new Map([
  ['/enquire/off-plan/', ['budget','property_type','timeline','funding']],
  ['/enquire/resale/', ['budget','property_type','timeline','funding']],
  ['/enquire/sell/', ['property_type','timeline','authority']],
  ['/enquire/let/', ['property_type','timeline','authority']],
  ['/enquire/rent/', ['budget','property_type','timeline']]
]);
const common = ['name','phone','country','email','area','property_details','website','contact_consent','marketing_consent'];

export function validateFormContract(receipt) {
  const errors = [];
  const pages = Array.isArray(receipt?.pages) ? receipt.pages : [];
  if (receipt?.schema_version !== 1) errors.push('schema_version must be 1');
  if (receipt?.read_only !== true || receipt?.changes_made !== false) errors.push('receipt must be read-only with changes_made=false');
  if (!/runtime receiver|CSRF|signature|deduplication/i.test(String(receipt?.evidence_limit))) errors.push('evidence_limit must disclose runtime limits');
  if (pages.length !== expected.size || new Set(pages.map(p => p.path)).size !== expected.size) errors.push('exactly five distinct service paths are required');
  for (const [path, required] of expected) {
    const page = pages.find(p => p.path === path);
    if (!page) { errors.push(`${path}: missing`); continue; }
    if (page.method !== 'post' || page.action !== '#') errors.push(`${path}: expected same-page POST contract`);
    const fields = new Set(Array.isArray(page.fields) ? page.fields : []);
    for (const field of [...common, ...required]) if (!fields.has(field)) errors.push(`${path}: missing ${field}`);
  }
  return {schema_version:1, valid:errors.length===0, errors, release_authorized:false};
}

if (process.argv[1] && process.argv[1].endsWith('validate_form_contract.mjs')) {
  const receipt = JSON.parse(readFileSync(process.argv[2], 'utf8'));
  const result = validateFormContract(receipt);
  console.log(JSON.stringify(result));
  process.exitCode = result.valid ? 0 : 1;
}
