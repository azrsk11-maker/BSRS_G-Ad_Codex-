/** Synthetic local file readback only. No native runtime or provider acceptance. */
import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync,writeFileSync,mkdirSync,mkdtempSync,rmSync} from 'node:fs';
import {resolve,join,dirname,basename} from 'node:path';
import {tmpdir} from 'node:os';
import {pathToFileURL,fileURLToPath} from 'node:url';
import {physicalIdentity,FOUR} from './physical-identity.mjs';
const source=resolve(process.env.BSRE_SOURCE_ROOT||fileURLToPath(new URL('../../../',import.meta.url)));
const scope=JSON.parse(readFileSync(new URL('./CURRENT_SCOPE.json',import.meta.url)));
const {syntheticInput}=await import(pathToFileURL(join(source,'tools/website-tracking/coupled-package-v3/synthetic-input.mjs')));
const {composeCoupledCanonicalLeaseV3,digest}=await import(pathToFileURL(join(source,'tools/website-tracking/coupled-package-v3/compose-v3.mjs')));
const {buildG36Native}=await import(pathToFileURL(join(source,'tools/website-tracking/coupled-package-v3/build-native.mjs')));
const result=await composeCoupledCanonicalLeaseV3(await syntheticInput({source_root:source})),native=await buildG36Native({source_root:source});
function fixture(){
  const root=mkdtempSync(join(tmpdir(),'g36-current-physical-'));
  const site=[...result.files].filter(([path])=>path.startsWith('site/')).map(([path,raw])=>[path.slice(5),raw]);
  for(const [path,raw]of site){const target=join(root,path);mkdirSync(dirname(target),{recursive:true});writeFileSync(target,raw);}
  writeFileSync(join(root,'BUILD.json'),JSON.stringify({profile:result.public_summary.profile,files:site.sort(([a],[b])=>a.localeCompare(b)).map(([path,raw])=>({path,sha256:digest(raw)}))},null,2)+'\n');
  writeFileSync(join(root,'NATIVE_BUILD.json'),JSON.stringify({schema:'bsre-g36-native-derivation-v1',profile:result.public_summary.profile,
    synthetic_only:true,deployment_prohibited:true,source_bindings:result.private_manifest.bindings,site_files:67,source_members:64,
    inherited_checks:native.inherited_checks,receipts:native.receipts,runtime_checks_executed:false,
    contact_modes:['hub','off-plan','resale','rent','sell','let']},null,2)+'\n');
  return root;
}
function cleanup(root){assert.equal(dirname(resolve(root)),resolve(tmpdir()));assert(basename(root).startsWith('g36-current-physical-'));rmSync(root,{recursive:true});}
test('physical67/source64 current readback matches sealed fresh derivation exactly',()=>{
  const root=fixture();try{assert.deepEqual(physicalIdentity(root,{context:scope.expected_receipt.retention_context}),scope.expected_receipt);}finally{cleanup(root);}
});
test('changed physical child is rejected rather than echoing a stale BUILD identity',()=>{
  const root=fixture();try{writeFileSync(join(root,FOUR[0]),Buffer.concat([readFileSync(join(root,FOUR[0])),Buffer.from('\n')]));assert.throws(()=>physicalIdentity(root),/SITE_HASH/);}finally{cleanup(root);}
});
test('self-rehashed physical child/BUILD still fails the independently bound source manifest',()=>{
  const root=fixture();try{
    const path=join(root,FOUR[0]),raw=Buffer.concat([readFileSync(path),Buffer.from('\n')]);writeFileSync(path,raw);
    const build=JSON.parse(readFileSync(join(root,'BUILD.json')));build.files.find(row=>row.path===FOUR[0]).sha256=digest(raw);writeFileSync(join(root,'BUILD.json'),JSON.stringify(build));
    assert.throws(()=>physicalIdentity(root),/SOURCE_HASH/);
  }finally{cleanup(root);}
});
test('path traversal, duplicate sites and stale native M binding fail closed',()=>{
  for(const mutate of [b=>b.files[0].path='../escape',b=>b.files[1]=b.files[0]]){
    const root=fixture();try{const build=JSON.parse(readFileSync(join(root,'BUILD.json')));mutate(build);writeFileSync(join(root,'BUILD.json'),JSON.stringify(build));assert.throws(()=>physicalIdentity(root),/PATH|DUPLICATE/);}finally{cleanup(root);}
  }
  const root=fixture();try{const build=JSON.parse(readFileSync(join(root,'NATIVE_BUILD.json')));build.source_bindings.M='0'.repeat(64);writeFileSync(join(root,'NATIVE_BUILD.json'),JSON.stringify(build));assert.throws(()=>physicalIdentity(root),/NATIVE_BINDINGS/);}finally{cleanup(root);}
});
