import {mkdirSync,writeFileSync,renameSync,rmSync,existsSync,lstatSync,realpathSync} from 'node:fs';
import {resolve,dirname,relative,isAbsolute,join,sep} from 'node:path';
import {randomUUID} from 'node:crypto';
import {assertHeldCandidateV3,assertWriterDestinationV3,prepareHeldWriteV3,CONTRACT_V3} from './compose-v3.mjs';
const need=(ok,code)=>{if(!ok)throw new Error(code);};
const nested=(a,b)=>{const p=relative(a,b);return p===''||(p!=='..'&&!p.startsWith('..'+sep)&&!isAbsolute(p));};
const selectionKeys=['profile','M','P','dropin_sha256','review_ref','diagnostic_only','deployment_prohibited','full_profile_complete'];
function write(result,options){
  need(options?.visibility==='PRIVATE_OFFLINE_ONLY','V3_PRIVATE_OUTPUT_REQUIRED');assertHeldCandidateV3(result);
  const selection=options.selection_binding,expected=result.private_manifest.bindings;
  need(selection&&typeof selection==='object'&&!Array.isArray(selection)&&Reflect.ownKeys(selection).sort().join(',')===[...selectionKeys].sort().join(','),'V3_ROOT_M_P_SELECTION_REQUIRED');
  const selected={};for(const key of selectionKeys){
    const d=Object.getOwnPropertyDescriptor(selection,key);need(d&&Object.hasOwn(d,'value')&&d.enumerable,'V3_ROOT_M_P_SELECTION_REQUIRED');selected[key]=d.value;
  }
  need(
    selected.profile===CONTRACT_V3.profile&&selected.M===expected.M&&selected.P===expected.P&&selected.dropin_sha256===expected.dropin_sha256&&
    typeof selected.review_ref==='string'&&selected.review_ref.length>0&&selected.review_ref.length<=256&&selected.diagnostic_only===true&&
    selected.deployment_prohibited===true&&selected.full_profile_complete===false,'V3_ROOT_M_P_SELECTION_REQUIRED');
  const destination=resolve(options.destination),parent=dirname(destination);
  assertWriterDestinationV3(result,destination);
  need(!existsSync(destination)&&existsSync(parent),'V3_NEW_OUTPUT_DIRECTORY_REQUIRED');
  need(Array.isArray(options.input_roots)&&options.input_roots.length>=2,'V3_INPUT_ROOTS_REQUIRED');
  let cursor=parent;for(;;){const s=lstatSync(cursor);need(s.isDirectory()&&!s.isSymbolicLink(),'V3_OUTPUT_PARENT_LINK');
    const next=dirname(cursor);if(next===cursor)break;cursor=next;}
  need(realpathSync(parent).toLowerCase()===parent.toLowerCase(),'V3_OUTPUT_PARENT_REDIRECTED');
  for(const root of options.input_roots){const source=realpathSync(resolve(root)).toLowerCase(),target=destination.toLowerCase();
    need(!nested(source,target)&&!nested(target,source),'V3_OUTPUT_INPUT_OVERLAP');}
  const temporary=join(parent,'.g36-held-'+randomUUID());
  // All option reads and destination/input checks precede the final genuine-result and
  // complete97-source-pin checks. Every output thereafter is detached from caller data.
  const plan=prepareHeldWriteV3(result,destination);
  const privateManifest={...plan.private_manifest,private_output_selection:{...selected}};
  const privateBytes=JSON.stringify(privateManifest,null,2)+'\n',publicBytes=JSON.stringify(plan.public_summary,null,2)+'\n';
  try{
    mkdirSync(temporary);
    for(const [path,bytes]of plan.files){const file=join(temporary,...path.split('/'));mkdirSync(dirname(file),{recursive:true});writeFileSync(file,bytes,{flag:'wx'});}
    writeFileSync(join(temporary,'PRIVATE_MANIFEST.json'),privateBytes,{flag:'wx'});
    writeFileSync(join(temporary,'PUBLIC_SUMMARY.json'),publicBytes,{flag:'wx'});
    renameSync(temporary,destination);
  }catch(_){
    if(dirname(temporary)===parent&&temporary.startsWith(join(parent,'.g36-held-'))&&existsSync(temporary))rmSync(temporary,{recursive:true});
    throw new Error('V3_ATOMIC_PRIVATE_WRITE_FAILED');
  }
  return {status:'PRIVATE_STRUCTURAL_68_OF_70_HELD_WRITTEN',files:68,complete_profile_certified:false,deployment_prohibited:true};
}
export function writeHeldCanonicalV3(result,options){try{return write(result,options);}catch(error){throw new Error(typeof error?.message==='string'&&/^[A-Z][A-Z0-9_]{0,96}$/.test(error.message)?error.message:'V3_PRIVATE_WRITE_INPUT_FAILED');}}
