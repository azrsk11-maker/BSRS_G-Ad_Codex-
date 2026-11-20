/** Builds only the explicit public synthetic G36 lab packet. Never reads a retained private packet. */
import {readFileSync,mkdirSync,writeFileSync,lstatSync,existsSync,realpathSync} from 'node:fs';
import {resolve,join,dirname} from 'node:path';
import {fileURLToPath,pathToFileURL} from 'node:url';
import {buildG36Native,digest,PROFILE} from '../website-tracking/coupled-package-v3/build-native.mjs';
const need=(ok,code)=>{if(!ok)throw new Error(code);};
export async function buildG36LabPacket({source_root}={}){
  need(typeof source_root==='string','G36_LAB_SOURCE_REQUIRED');const root=resolve(source_root);
  const {syntheticInput}=await import(pathToFileURL(join(root,'tools/website-tracking/coupled-package-v3/synthetic-input.mjs')).href);
  const {composeCoupledCanonicalLeaseV3,assertHeldCandidateV3}=await import(pathToFileURL(join(root,'tools/website-tracking/coupled-package-v3/compose-v3.mjs')).href);
  const result=await composeCoupledCanonicalLeaseV3(await syntheticInput({source_root:root,digits:'19995550123',display:'+1 999 555 0123'}));
  assertHeldCandidateV3(result);
  need(result.files.size===68 && result.public_summary.profile===PROFILE,'G36_LAB_PACKET_CHANGED');
  const receiver=result.files.get('companion/receiver/Code.gs');
  const v2Receiver=result.private_manifest.v2_private_manifest.outputs.find(row=>row.path==='companion/receiver/Code.gs');
  need(v2Receiver && digest(receiver)===v2Receiver.sha256 && digest(receiver)===result.private_manifest.receiver_sha256,'G36_LAB_V2_RECEIVER_CHANGED');
  const site=new Map(),prefix='site/';
  for(const [path,bytes] of result.files){
    if(path==='companion/receiver/Code.gs')continue;
    need(path.startsWith(prefix),'G36_LAB_UNEXPECTED_PACKET_PATH');const relative=path.slice(prefix.length);
    need(relative==='wp-content/db.php' || relative.startsWith('wp-content/plugins/bsre-enquiries/'),'G36_LAB_UNEXPECTED_SITE_PATH');
    need(!relative.split('/').some(p=>!p||p==='.'||p==='..') && /^[A-Za-z0-9_./-]+$/.test(relative),'G36_LAB_UNSAFE_SITE_PATH');
    site.set(relative,Buffer.from(bytes));
  }
  need(site.size===67 && [...site.keys()].filter(p=>p.startsWith('wp-content/plugins/bsre-enquiries/')).length===66,'G36_LAB_SITE_COUNT');
  const base='wp-content/plugins/bsre-enquiries/',manifest=JSON.parse(site.get(base+'includes/candidate/runtime/canonical-source.json'));
  need(manifest.profile===PROFILE && Object.keys(manifest.files).length===64,'G36_LAB_MANIFEST64');
  const hub=site.get(base+'templates/source/hub.html'),guard=site.get(base+'includes/parent-isolation.php').toString();
  need(guard.includes("const OWNED_HUB_SHA256 = '"+digest(hub)+"';") && guard.includes('const OWNED_HUB_PAGE_ID = 26750;'),'G36_LAB_HUB_BINDING');
  for(const name of ['hub','off-plan','resale','rent','sell','let']){
    const body=site.get(base+'templates/source/'+name+'.html').toString(),count=s=>body.split(s).length-1;
    need(count('https://wa.me/19995550123')===(name==='hub'?0:3) && count('tel:+19995550123')===(name==='hub'?1:3)
      && count('+1 999 555 0123')===(name==='hub'||name==='rent'?1:2) && !body.includes('971568285677') && !body.includes('+971 56 828 5677'),'G36_LAB_SYNTHETIC_CONTACT_ABI');
  }
  const native=await buildG36Native({source_root:root});
  const auxiliary=new Map(native.files);
  auxiliary.set('contact-abi.php',readFileSync(new URL('../website-tracking/coupled-package-v3/native-contact-abi.php',import.meta.url)));
  auxiliary.set('contact-native.php',readFileSync(new URL('./canonical-coupled-contact-native.php',import.meta.url)));
  const build=Buffer.from(JSON.stringify({profile:PROFILE,files:[...site].sort(([a],[b])=>a.localeCompare(b)).map(([path,bytes])=>({path,sha256:digest(bytes)}))},null,2)+'\n');
  auxiliary.set('BUILD.json',build);
  auxiliary.set('NATIVE_BUILD.json',Buffer.from(JSON.stringify({schema:'bsre-g36-native-derivation-v1',profile:PROFILE,
    synthetic_only:true,deployment_prohibited:true,source_bindings:result.private_manifest.bindings,site_files:67,source_members:64,
    inherited_checks:native.inherited_checks,receipts:native.receipts,
    runtime_checks_executed:false,contact_modes:['hub','off-plan','resale','rent','sell','let']},null,2)+'\n'));
  return {site,auxiliary,receiver:Buffer.from(receiver),receiver_v2_sha256:v2Receiver.sha256,native,
    summary:{profile:PROFILE,site_files:67,plugin_files:66,source_members:64,companion_receiver_preserved:true,synthetic_only:true,native_executed:false}};
}
function ensureDirectory(path){
  if(!existsSync(path)){ensureDirectory(dirname(path));mkdirSync(path);}
  need(lstatSync(path).isDirectory()&&!lstatSync(path).isSymbolicLink()&&realpathSync(path)===path,'G36_LAB_DESTINATION_REDIRECT');
}
function writeNew(root,path,bytes){
  need(path!=='BUILD.json'||!existsSync(join(root,'BUILD.json')),'G36_LAB_BUILD_ALREADY_EXISTS');
  const target=join(root,path);need(target.startsWith(root+'/')&&!existsSync(target),'G36_LAB_OUTPUT_EXISTS');
  ensureDirectory(dirname(target));writeFileSync(target,bytes,{flag:'wx'});need(digest(readFileSync(target))===digest(bytes),'G36_LAB_OUTPUT_READBACK_CHANGED');
}
if(process.argv[1] && import.meta.url===pathToFileURL(process.argv[1]).href){
  need(process.argv.length===2,'G36_FIXED_LAB_BUILD_ONLY');
  const root='/opt/lab/g36';need(!existsSync(root),'G36_FRESH_LAB_ROOT_REQUIRED');
  const packet=await buildG36LabPacket({source_root:'/opt/lab/g36-source'});
  // Source composition, all paths and full native reversals complete before the first output write.
  ensureDirectory(root);
  for(const [path,bytes] of [...packet.site,...packet.auxiliary])writeNew(root,path,bytes);
  // The companion is outside WP_CONTENT_DIR and never substituted into another accepted lane.
  ensureDirectory('/opt/lab/g36-companion');writeNew('/opt/lab/g36-companion','Code.gs',packet.receiver);
}
