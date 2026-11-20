import {readFileSync,writeFileSync,mkdirSync} from 'node:fs';
import {dirname,join,resolve} from 'node:path';
import {fileURLToPath} from 'node:url';
import {createHash} from 'node:crypto';
import {currentInputProfile} from './current-input-context.mjs';
export const here=dirname(fileURLToPath(import.meta.url));
export const sha=b=>createHash('sha256').update(b).digest('hex');
const pref='tools/website-tracking/g5-preference-runtime/candidate/plugin/includes/candidate/retention/';
const receiver='tools/website-tracking/g5-receiver-runtime/';
export const FIXED_ROOT='/opt/lab/g39-history-local';
export const FIXED_PREFIX='g39_history_synthetic_';
export function editExact(input,changes){
 let bytes=Buffer.from(input),edits=[];
 for(const [label,before,after] of changes){
  const b=Buffer.from(before),a=Buffer.from(after);const at=bytes.indexOf(b);
  if(at<0||bytes.indexOf(b,at+b.length)!==-1)throw Error('G39_EDIT_ANCHOR:'+label);
  edits.push({label,offset:at,before,after});bytes=Buffer.concat([bytes.subarray(0,at),a,bytes.subarray(at+b.length)]);
 }
 let reversed=Buffer.from(bytes);
 for(const e of [...edits].reverse()){
  const after=Buffer.from(e.after);if(!reversed.subarray(e.offset,e.offset+after.length).equals(after))throw Error('G39_REVERSE_ANCHOR');
  reversed=Buffer.concat([reversed.subarray(0,e.offset),Buffer.from(e.before),reversed.subarray(e.offset+after.length)]);
 }
 if(!reversed.equals(Buffer.from(input)))throw Error('G39_REVERSE_FAILED');
 return {bytes,receipt:{preimage_sha256:sha(input),output_sha256:sha(bytes),reverse_verified:true,edits}};
}
export function deriveJournal(bytes){
 const methods=readFileSync(join(here,'edits/journal-history-methods.php.txt'),'utf8');
 return editExact(bytes,[
  ['PRIVATE_READ_QUARANTINE','    private bool $uncertain = false;','    private bool $uncertain = false;\n    private bool $localHistoryUncertain = false;'],
  ['RETAIN_UNCERTAIN_READ_CUSTODY','                if ($held) {','                if ($held && !$this->localHistoryUncertain) {'],
  ['PURPOSE_SPECIFIC_CURRENT_READ','    public function historyIncomplete(): bool',methods+'    public function historyIncomplete(): bool']
 ]);
}
export function derivePreference(bytes){
 const methods=readFileSync(join(here,'edits/preference-history-methods.php.txt'),'utf8');
 const physical=readFileSync(join(here,'edits/preference-physical-methods.php.txt'),'utf8');
 const source=Buffer.from(bytes).toString('utf8'),parts=preferenceReadMethods(source);
 const result=editExact(bytes,[
  ['PRIVATE_READ_MODE','    private bool $leased=false;private bool $transaction=false;private bool $uncertain=false;','    private bool $leased=false;private bool $transaction=false;private bool $uncertain=false;\n    private bool $historyBorrowed=false;private bool $historyReadBlock=false;'],
  ['NO_SQL_MUTATION_WHILE_BORROWED','    private function query(string $sql): int {\n        $this->guard(true);',"    private function query(string $sql): int {\n        if($this->historyBorrowed)Guard::fail('G39_READ_ONLY_BORROW_NO_MUTATION');\n        $this->guard(true);"],
  ['LEASE_READ_ONLY_BORROW','        if(!$this->leased||!$this->db->custodyIsActive()',
   "        if($this->historyBorrowed&&($this->scalar('SELECT @@session.in_transaction')!=='1'||$this->scalar('SELECT @@session.tx_read_only')!=='1'||$this->scalar('SELECT @@session.tx_isolation')!=='REPEATABLE-READ'))Guard::fail('G39_BORROWED_CUSTODY_REQUIRED');\n        if((!$this->leased&&!$this->historyBorrowed)||!$this->db->custodyIsActive()"],
  ['PURPOSE_SPECIFIC_BORROW','    public function discover(string $cursor): array {',methods+physical+parts.map(p=>p.bytes.toString()).join('')+'    public function discover(string $cursor): array {']
 ]);
 result.receipt.extracted_validators=parts.map(p=>p.receipt);return result;
}
function extracted(text,start,end,changes,label){
 const at=text.indexOf(start),last=text.indexOf(end,at+start.length);if(at<0||last<0||text.indexOf(start,at+1)!==-1)throw Error('G39_EXTRACTION_ANCHOR:'+label);
 const original=text.slice(at,last),result=editExact(Buffer.from(original),changes);
 result.receipt={label,source_offset:Buffer.byteLength(text.slice(0,at)),source_bytes:Buffer.byteLength(original),source_sha256:sha(original),...result.receipt};return result;
}
function replaceAllEdits(text,before,after,label){
 const changes=[];const n=text.split(before).length-1;if(!n)throw Error('G39_EXTRACTION_REPLACE:'+label);
 for(let i=0;i<n;i++)changes.push([label+'_'+i,before,after]);
 // editExact requires unique anchors; include one complete evolving method for each repeated replacement.
 const stages=[];for(let i=0;i<n;i++){const next=text.replace(before,after);stages.push([label+'_'+i,text,next]);text=next;}return stages;
}
function preferenceReadMethods(source){
 const schemaStart='    private function schema(): void {',schemaEnd='    private function metadataVisibility(array $tables): void {';
 const original=source.slice(source.indexOf(schemaStart),source.indexOf(schemaEnd));
 let work=original;const schemaChanges=[];
 for(const [label,before,after]of [['SCHEMA_READ_NAME','private function schema()','private function historySchema()'],['OWNER_MOVED_TO_TYPED_BLOCK','        $this->lease();\n        $this->metadataVisibility([$this->table,$this->audit]);\n','']]){schemaChanges.push([label,before,after]);work=work.replace(before,after);}
 for(const [before,after,label]of [['$this->rows(','$this->historyRows(','TYPED_ROWS'],['$this->scalar(','$this->historyScalar(','TYPED_SCALAR']]){const stages=replaceAllEdits(work,before,after,label);schemaChanges.push(...stages);work=stages.at(-1)[2];}
 const schema=extracted(source,schemaStart,schemaEnd,schemaChanges,'EXACT_SHARED_SCHEMA_VALIDATORS');
 const metadata=extracted(source,schemaEnd,'    private function consentMutationSchema(): void {',[
  ['METADATA_READ_NAME','private function metadataVisibility(array $tables)','private function historyMetadataVisibility(array $tables,\\BSRE\\ActualRetention\\HistoryLocalV1\\BorrowedHistoryContext $context)'],
  ['GUARDED_EXISTING_METADATA_PROTOCOL',"$this->proofs->request('preference-metadata','COMPLETE_CONSTRAINT_VISIBILITY',$request)",'$this->proofs->historyMetadataVisibility($request,$context)']
 ],'EXACT_METADATA_VISIBILITY_VALIDATORS');
 const rawStart='    private function raw(bool $lock): ?array {',rawEnd='    public function current(bool $lock=false): array {';
 const raw=extracted(source,rawStart,rawEnd,[
  ['RAW_READ_NAME','private function raw(bool $lock): ?array','private function historyRaw(array $r,array $auditRow,\\BSRE\\ActualRetention\\HistoryLocalV1\\BorrowedHistoryContext $context): array'],
  ['CAPTURED_TYPED_CONTROL_ROW','        $this->lease();$r=$this->rows($this->db->prepare("SELECT * FROM {$this->table} WHERE id=%s ORDER BY id LIMIT 2",$this->policy->partition).($lock?\' FOR UPDATE\':\'\'),1);\n        if($r===[])return null;$r=$r[0];\n',''],
  ['GUARDED_CUSTODY_KEY_CALLBACK','$state=$this->custody->open($r[\'body\'],$r[\'operation_revision\']);',"$context->assertCurrent($this->policy);\n        try{$state=$this->custody->open($r['body'],$r['operation_revision']);}finally{$context->assertCurrent($this->policy);}"],
  ['CAPTURED_TYPED_AUDIT_ROW','$audit=$this->rows($this->db->prepare("SELECT * FROM {$this->audit} WHERE operation_id=%s",$intent[\'operation\']),1);',"if(($auditRow['operation_id']??null)!==$intent['operation'])Guard::fail('PREFERENCE_AUDIT_BINDING_INVALID');\n        $audit=[$auditRow];"]
 ],'EXACT_CONTROL_CIPHER_INTENT_AUDIT_VALIDATORS');
 return[schema,metadata,raw];
}
export function deriveContracts(bytes){
 const source=Buffer.from(bytes).toString('utf8'),start='    public function request(string $service,string $operation,array $payload,?array &$attestation=null): array {',end='    public function approval(';
 const method=extracted(source,start,end,[
  ['PURPOSE_SPECIFIC_GUARDED_READ','public function request(string $service,string $operation,array $payload,?array &$attestation=null)','private function historyReadRequest(string $service,string $operation,array $payload,\\BSRE\\ActualRetention\\HistoryLocalV1\\BorrowedHistoryContext $context,?array &$attestation=null)'],
  ['READ_OPERATION_WHITELIST',"        $source=$this->policy->source();","        if(!(($service==='preference-anchor'&&$operation==='CURRENT'&&$payload===[])||($service==='preference-metadata'&&$operation==='COMPLETE_CONSTRAINT_VISIBILITY')))Guard::fail('G39_READ_ONLY_PROOF_SCOPE_REQUIRED');\n        $source=$this->policy->source();"],
  ['GUARDED_TRANSPORT_CALLBACK',"        $e=Guard::json($this->transport->exchange($operation,$request));",'        $context->assertCurrent($this->policy);\n        try{$raw=$this->transport->exchange($operation,$request);}finally{$context->assertCurrent($this->policy);}\n        $e=Guard::json($raw);'],
  ['GUARDED_KEY_CALLBACK_AND_POST_IO_CLOCK',"        $now=time();$sig=base64_decode($e['signature'],true);$key=$this->keys->publicKey($service,$e['key_id']);", "        // The post-transport full guard also precedes this key callback: only pure closed JSON/type/binding checks intervene.\n        $sig=base64_decode($e['signature'],true);\n        try{$key=$this->keys->publicKey($service,$e['key_id']);}finally{$context->assertCurrent($this->policy);}\n        $now=time();"]
 ],'EXACT_SIGNED_REQUEST_VALIDATORS_WITH_GUARDED_READ_CALLBACKS');
 const entries="    public function historyCurrent(\\BSRE\\ActualRetention\\HistoryLocalV1\\BorrowedHistoryContext $context,?array &$attestation=null): array {return $this->historyReadRequest('preference-anchor','CURRENT',[],$context,$attestation);}\n    public function historyMetadataVisibility(array $payload,\\BSRE\\ActualRetention\\HistoryLocalV1\\BorrowedHistoryContext $context): array {return $this->historyReadRequest('preference-metadata','COMPLETE_CONSTRAINT_VISIBILITY',$payload,$context);}\n";
 const result=editExact(bytes,[['ADDITIVE_PURPOSE_SPECIFIC_PROOF_READS',end,entries+method.bytes.toString()+end]]);result.receipt.extracted_validators=[method.receipt];return result;
}
function admissionHelper(engine,workflow){
 const a=engine.indexOf('    private function verifiedAdmission(int $now): array');
 const end=engine.indexOf('    /** Canonical record/chronology checks',a);
 if(a<0||end<0)throw Error('G39_ADMISSION_SOURCE_ANCHOR');
 const original=engine.slice(a,end);
 const transformed=editExact(Buffer.from(original),[
  ['READ_METHOD','private function verifiedAdmission','public function read'],
  ['CONFIGURATION_DIGEST_METHOD','private static function admissionHash','public static function configurationHash']
 ]);
 const k=workflow.indexOf('    private static function keys($value, array $expected): void');
 const stop=workflow.indexOf('    private static function uuid(',k);
 if(k<0||stop<0)throw Error('G39_ADMISSION_PRIMITIVES_ANCHOR');
 const primitives=workflow.slice(k,stop);
 const text="<?php\ndeclare(strict_types=1);\nnamespace BSRE\\ActualRetention\\HistoryLocalV1;\nuse BSRE\\ClosedRetention as C;\n/** Exact extracted current admission validators; no new external protocol. */\nfinal class VerifiedAdmission {\n    public function __construct(private C\\Admission $admission) {}\n"+transformed.bytes.toString()+primitives+
  "    private static function digest(array $value): string { return C\\Workflow::digest($value); }\n    private static function fail(string $code): void { throw new C\\Failure($code); }\n}\n";
 return {bytes:Buffer.from(text),receipt:{kind:'EXACT_METHOD_EXTRACTION',engine_slice:{offset:Buffer.byteLength(engine.slice(0,a)),bytes:Buffer.byteLength(original),sha256:sha(original)},primitives_slice:{offset:Buffer.byteLength(workflow.slice(0,k)),bytes:Buffer.byteLength(primitives),sha256:sha(primitives)},method_derivation:transformed.receipt,output_sha256:sha(text)}};
}
function replaceEvery(text,before,after,label,edits){
 const n=text.split(before).length-1;if(n===0)throw Error('G39_DRIVER_ANCHOR:'+label);
 for(let i=0;i<n;i++){const offset=Buffer.byteLength(text.slice(0,text.indexOf(before)));edits.push({label,offset,before,after});text=text.replace(before,after);}return text;
}
function buildPinned(sourceRoot,pins){
 const inputs=new Map();for(const [p,pin] of Object.entries(pins.files)){
  const b=readFileSync(join(sourceRoot,p));if(b.length!==pin.bytes||sha(b)!==pin.sha256)throw Error('G39_SOURCE_PIN_CHANGED:'+p);inputs.set(p,b);
 }
 const files=new Map(),derivations={};
 for(const p of ['build-candidate.mjs','runtime/control.gs','runtime/no-copy.gs','candidate/plugin/includes/candidate/receiver/ReceiverContracts.php','candidate/plugin/includes/candidate/receiver/NoMailCopyAlgebra.php','candidate/plugin/includes/candidate/receiver/ActualRetirementPort.php','candidate/plugin/includes/candidate/receiver/ReceiverOperationalEvidence.php','candidate/plugin/includes/candidate/receiver/ActualReceiverWorkflow.php','tests/control-fixture.mjs','tests/native-bridge.mjs'])files.set(p,inputs.get(receiver+p));
 for(const [name,path] of [['ActualReceiverJournal.php',receiver+'candidate/plugin/includes/candidate/closed-enquiry-retention/ActualReceiverJournal.php'],['ActualPurgeJournal.php','tools/website-tracking/g5-actual-purge-runtime/code/ActualPurgeJournal.php']]){
  const d=deriveJournal(inputs.get(path));files.set('candidate/plugin/includes/candidate/closed-enquiry-retention/'+name,d.bytes);derivations[name]=d.receipt;
 }
 const prefNames=['ActualPreferenceRetention.php','PreferenceAlgebra.php','PreferenceAtomicStore.php','PreferenceContracts.php','PreferenceCustody.php'];
 for(const name of prefNames){const b=inputs.get(pref+name);if(name==='PreferenceAtomicStore.php'||name==='PreferenceContracts.php'){const d=name==='PreferenceAtomicStore.php'?derivePreference(b):deriveContracts(b);files.set('preference/'+name,d.bytes);derivations[name]=d.receipt;}else files.set('preference/'+name,b);}
 const prefManifest={contract:'bsre-preference-runtime-v1',files:Object.fromEntries(prefNames.map(n=>[n,sha(files.get('preference/'+n))]))};
 files.set('preference/preference-source.json',Buffer.from(JSON.stringify(prefManifest)+'\n'));
 const helper=admissionHelper(inputs.get('tools/website-tracking/g5-actual-purge-runtime/code/ActualPurgeEngine.php').toString(),inputs.get('tools/closed-enquiry-retention/Workflow.php').toString());
 files.set('history/VerifiedAdmission.php',helper.bytes);derivations['VerifiedAdmission.php']=helper.receipt;
 files.set('history/LocalHistoryObserver.php',readFileSync(join(here,'history/LocalHistoryObserver.php')));
 files.set('tests/foreign-capture-snapshot.php',inputs.get('tools/website-tracking/g5-actual-purge-runtime/tests/foreign-capture-snapshot.php'));
 for(const n of ['native-history.php','synthetic-ledger.json'])files.set('tests/'+n,readFileSync(join(here,'native',n)));
 const original=inputs.get(receiver+'tests/receiver-runtime-native.php');let driver=original.toString();const edits=[];
 const cut=" $journal=new A\\ActualReceiverJournal($wpdb,$policy,$custody,$authority,$evidence,$proof,$producer);";
 if(driver.split(cut).length!==2)throw Error('G39_DRIVER_CUT_CHANGED');const at=driver.indexOf(cut),tail=driver.slice(at);
 const after=" require __DIR__.'/native-history.php';\n"+
  "$g39ForeignAfter=\\BSRE\\G38PurgeLab\\snapshot();\n"+
  "if(!isset($g39ForeignAfter['g39_history_synthetic_bsre_consent_captures']))throw new RuntimeException('G39_OWN_CAPTURE_TABLE_MISSING');\n"+
  "unset($g39ForeignAfter['g39_history_synthetic_bsre_consent_captures']);\n"+
  "receiver_check('g39_all_foreign_capture_tables_preserved',$g39ForeignAfter===$g39ForeignBefore);\n"+
  " echo wp_json_encode(['phase'=>'g39_local_history','checks'=>$checks,'runtime_isolation'=>$isolation,'local_checkpoint_digest'=>$historyCheckpoint['digest'],'synthetic_services'=>true,'provider_accepted'=>false,'production_authorized'=>false]).\"\\n\";\n}finally{fclose($pipes[0]);fclose($pipes[1]);if(proc_close($bridge)!==0)throw new RuntimeException('G39_RECEIVER_BRIDGE_EXIT_FAILED');}\n";
 edits.push({label:'OWN_LOCAL_OBSERVER_TAIL',offset:Buffer.byteLength(driver.slice(0,at)),before:tail,after});driver=driver.slice(0,at)+after;
 driver=replaceEvery(driver,'/opt/lab/g5-receiver-runtime',FIXED_ROOT,'OWN_RUNTIME_ROOT',edits);
 driver=replaceEvery(driver,'g5_receiver_synthetic_',FIXED_PREFIX,'OWN_FIXED_NAMESPACE',edits);
 driver=replaceEvery(driver,'/tmp/g5-receiver-runtime-progress.json','/tmp/g39-local-history-progress.json','OWN_PROGRESS',edits);
 const flag="define('BSRE_ACTUAL_RECEIVER_RETIREMENT_ENABLED',true);";
 const setup=flag+"\ndefine('BSRE_G5_PREFERENCE_RUNTIME_ENABLED',true);\ndefine('BSRE_G5_PREFERENCE_SOURCE_SHA256',hash_file('sha256','"+FIXED_ROOT+"/preference/preference-source.json'));";
 const def=editExact(Buffer.from(driver),[['EXPLICIT_PREFERENCE_BINDING',flag,setup]]);edits.push(...def.receipt.edits);driver=def.bytes.toString();
 const cutMarker="$wpdb->prefix='"+FIXED_PREFIX+"';E\\install();";
 const freshness="$wpdb->prefix='"+FIXED_PREFIX+"';\n$wpdb->last_error='';$g39Existing=$wpdb->get_col($wpdb->prepare('SELECT TABLE_NAME FROM information_schema.TABLES WHERE TABLE_SCHEMA=DATABASE() AND BINARY LEFT(TABLE_NAME,%d)=BINARY %s ORDER BY TABLE_NAME LIMIT 2',strlen($wpdb->prefix),$wpdb->prefix));\nif($wpdb->last_error!==''||$g39Existing!==[])throw new RuntimeException('G39_FRESH_NAMESPACE_REQUIRED');\n"+
  "require_once '/opt/lab/g36/contact-abi.php';\nrequire_once __DIR__.'/foreign-capture-snapshot.php';\n"+
  "$g39ForeignBefore=\\BSRE\\G38PurgeLab\\snapshot();\n"+
  "if(!array_filter($g39ForeignBefore,fn($row)=>$row['rows']>=1100))throw new RuntimeException('G39_FOREIGN_SCALE_PREDECESSOR_REQUIRED');\nE\\install();";
 const fresh=editExact(Buffer.from(driver),[['FRESH_FIXED_NAMESPACE',cutMarker,freshness]]);edits.push(...fresh.receipt.edits);driver=fresh.bytes.toString();
 let reverse=Buffer.from(driver);for(const e of [...edits].reverse()){const b=Buffer.from(e.after);if(!reverse.subarray(e.offset,e.offset+b.length).equals(b))throw Error('G39_DRIVER_REVERSE_ANCHOR');reverse=Buffer.concat([reverse.subarray(0,e.offset),Buffer.from(e.before),reverse.subarray(e.offset+b.length)]);}if(!reverse.equals(original))throw Error('G39_DRIVER_REVERSE_FAILED');
 files.set('tests/local-history-native.php',Buffer.from(driver));derivations['local-history-native.php']={preimage_sha256:sha(original),output_sha256:sha(driver),reverse_verified:true,edits};
 const expectedChecks=[...driver.replace("require __DIR__.'/native-history.php';",files.get('tests/native-history.php').toString()).matchAll(/receiver_check\('([^']+)'/g)].map(m=>m[1]);
 if(expectedChecks.length===0||new Set(expectedChecks).size!==expectedChecks.length)throw Error('G39_CHECK_SET_INVALID');
 const manifest={schema:'bsre-g39-private-local-history-native-v1',accepted_source_head:pins.accepted_head,fixed_root:FIXED_ROOT,fixed_prefix:FIXED_PREFIX,
  entry:'tests/local-history-native.php',phase:'g39_local_history',expected_checks:expectedChecks,preference_source_sha256:sha(files.get('preference/preference-source.json')),
  local_scope_only:true,native_executed:false,provider_accepted:false,production_authorized:false,
  derivations,files:Object.fromEntries([...files].map(([p,b])=>[p,{sha256:sha(b),bytes:b.length}]))};
 files.set('G39_BUILD.json',Buffer.from(JSON.stringify(manifest,null,2)+'\n'));return{files,manifest};
}
/** Frozen historical context; rejects the successor queue bytes. */
export function build(sourceRoot){
 return buildPinned(sourceRoot,JSON.parse(readFileSync(join(here,'SOURCE_PINS.json'),'utf8')));
}
/** Explicit held current input context; native packet bytes must remain identical. */
export function buildCurrent(sourceRoot){
 if(arguments.length!==1)throw Error('G39_CURRENT_EXACT_SOURCE_ROOT_REQUIRED');
 const profile=currentInputProfile(),packet=buildPinned(sourceRoot,profile.pins);
 if(packet.files.size!==25||packet.manifest.expected_checks.length!==43||
    sha(packet.files.get('G39_BUILD.json'))!==profile.receipt.frozen_runtime_manifest_sha256)
  throw Error('G39_CURRENT_RUNTIME_BYTES_CHANGED');
 return packet;
}
if(process.argv[1]===fileURLToPath(import.meta.url)){
 const source=process.argv[2];if(!source||process.argv.length!==3)throw Error('G39_EXACT_SOURCE_ROOT_REQUIRED');
 const packet=build(resolve(source));for(const [p,b]of packet.files){const dest=join(here,'prepared-native',p);mkdirSync(dirname(dest),{recursive:true});writeFileSync(dest,b);}
 writeFileSync(join(here,'DERIVATION.json'),JSON.stringify(packet.manifest.derivations,null,2)+'\n');
 console.log(JSON.stringify({prepared:true,files:packet.files.size,checks:packet.manifest.expected_checks.length,native_executed:false,manifest_sha256:sha(packet.files.get('G39_BUILD.json'))}));
}
