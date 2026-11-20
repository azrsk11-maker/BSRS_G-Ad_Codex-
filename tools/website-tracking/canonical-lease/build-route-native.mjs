// Fixed synthetic native derivation. No provider credentials or runtime authority.
import {readFileSync} from 'node:fs';
import {createHash} from 'node:crypto';
const sha=value=>createHash('sha256').update(value).digest('hex');
export const ROUTE_NATIVE_SHA='6bf64c476663ecf0e0c7a5a3ce7d5697603badae163bbd8066d5ccb932f83d19';
export const G5_NATIVE_SHA='266076af2e47feb2e72db3de5143c9490fc310dc431dbf2e5d78ee3bd4e20bd2';
function once(value,before,after,edits){
 if(value.split(before).length!==2)throw new Error('G35_NATIVE_ANCHOR_CHANGED');
 edits.push({before,after});return value.replace(before,after);
}
export function buildCanonicalRouteNative(){
 const raw=readFileSync(new URL('../../staging-lab/g3-route-context-native.php',import.meta.url));
 const g5=readFileSync(new URL('../g5-runtime-ports/tests/native.php',import.meta.url));
 if(sha(raw)!==ROUTE_NATIVE_SHA||sha(g5)!==G5_NATIVE_SHA)throw new Error('G35_NATIVE_PREIMAGE_CHANGED');
 let text=raw.toString('utf8');const edits=[];
 text=once(text,"$mode=$argv[1]??'enforced';\nif(count($argv)>2 || !in_array($mode,['enforced','inactive','missing-store','disabled','malformed'],true)) throw new RuntimeException('G3_FIXED_MODE_ONLY');",
 "$canonicalMode=$argv[1]??'routes';\nif(count($argv)>2 || !in_array($canonicalMode,['routes','loss'],true)) throw new RuntimeException('G35_FIXED_MODE_ONLY');\n$mode='enforced';",edits);
 text=once(text,"define('WP_ENVIRONMENT_TYPE','local');define('WP_PLUGIN_DIR','/opt/lab/g3/plugins');",
 "define('WP_ENVIRONMENT_TYPE','local');define('WP_CONTENT_DIR','/opt/lab/g35/wp-content');define('WP_PLUGIN_DIR',WP_CONTENT_DIR.'/plugins');define('BSRE_CANONICAL_LEASE_ENABLED',true);",edits);
 text=once(text,"!is_writable('/opt/lab/g3/plugins')","!is_writable('/opt/lab/g35')",edits);
 text=once(text,"$wpdb->prefix='g3_'.str_replace('-','_',$mode).'_synthetic_';","$wpdb->prefix='g35_'.$canonicalMode.'_synthetic_';",edits);
 const anchor="    foreach(E\\SERVICES as $slug=>$service)foreach(['lead','purpose-lead'] as $route){";
 text=once(text,anchor,"    $canonicalProducer=new \\BSRE\\ActualRetention\\CanonicalCaptureProducer($wpdb);\n"+
 "    g3check('canonical_first_global_is_original_lease_class',get_class($wpdb)==='BSRE\\ClosedRetention\\LeaseBoundWpdb' && defined('BSRE_CANONICAL_LEASE_BOOTSTRAPPED') && BSRE_CANONICAL_LEASE_BOOTSTRAPPED===true);\n"+
 "    g3check('canonical_shared_repository_exact_object',G\\repository()->database()===$wpdb && G\\Runtime::$db===$wpdb && G\\Runtime::$store===G\\repository());\n"+anchor,edits);
 const rowAnchor="        g3check($name.'_common_store_linked',is_array($row) && $row['lead_id']===$accepted['lead_id'] && $row['event_id']===$accepted['event_id'] && (int)$row['known']===0 && (int)$row['analytics']===0 && (int)$row['ad_measurement']===0);";
 text=once(text,rowAnchor,rowAnchor+"\n        $canonicalProducer->assertCurrent($wpdb);$canonicalProducer->assertPurposeRecord($row);g3check($name.'_actual_canonical_producer_accepts_retained_row',true);",edits);
 text=once(text,"['phase'=>'g3_route_context','mode'=>$mode,'checks'=>$checks,'runtime_isolation'=>$isolation,'forward_count'=>count($forwards)",
 "['phase'=>'g35_route_context','mode'=>$canonicalMode,'checks'=>$checks,'runtime_isolation'=>$isolation,'forward_count'=>count($forwards)",edits);
 let recovered=text;for(const {before,after}of [...edits].reverse()){
  if(recovered.split(after).length!==2)throw new Error('G35_NATIVE_REVERSE_ANCHOR_CHANGED');recovered=recovered.replace(after,before);
 }
 if(recovered!==raw.toString('utf8'))throw new Error('G35_NATIVE_REVERSE_FAILED');
 const originalG5=g5.toString('utf8'),start='final class SyntheticWitness implements A\\AnchorTransport',end='final class SyntheticProducer implements A\\CaptureProducer';
 if(originalG5.split(start).length!==2||originalG5.split(end).length!==2)throw new Error('G35_NATIVE_FIXTURE_SPAN_CHANGED');
 const fixtures=originalG5.slice(originalG5.indexOf(start),originalG5.indexOf(end)).replaceAll('A\\','G5\\').replaceAll('C\\','Closed\\');
 const postlude=readFileSync(new URL('./route-custody-postlude.php',import.meta.url),'utf8');
 if(!postlude.startsWith('<?php\n'))throw new Error('G35_POSTLUDE_TAG_CHANGED');
 return {php:Buffer.from(text+"\nuse BSRE\\ActualRetention as G5;\nuse BSRE\\ClosedRetention as Closed;\n"+fixtures+'\n'+postlude.slice(6)),
  original_route_sha256:ROUTE_NATIVE_SHA,original_G5_sha256:G5_NATIVE_SHA,ordered_edits:edits.length,original_route_recovered:true,
  synthetic_fixtures_only:true,production_authorized:false};
}
