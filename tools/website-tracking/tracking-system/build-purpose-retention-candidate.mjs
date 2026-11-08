import {readFileSync, writeFileSync, mkdirSync} from 'node:fs';
import {createHash} from 'node:crypto';
import {join} from 'node:path';
import {pathToFileURL} from 'node:url';

const pins = {PreferenceRetirement:'54cfe60473167a6bf2f8009a59a191510ef5498fb2d2eb58450f72016afe31ea',
  RetirementLedger:'3ff69def0fcc91d1894751a3188f87ae0c3f861b5879a19a76c5b9e46a0043ad',
  restore:'f043b7708e185e9a5329caffaf57a0b3eeb7414559b61d695dba8ba46dc2c2be'};
export function buildPurposeRetention(bytes, name) {
  if(createHash('sha256').update(bytes).digest('hex')!==pins[name])throw new Error('PURPOSE_RETENTION_SOURCE_CHANGED');
  let source=Buffer.from(bytes).toString('utf8').replaceAll('\r\n','\n');
  // Every derived class and its fixture must use the same isolated tables.
  // Keep all other guard conditions, including local mode and synthetic origin.
  source=source.replaceAll("'retention_synthetic_'", "'purpose_retention_synthetic_'");
  if(name==='restore'){
    source=source.replace("require '/opt/lab/consent-retention/candidate-store.php';", "require '/opt/lab/purpose/store.php';\nrequire '/opt/lab/purpose/purpose-attribution.php';");
    source=source.replace("require '/opt/lab/consent-retention/PreferenceRetirement.php';", "require '/opt/lab/purpose-retention/PreferenceRetirement.php';");
    source=source.replaceAll('BSRE\\RetentionCandidate\\','BSRE\\PurposeAttribution\\').replaceAll('BSRE\\RetentionReview\\','BSRE\\PurposeRetention\\');
    source=source.replace('$store=new WpConsentRepository($db);', `$store=new WpConsentRepository($db);
$originalDb=$wpdb; $wpdb=$db;
if (!BSRE\\PurposeAttribution\\install_consent_storage()) throw new RuntimeException('Purpose retention schema unavailable');
$wpdb=$originalDb;`);
    source=source.replace("$subject=str_repeat('e',64);", `$seedSubject=str_repeat('9',64);
$seedChoice=$store->choose($seedSubject,['analytics'=>true,'ad_measurement'=>true],BSRE\\Enquiries\\CONSENT_NOTICE_VERSION,$clock-60);
$seedId=wp_generate_uuid4(); $seedBody='SYNTHETIC PURPOSE RETENTION';
$seedTouch=['capture_id'=>wp_generate_uuid4(),'decision_version'=>$seedChoice['receipt'],'notice_version'=>BSRE\\Enquiries\\CONSENT_NOTICE_VERSION,'landing_page'=>'https://blackswanrealestate.ae/enquire/rent/','referrer'=>'','timestamp'=>($clock-30)*1000,'parameters'=>(object)['gclid'=>'Synthetic_Retention_Click']];
$seedSidecar=['version'=>1,'analytics'=>['first'=>null,'last'=>null],'advertising'=>['first'=>$seedTouch,'last'=>$seedTouch]];
BSRE\\PurposeAttribution\\Runtime::$submission=['fingerprint'=>hash('sha256',$seedBody),'sidecar'=>$seedSidecar];
$seedCapture=['request_id'=>$seedId,'fingerprint'=>hash('sha256',$seedBody),'subject_key'=>$seedSubject,'original_revision'=>$seedChoice['revision'],'decision_version'=>$seedChoice['receipt'],'notice_version'=>BSRE\\Enquiries\\CONSENT_NOTICE_VERSION,'analytics'=>1,'ad_measurement'=>1,'preference_expires_at'=>$seedChoice['expires_at'],'eligible'=>1,'known'=>1,'created_at'=>$clock-20,'uncertain'=>0,'click_capture_state'=>'CAPTURED','gclid_first'=>'Synthetic_Retention_Click','gclid_last'=>'Synthetic_Retention_Click','gclid_first_captured_ms'=>($clock-30)*1000,'gclid_last_captured_ms'=>($clock-30)*1000];
$store->stage($seedCapture); BSRE\\PurposeAttribution\\Runtime::$submission=null;
$store->link($seedId,$seedCapture['fingerprint'],'BSRE-'.wp_generate_uuid4(),'evt_'.wp_generate_uuid4());
$seedRow=$db->get_row($db->prepare("SELECT * FROM {$db->prefix}bsre_consent_captures WHERE request_id=%s",$seedId),ARRAY_A);
BSRE\\PurposeAttribution\\assert_record($seedRow);
$seedRecord=json_decode($seedRow['purpose_json'],true,12,JSON_THROW_ON_ERROR);
restore_check('purpose_seed_has_all_four_fields', (int)$seedRow['purpose_version']===1
    && preg_match('/^[a-f0-9]{64}$/D',$seedRow['purpose_hash'])===1
    && preg_match('/^[a-f0-9]{64}$/D',$seedRow['purpose_record_hash'])===1
    && is_string($seedRow['purpose_json']) && $seedRow['purpose_json']!=='');
restore_check('purpose_seed_input_hash_matches', $seedRow['purpose_hash']===hash('sha256',BSRE\\PurposeAttribution\\canonical($seedSidecar)));
restore_check('purpose_seed_has_nonempty_permitted_clicks', ($seedRecord['advertising']['first']['parameters']['gclid']??null)==='Synthetic_Retention_Click'
    && ($seedRecord['advertising']['last']['parameters']['gclid']??null)==='Synthetic_Retention_Click');
$subject=str_repeat('e',64);`);
    source=source.replace('restore_fixture(json_decode($package[\'raw\'],true));', `restore_fixture(json_decode($package['raw'],true));
$restoredSeed=$db->get_row($db->prepare("SELECT * FROM {$db->prefix}bsre_consent_captures WHERE request_id=%s",$seedId),ARRAY_A);
BSRE\\PurposeAttribution\\assert_record($restoredSeed);
restore_check('purpose_restore_keeps_exact_nonempty_sidecar', $restoredSeed===$seedRow);`);
    source=source.replace("$db->delete($db->prefix.'bsre_consent_captures',['request_id'=>$conflict['request_id']]);", `$db->delete($db->prefix.'bsre_consent_captures',['request_id'=>$conflict['request_id']]);
// The accepted submission still refers to its valid, non-retired seed decision.
// Only a nested purpose touch refers to retired evidence, isolating the new guard.
$nested=$seedRow; $nested['request_id']=wp_generate_uuid4();
$nestedRecord=$seedRecord;
$nestedRecord['advertising']['first']['decision_version']=$state['receipt'];
$nestedRecord['advertising']['last']['decision_version']=$state['receipt'];
$nested['purpose_json']=BSRE\\PurposeAttribution\\canonical($nestedRecord);
$nestedInput=$nestedRecord;
foreach(['analytics','advertising']as$purpose)foreach(['first','last']as$slot){
    if($nestedInput[$purpose][$slot]!==null)unset($nestedInput[$purpose][$slot]['original_revision'],$nestedInput[$purpose][$slot]['expires_at']);
}
$nested['purpose_hash']=hash('sha256',BSRE\\PurposeAttribution\\canonical($nestedInput));
$nested['purpose_record_hash']=hash('sha256',$nested['fingerprint']."\\n".$nested['purpose_hash']."\\n".$nested['purpose_json']);
BSRE\\PurposeAttribution\\assert_record($nested);
restore_check('nested_fixture_keeps_valid_primary_decision', $nested['state']==='ACCEPTED'
    && $nested['decision_version']===$seedChoice['receipt'] && $nested['subject_key']===$seedSubject
    && $nested['decision_version']!==$state['receipt']);
restore_check('nested_fixture_inserted', $db->insert($db->prefix.'bsre_consent_captures',$nested)!==false);
$nestedPackage=package_snapshot($retirement->backupSnapshot(),$oldAnchor['sequence'],$clock-100);
restore_check('nested_only_retired_touch_blocks_restore', restore_denied(fn()=>$retirement->previewRestore($nestedPackage['metadata'],$anchor),'RESTORED_CAPTURE_REQUIRES_RECONCILIATION'));
$db->delete($db->prefix.'bsre_consent_captures',['request_id'=>$nested['request_id']]);`);
    source=source.replace("'phase'=>'retention_restore_rehearsal'", "'phase'=>'purpose_retention_restore_rehearsal'");
  }else{
    source=source.replace('namespace BSRE\\RetentionReview;', 'namespace BSRE\\PurposeRetention;');
    if(name==='PreferenceRetirement')source=source.replace("require_once __DIR__ . '/RetentionInventory.php';", "require_once '/opt/lab/consent-retention/RetentionInventory.php';\nrequire_once '/opt/lab/purpose-retention/purpose-retention.php';");
    else source=source.replace('$eligible=[];', 'RetentionInventory::assertRestoreReferences($snapshot,$retired);\n        $eligible=[];');
  }
  return source;
}
if(process.argv[1]&&import.meta.url===pathToFileURL(process.argv[1]).href){
  const [input,fixture,output]=process.argv.slice(2);mkdirSync(output,{recursive:true});
  for(const name of ['PreferenceRetirement','RetirementLedger'])writeFileSync(join(output,name+'.php'),buildPurposeRetention(readFileSync(join(input,name+'.php')),name));
  writeFileSync(join(output,'restore.php'),buildPurposeRetention(readFileSync(fixture),'restore'));
}
