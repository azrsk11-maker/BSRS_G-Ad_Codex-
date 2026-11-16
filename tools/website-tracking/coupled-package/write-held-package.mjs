import {mkdirSync, writeFileSync, renameSync, rmSync, existsSync, lstatSync, realpathSync} from 'node:fs';
import {resolve, dirname, relative, isAbsolute, join} from 'node:path';
import {randomUUID} from 'node:crypto';
import {memberMap, digest, CONTRACT} from './compose.mjs';
const need = (ok,code) => { if (!ok) throw new Error(code); };
const nested = (a,b) => { const r=relative(a,b); return r === '' || (!r.startsWith('..') && !isAbsolute(r)); };
/** Explicit private destination only; no fixture/site/installer or deployment destination. */
function writeBound(result, options) {
  need(options?.visibility === 'PRIVATE_OFFLINE_ONLY', 'PRIVATE_OUTPUT_REQUIRED');
  need(result?.public_summary?.deployment_prohibited === true && result.public_summary.complete_profile_certified === false &&
    result.private_manifest?.classification === 'PRIVATE_DO_NOT_PUBLISH', 'HELD_RESULT_REQUIRED');
  const destination=resolve(options.destination), parent=dirname(destination);
  need(!existsSync(destination) && existsSync(parent), 'NEW_OUTPUT_DIRECTORY_REQUIRED');
  need(Array.isArray(options.input_roots) && options.input_roots.length >= 2, 'INPUT_ROOTS_REQUIRED');
  let at=parent;
  while (true) { const s=lstatSync(at); need(s.isDirectory()&&!s.isSymbolicLink(), 'OUTPUT_PARENT_LINK_PROHIBITED');
    const next=dirname(at); if(next===at)break; at=next; }
  need(realpathSync(parent).toLowerCase()===parent.toLowerCase(),'OUTPUT_PARENT_REDIRECTED');
  for(const root of options.input_roots) { const input=realpathSync(resolve(root));
    need(!nested(input.toLowerCase(),destination.toLowerCase())&&!nested(destination.toLowerCase(),input.toLowerCase()),'OUTPUT_ROOT_OVERLAP'); }
  const entries=[...result.files].map(([path,bytes])=>({path,bytes})); memberMap(entries);
  need(entries.length===result.private_manifest.outputs.length,'OUTPUT_MANIFEST_COUNT');
  for(const row of result.private_manifest.outputs) need(result.files.has(row.path)&&digest(result.files.get(row.path))===row.sha256,
    'OUTPUT_MANIFEST_CHANGED');
  need(entries.every(r=>CONTRACT.required_outputs.includes(r.path)),'OUTPUT_NOT_SELECTED');
  const temporary=join(parent,'.held-package-'+randomUUID());
  try {
    mkdirSync(temporary);
    for(const {path,bytes} of entries) { const file=join(temporary,...path.split('/')); mkdirSync(dirname(file),{recursive:true}); writeFileSync(file,bytes,{flag:'wx'}); }
    writeFileSync(join(temporary,'PRIVATE_MANIFEST.json'),JSON.stringify(result.private_manifest,null,2)+'\n',{flag:'wx'});
    writeFileSync(join(temporary,'PUBLIC_SUMMARY.json'),JSON.stringify(result.public_summary,null,2)+'\n',{flag:'wx'});
    renameSync(temporary,destination);
  } catch (_) {
    // Only the newly allocated checked sibling is eligible for removal.
    if(dirname(temporary)===parent && temporary.startsWith(join(parent,'.held-package-')) && existsSync(temporary)) rmSync(temporary,{recursive:true});
    throw new Error('ATOMIC_PRIVATE_WRITE_FAILED');
  }
  return {status:'PRIVATE_OFFLINE_PACKAGE_WRITTEN',output_count:entries.length,deployment_prohibited:true};
}
export function writeHeldPackage(result, options) {
  try { return writeBound(result,options); } catch(error) {
    throw new Error(typeof error?.message === 'string' && /^[A-Z][A-Z0-9_]{0,96}$/.test(error.message)
      ? error.message : 'PRIVATE_PACKAGE_WRITE_INPUT_FAILED');
  }
}
