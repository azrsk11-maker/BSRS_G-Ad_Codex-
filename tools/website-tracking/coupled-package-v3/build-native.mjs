/** Explicit G36 synthetic-lab derivatives. No source mutation, credentials or deployment authority. */
import {readFileSync} from 'node:fs';
import {createHash} from 'node:crypto';
import {resolve,join} from 'node:path';
import {fileURLToPath,pathToFileURL} from 'node:url';
export const PROFILE='G36_COUPLED_CANONICAL_LEASE_V3';
export const PREIMAGES=Object.freeze({
  bootstrap:'db5ed1a8a675e86eea78a208e4ea58eb52cde5d54f52f55d0f6c942c1029dd4b',
  route:'63c276204010640d7286553827a6f99262cc9f6622381ba18b0ac1c6d893b0b4',
  purpose:'e7d356059594bd9447b707dee77999c039a92df90fc3cb3a076097ec7c7fee1a',
  route_builder:'defa12ce565c285a46c6b09440984423c6f4adb0d46c896af018f8e0021e064a',
  postlude:'b696b5aee72e1d32303ea9d4d69c6e35327ffa7baea03f642ae456780b36ffc4'
});
export const digest=bytes=>createHash('sha256').update(bytes).digest('hex');
const need=(ok,code)=>{if(!ok)throw new Error(code);};
// Every edit carries its exact intermediate byte offset and reverse preimage.
export function deriveNative(bytes,pin,operations){
  need(Buffer.isBuffer(bytes)&&digest(bytes)===pin,'G36_NATIVE_PREIMAGE_CHANGED');
  let out=Buffer.from(bytes);const edits=[];
  for(const {before,after,count=1,label} of operations){
    need(typeof before==='string'&&before.length>0&&typeof after==='string'&&before!==after,'G36_NATIVE_EDIT_INVALID');
    const from=Buffer.from(before),to=Buffer.from(after),offsets=[];
    for(let pos=0;(pos=out.indexOf(from,pos))!==-1;pos+=from.length)offsets.push(pos);
    need(offsets.length===count,'G36_NATIVE_ANCHOR_CHANGED:'+label);
    // Right-to-left offsets remain valid within this explicitly counted operation.
    for(const offset of offsets.reverse()){
      need(out.subarray(offset,offset+from.length).equals(from),'G36_NATIVE_EDIT_SLICE_CHANGED');
      out=Buffer.concat([out.subarray(0,offset),to,out.subarray(offset+from.length)]);
      edits.push({label,offset,before,after});
    }
  }
  const receipt={input_sha256:pin,output_sha256:digest(out),edits,reverse_verified:false};
  need(reverseNative(out,receipt).equals(bytes),'G36_NATIVE_REVERSE_FAILED');receipt.reverse_verified=true;
  return {bytes:out,receipt};
}
export function reverseNative(bytes,receipt){
  need(Buffer.isBuffer(bytes)&&digest(bytes)===receipt.output_sha256,'G36_NATIVE_OUTPUT_CHANGED');
  let out=Buffer.from(bytes);
  for(const {offset,before,after} of [...receipt.edits].reverse()){
    const from=Buffer.from(after);need(out.subarray(offset,offset+from.length).equals(from),'G36_NATIVE_REVERSE_SLICE_CHANGED');
    out=Buffer.concat([out.subarray(0,offset),Buffer.from(before),out.subarray(offset+from.length)]);
  }
  need(digest(out)===receipt.input_sha256,'G36_NATIVE_REVERSE_PREIMAGE_CHANGED');return out;
}
const move=(before,after,count=1)=>({before,after,count,label:before});
export async function buildG36Native({source_root=resolve(fileURLToPath(new URL('../../../',import.meta.url)))}={}){
  const root=resolve(source_root),read=p=>readFileSync(join(root,p));
  need(digest(read('tools/website-tracking/canonical-lease/build-route-native.mjs'))===PREIMAGES.route_builder &&
    digest(read('tools/website-tracking/canonical-lease/route-custody-postlude.php'))===PREIMAGES.postlude,'G36_NATIVE_GENERATOR_CHANGED');
  const {buildCanonicalRouteNative}=await import(pathToFileURL(join(root,'tools/website-tracking/canonical-lease/build-route-native.mjs')).href);
  const originals={bootstrap:read('tools/staging-lab/canonical-lease-bootstrap-native.php'),route:buildCanonicalRouteNative().php,purpose:read('tools/staging-lab/canonical-purpose-native.php')};
  const bootstrap=deriveNative(originals.bootstrap,PREIMAGES.bootstrap,[
    move('/opt/lab/g35','/opt/lab/g36',2),move('/tmp/g35','/tmp/g36',2),
    move("'G35_CANONICAL_LEASE_CODE_ONLY'","'"+PROFILE+"'"),
    move("count($build['files'])===58","count($build['files'])===67"),
    move("$counts===['profile'=>1,'files'=>1,'path'=>58,'sha256'=>58] || ($counts['profile']??0)===1 && ($counts['files']??0)===1 && ($counts['path']??0)===58 && ($counts['sha256']??0)===58",
      "$counts===['profile'=>1,'files'=>1,'path'=>67,'sha256'=>67] || ($counts['profile']??0)===1 && ($counts['files']??0)===1 && ($counts['path']??0)===67 && ($counts['sha256']??0)===67"),
    move("count($manifest['files'])===55","count($manifest['files'])===64"),
    // Legacy check names are retained byte-for-byte; their expressions verify the selected 67-file tree.
    move("count($site['files'])===58","count($site['files'])===67",2),
    move('synthetic_g35_bootstrap_probe','synthetic_g36_bootstrap_probe'),
    move("'phase'=>'g35_canonical_lease_bootstrap'","'phase'=>'g36_canonical_lease_bootstrap'")
  ]);
  const route=deriveNative(originals.route,PREIMAGES.route,[
    move('/opt/lab/g35','/opt/lab/g36',3),move('/tmp/g35','/tmp/g36'),
    move("$wpdb->prefix='g35_'.$canonicalMode.'_synthetic_';","$wpdb->prefix='g36_'.$canonicalMode.'_synthetic_';"),
    move("$wpdb->prefix='g35_foreign_synthetic_';","$wpdb->prefix='g36_foreign_synthetic_';"),
    move("'phase'=>'g35_route_context'","'phase'=>'g36_route_context'"),
    move("'phase'=>'g35_canonical_custody'","'phase'=>'g36_canonical_custody'"),
    move("$GLOBALS['wp_rewrite']->set_permalink_structure('/%postname%/');",
      "$GLOBALS['wp_rewrite']->set_permalink_structure('/%postname%/');\nrequire_once '/opt/lab/g36/contact-abi.php';\n\\BSRE\\G36Native\\reconcile();")
  ]);
  const purpose=deriveNative(originals.purpose,PREIMAGES.purpose,[move('/opt/lab/g35','/opt/lab/g36'),move('/tmp/g35','/tmp/g36')]);
  const files=new Map([['bootstrap-native.php',bootstrap.bytes],['route-native.php',route.bytes],['purpose-native.php',purpose.bytes]]);
  return {files,receipts:{bootstrap:bootstrap.receipt,route:route.receipt,purpose:purpose.receipt},
    profile:PROFILE,preimages:{...PREIMAGES},inherited_checks:{route:101,forwards:20,custody_routes:63,custody_loss:69,purpose:43},
    original_check_names_preserved:true,production_authorized:false,native_executed:false};
}
