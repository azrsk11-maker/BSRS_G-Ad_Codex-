/** Builds a private review packet only. No Docker/PHP execution, source or provider writes. */
import{readFileSync,writeFileSync,mkdirSync,existsSync}from'node:fs';
import{dirname,resolve,join}from'node:path';
import{fileURLToPath,pathToFileURL}from'node:url';
import{createHash}from'node:crypto';
import{buildManifest,names,folder}from'./build-runtime.mjs';
const here=dirname(fileURLToPath(import.meta.url));
const root=resolve(process.env.BSRE_SOURCE_ROOT||resolve(here,'../../..'));
export const modes=['disabled','missing_provider','nonce','signature','coverage','reference_coverage','closed_due','closed_early','retire','known_after','unknown_after','new_choice','restore_later','cas_ack','rollback','trigger','foreign_key','snapshot_expiry','compact','floor_restore','upgrade_scope','large_unrelated','partition_conflict','orphan_history','expired_approval','revoked_cleanup','expired_backup_reference','external_deadlines'];
const sha=b=>createHash('sha256').update(b).digest('hex');
export async function buildPacket(){
 const{buildG36LabPacket}=await import(pathToFileURL(join(root,'tools/staging-lab/build-coupled-canonical-v3-lab.mjs')).href);
 const previous=await buildG36LabPacket({source_root:root}),manifest=buildManifest(),files=new Map();
 for(const[path,bytes]of previous.site)files.set('g36/'+path,Buffer.from(bytes));
 // Retained helper is a lab input only, not part of the unchanged 67-file site.
 files.set('g36/contact-abi.php',previous.auxiliary.get('contact-abi.php'));
 for(const name of names)files.set('g37-pref/runtime/'+name,readFileSync(join(folder,name)));
 files.set('g37-pref/runtime/preference-source.json',manifest.bytes);
 files.set('g37-pref/FixturePorts.php',readFileSync(join(here,'native/FixturePorts.php')));
 files.set('g37-pref/native.php',readFileSync(join(here,'native/native.php')));
 const receipt={schema:'bsre-g37-preference-native-packet-v1',status:'PREPARED_NATIVE_UNEXECUTED',site_files:67,
  original_site_profile:previous.summary.profile,runtime_source_manifest_sha256:manifest.sha256,runtime_files:5,
  modes,required_profiles:['debian-bookworm','mariadb-11.8.9'],synthetic_service_fixtures_only:true,actual_provider_accepted:false,
  missing_acceptance:['four new G2 two-connection wait/rollback schedules','all statement/commit/readback fault schedules','cross-subject nested reference corruption native case','full code-update process/actor migration native case','single-subject/partition overflow/business scale','genuine provider enrollment, source coverage, metadata visibility and key/snapshot custody']};
 return{files,receipt};
}
if(process.argv[1]&&import.meta.url===pathToFileURL(process.argv[1]).href){
 const result=await buildPacket(),packetId=sha(Buffer.from(JSON.stringify([...result.files].map(([p,b])=>[p,sha(b)]).sort(([a],[b])=>a.localeCompare(b)))));
 const packetDirectory='verification/packet-'+packetId.slice(0,12),destination=join(here,packetDirectory);
 if(existsSync(destination))throw Error('G37_FRESH_PRIVATE_PACKET_REQUIRED');
 mkdirSync(destination,{recursive:true});
 const outputs=[];
 for(const[path,bytes]of result.files){const target=join(destination,path);mkdirSync(dirname(target),{recursive:true});writeFileSync(target,bytes,{flag:'wx'});outputs.push({path,bytes:bytes.length,sha256:sha(bytes)});}
 writeFileSync(join(here,'NATIVE_PACKET_MANIFEST.json'),JSON.stringify({...result.receipt,packet_id:packetId,packet_directory:packetDirectory,outputs},null,2)+'\n');
 writeFileSync(join(here,'ENTRYPOINT_APPEND.fragment'),'\n# Explicit private G37 preference acceptance; after every accepted G36 contact lane.\n'+modes.map(mode=>'php -d sendmail_path=/bin/false /opt/lab/g37-pref/native.php '+mode).join('\n')+'\n');
 writeFileSync(join(here,'DOCKER_INTEGRATION.md'),'Use the exact packet_directory in NATIVE_PACKET_MANIFEST.json as an explicit build-context input. Preserve its g36/ and g37-pref/ paths beneath /opt/lab. The g36 site must match the accepted 67-file synthetic site; only contact-abi.php is an extra lab helper. Copy as root before USER mysql, then make application/runtime files read-only. Append the28 fixed commands only after all retained G36 phases in BOTH existing isolated profiles. BSRE_SOURCE_ROOT may select the public curated input tree; otherwise the public tool root is derived portably. No real service keys/URLs or production data belong in this packet. This file does not change Source or authorize integration.\n');
 process.stdout.write(JSON.stringify({status:result.receipt.status,packet_files:outputs.length,site_files:67,runtime_files:5,modes:modes.length,native_execution:false})+'\n');
}
