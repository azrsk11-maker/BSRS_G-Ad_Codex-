import {readFileSync,writeFileSync,mkdirSync} from 'node:fs';import {fileURLToPath} from 'node:url';import {sha} from './build.mjs';
export function nativePacketFromInputs(inputs){
 const base=Buffer.from(inputs.driver);
 const anchor=" $producer->assertCurrent($wpdb);receiver_check('lease_clean_and_original_global_preserved'";
 let driver=base.toString('utf8');if(driver.split(anchor).length!==2)throw Error('NATIVE_CONSUMER_ANCHOR_CHANGED');
 driver=driver.replace(anchor," require __DIR__.'/native-extension.php';\n"+anchor);
 const files=new Map([['tests/receiver-runtime-native.php',Buffer.from(driver)],['tests/native-extension.php',readFileSync(new URL('./tests/native-extension.php',import.meta.url))]]);
 const positiveAnchor=' $journal=new A\\ActualReceiverJournal($wpdb,$policy,$custody,$authority,$evidence,$proof,$producer);';
 if(base.toString('utf8').split(positiveAnchor).length!==2)throw Error('POSITIVE_NATIVE_ANCHOR_CHANGED');
 const cut=base.toString('utf8').indexOf(positiveAnchor);
 const positive=base.toString('utf8').slice(0,cut)+" require __DIR__.'/native-positive.php';\n echo wp_json_encode(['phase'=>'g5_actual_purge_positive','checks'=>$checks,'runtime_isolation'=>$isolation,'synthetic_services'=>true,'provider_accepted'=>false,'production_authorized'=>false]).\"\\n\";\n}finally{fclose($pipes[0]);fclose($pipes[1]);if(proc_close($bridge)!==0)throw new RuntimeException('G5_RECEIVER_BRIDGE_EXIT_FAILED');}\n";
 files.set('tests/purge-positive-native.php',Buffer.from(positive));
 files.set('tests/native-positive.php',readFileSync(new URL('./tests/native-positive.php',import.meta.url)));
 const intakeSource=Buffer.from(inputs.intakeSource).toString('utf8');
 const headers=JSON.parse(intakeSource.match(/var LEAD_HEADERS = (\[.*?\]);/)[1].replaceAll("'",'"'));
 if(headers.length!==26)throw Error('INTAKE26_SCHEMA_CHANGED');
 files.set('tests/intake26-headers.json',Buffer.from(JSON.stringify(headers)+'\n'));
 files.set('tests/outcome40-schema.json',Buffer.from(inputs.outcomeSchema));
 const prefix='candidate/plugin/includes/candidate/closed-enquiry-retention/';
 for(const name of ['ActualPurgeEngine.php','ActualPurgeJournal.php','ActualPurgeCaptureResource.php','ActualPurgeResources.php','ActualPurgeWorkflow.php','PurgeBoundary.php'])files.set(prefix+name,readFileSync(new URL('./code/'+name,import.meta.url)));
 files.set(prefix+'CaptureRules.php',Buffer.from(inputs.captureRules));
 const manifest={schema:'bsre-actual-purge-prepared-native-v1',predecessor:'g5-receiver-runtime fixed native lab',predecessor_driver_sha256:sha(base),
  isolation:'unchanged predecessor driver preflight; fixed namespace; no network; no capabilities; non-root; read-only application',
  native_executed:false,provider_accepted:false,production_authorized:false,
  native_entrypoints:{
   held:{path:'/opt/lab/g5-receiver-runtime/tests/receiver-runtime-native.php',fresh_fixed_lab_required:true,expected_checks:[...driver.matchAll(/receiver_check\('([^']+)'/g),...files.get('tests/native-extension.php').toString().matchAll(/receiver_check\('([^']+)'/g)].map(m=>m[1])},
   positive:{path:'/opt/lab/g5-receiver-runtime/tests/purge-positive-native.php',fresh_fixed_lab_required:true,expected_checks:[...positive.matchAll(/receiver_check\('([^']+)'/g),...files.get('tests/native-positive.php').toString().matchAll(/receiver_check\('([^']+)'/g)].map(m=>m[1])}
  },
  files:Object.fromEntries([...files].map(([name,b])=>[name,{sha256:sha(b),bytes:b.length}]))};
 return {files,manifest};
}
export function nativePacket(source){return nativePacketFromInputs({
 driver:readFileSync(source+'/tools/website-tracking/g5-receiver-runtime/tests/receiver-runtime-native.php'),
 intakeSource:readFileSync(source+'/tools/staging-lab/fixtures/receiver-v2/Code.gs'),
 outcomeSchema:readFileSync(source+'/tools/qualification-history/schema/outcome-register-schema.json'),
 captureRules:readFileSync(source+'/tools/website-tracking/g5-runtime-ports/candidate/plugin/includes/candidate/closed-enquiry-retention/CaptureRules.php')
});}
if(process.argv[1]===fileURLToPath(import.meta.url)){const p=nativePacket(process.argv[2]);const out=fileURLToPath(new URL('./native-packet/',import.meta.url));for(const [name,b] of p.files){mkdirSync(new URL('.',new URL(name,'file:///'+out.replace(/\\/g,'/'))),{recursive:true});writeFileSync(out+name,b);}writeFileSync(out+'MANIFEST.json',JSON.stringify(p.manifest,null,2)+'\n');}
