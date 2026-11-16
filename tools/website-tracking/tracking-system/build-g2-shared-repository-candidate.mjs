import {createHash} from 'node:crypto';
const sha=b=>createHash('sha256').update(b).digest('hex');
const pins=Object.freeze({plugin:'9a0bd37545bd0da326d592bae7ac78eff0a8b79085bd4b1542d65289d627855b',
  consent:'68c36328e2b660b6209320033cc7bc4b2857e4ecbf0261fdc5822d0e0708bead',
  purpose:'de6eec40c0123ca4239f30b1d99f5547179c166bd19d47d254ea61db118bfa08',
  recovery:'de72e87d9dce89e9511607cb3447fbc9216ceafe33b011f7b2ffd58ab02518f4'});
const flag="defined('BSRE_G2_SHARED_REPOSITORY_ENABLED') && BSRE_G2_SHARED_REPOSITORY_ENABLED === true";
function pinned(bytes,key) {
  if(!Buffer.isBuffer(bytes)||sha(bytes)!==pins[key])throw new Error('G2_'+key.toUpperCase()+'_SOURCE_CHANGED');
  return bytes.toString('utf8');
}
function change(text,before,after) {
  const nl=text.includes('\r\n')?'\r\n':'\n';before=before.replaceAll('\n',nl);after=after.replaceAll('\n',nl);
  if(text.split(before).length!==2)throw new Error('G2_SELECTOR_ANCHOR_CHANGED');
  return text.replace(before,after);
}
export function buildG2SharedRepositorySources(pluginBytes,consentBytes,purposeBytes,recoveryBytes) {
  let plugin=pinned(pluginBytes,'plugin'),consent=pinned(consentBytes,'consent'),purpose=pinned(purposeBytes,'purpose'),recovery=pinned(recoveryBytes,'recovery');
  plugin=change(plugin,"require_once __DIR__ . '/includes/presentation.php';",
    "require_once __DIR__ . '/includes/presentation.php';\nrequire_once __DIR__ . '/includes/g2-profile/bootstrap.php';");
  consent=change(consent,'function consent_repository(?ConsentRepository $store = null): ConsentRepository {',
    `function consent_repository(?ConsentRepository $store = null): ConsentRepository {
    if (${flag}) {
        if (!function_exists('BSRE\\\\SharedRepository\\\\repository')) throw new \\RuntimeException('G2_BOOTSTRAP_UNAVAILABLE');
        return \\BSRE\\SharedRepository\\repository($store);
    }`);
  purpose=change(purpose,'function repository(): ConsentRepository {\n    global $wpdb;',
    `function repository(): ConsentRepository {
    global $wpdb;
    if (${flag}) return \\BSRE\\SharedRepository\\repository(Runtime::$store);`);
  purpose=change(purpose,'$db = Runtime::$store ? Runtime::$store->database() : $wpdb;',
    `$db = (${flag}) ? repository()->database() : (Runtime::$store ? Runtime::$store->database() : $wpdb);`);
  // Status guards/rate limits and the proof-return branch remain BEFORE this assertion.
  recovery=change(recovery,'    return Intake\\response(200, recover($body->proof, $session, $secret, $now, static function (string $id) use ($wpdb) {',
    `    if (${flag}) \\BSRE\\SharedRepository\\repository();
    return Intake\\response(200, recover($body->proof, $session, $secret, $now, static function (string $id) use ($wpdb) {`);
  return Object.freeze({plugin,consent,purpose,recovery,diagnostic_only:true,deployment_prohibited:true,
    candidate_sha256:Object.freeze({plugin:sha(plugin),consent:sha(consent),purpose:sha(purpose),recovery:sha(recovery)})});
}
