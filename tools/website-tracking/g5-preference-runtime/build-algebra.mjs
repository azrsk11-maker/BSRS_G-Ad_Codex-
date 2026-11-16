/** Exact pinned pure-algorithm extraction; the original guarded classes are never changed. */
import{readFileSync,writeFileSync,existsSync}from'node:fs';
import{createHash}from'node:crypto';
import{dirname,resolve,join}from'node:path';
import{fileURLToPath,pathToFileURL}from'node:url';
const here=dirname(fileURLToPath(import.meta.url));
const root=resolve(process.env.BSRE_SOURCE_ROOT||resolve(here,'../../..'));
const source=readFileSync(join(root,'tools/consent-retention/RetirementLedger.php'));
export const sha=b=>createHash('sha256').update(b).digest('hex');
const PIN='9675b7928ee0bae042c5f0305cdd1d73d13a343fda4dc8800d3e4d0568c1cba3';
if(sha(source)!==PIN)throw Error('PREFERENCE_ALGEBRA_SOURCE_CHANGED');
const text=source.toString(),receipts=[];
function method(name){
  const regex=new RegExp('^    (?:public|private) (?:static )?function '+name+'\\(','m'),match=regex.exec(text);
  if(!match)throw Error('PREFERENCE_ALGEBRA_METHOD_MISSING:'+name);
  const start=match.index,lineEnd=text.indexOf('\n',start),first=text.slice(start,lineEnd);
  let end;if(first.includes('}'))end=lineEnd;else{const closing=/^    \}\r?$/gm;closing.lastIndex=lineEnd;const found=closing.exec(text);if(!found)throw Error('PREFERENCE_ALGEBRA_END');end=found.index+found[0].length;}
  const raw=text.slice(start,end);return{raw,start,end};
}
function derive(name,operations){
  const input=method(name);let out=input.raw;const edits=[];
  for(const[before,after]of operations){if(out.split(before).length!==2)throw Error('PREFERENCE_ALGEBRA_ANCHOR:'+name);const offset=out.indexOf(before);out=out.replace(before,after);edits.push({offset,before,after});}
  let reverse=out;for(const{offset,before,after}of[...edits].reverse()){if(reverse.slice(offset,offset+after.length)!==after)throw Error('PREFERENCE_ALGEBRA_REVERSE');reverse=reverse.slice(0,offset)+before+reverse.slice(offset+after.length);}
  if(reverse!==input.raw)throw Error('PREFERENCE_ALGEBRA_REVERSE');
  receipts.push({method:name,source_start:input.start,source_end:input.end,input_sha256:sha(input.raw),output_sha256:sha(out),edits,reverse_verified:true});return out;
}
const parts=['<?php','declare(strict_types=1);','namespace BSRE\\ActualRetention\\PreferenceV1;',
  '/** Pure reviewed algebra only. All authority and SQL ownership live in the consuming runtime. */','final class Algebra {'];
for(const name of['rowHash','uint','clock','anchor'])parts.push(derive(name,[]));
// Select only the calculation following the original adapter's authority check.
// No original guard/class is edited, instantiated, reflected or bypassed.
const compaction=method('compactionPlan'),prefix="        $this->compactionGuard();\n";
if(compaction.raw.split(prefix).length!==2)throw Error('PREFERENCE_COMPACTION_PURE_BOUNDARY');
const compactMath=compaction.raw.slice(compaction.raw.indexOf(prefix)+prefix.length,compaction.raw.lastIndexOf('\n    }'));
parts.push('    public static function compactionPlan(array $ledger,int $now,array $trustedAnchor): array {\n'+compactMath+'\n    }');
receipts.push({method:'compactionPlan-calculation-only',source_start:compaction.start+compaction.raw.indexOf(prefix)+prefix.length,input_sha256:sha(compactMath),output_sha256:sha(compactMath),reverse_verified:true});
parts.push(derive('restorePlan',[
  ['public function restorePlan','public static function restorePlan'],
  ["$metadata['source']!=='SYNTHETIC_BSRE_LAB'","$metadata['source']!=='ACTUAL_PREFERENCE_SNAPSHOT_V1'"],
  ['RetentionInventory::plan($snapshot,$now,true);','SnapshotFormat::plan($snapshot,$now,true);'],
  ['$eligible=[];','\\BSRE\\PurposeRetention\\RetentionInventory::assertRestoreReferences($snapshot,$retired);\n        $eligible=[];']
]));
const restore=method('restorePlan'),refStart=restore.raw.indexOf("        if ($ledger['floor']['generation']>0"),refEnd=restore.raw.indexOf("        return ['version'=>1");
if(refStart<0||refEnd<refStart)throw Error('PREFERENCE_RESTORE_REFERENCE_BOUNDARY');
let refs=restore.raw.slice(refStart,refEnd);
const refRaw=refs;
refs=refs.replace('RetentionInventory::plan($snapshot,$now,true);','SnapshotFormat::plan($snapshot,$now,true);')
  .replace('$eligible=[];','\\BSRE\\PurposeRetention\\RetentionInventory::assertRestoreReferences($snapshot,$retired);\n        $eligible=[];');
parts.push('    public static function references(array $snapshot,array $ledger,int $now): array {\n'+refs+'        return $eligible;\n    }');
receipts.push({method:'restore-reference-calculation-only',source_start:restore.start+refStart,input_sha256:sha(refRaw),output_sha256:sha(refs),original_reference_math_preserved:true,reverse_verified:refs.replace('\\BSRE\\PurposeRetention\\RetentionInventory::assertRestoreReferences($snapshot,$retired);\n        $eligible=[];','$eligible=[];').replace('SnapshotFormat::plan($snapshot,$now,true);','RetentionInventory::plan($snapshot,$now,true);')===refRaw});
parts.push(derive('record',[
  ['public function record','public static function append'],
  ["$planHash=hash('sha256',json_encode($plan,JSON_THROW_ON_ERROR))","$planHash=Guard::digest($plan)"],
  ["$pending=count(array_filter($snapshot['history'],fn($row)=>in_array('bsre_consent_history:'.$row['receipt'],$plan['eligible'],true)));","$pending=count(array_filter($snapshot['history'],fn($row)=>in_array('bsre_consent_history:'.$row['receipt'],$plan['details']['eligible'],true)));"],
  ["if (!in_array('bsre_consent_history:'.$history['receipt'],$plan['eligible'],true)) continue;","if (!in_array('bsre_consent_history:'.$history['receipt'],$plan['details']['eligible'],true)) continue;"],
  ["            if ($this->db->insert($this->db->prefix.'bsre_retirement_ledger',$row)===false) throw new \\RuntimeException('LEDGER_STORAGE_UNAVAILABLE');","            $ledger['rows'][]=$row;"],
  ['        $this->query($this->db->prepare("UPDATE {$this->db->prefix}bsre_retirement_checkpoint SET sequence_no=%d,chain_hash=%s WHERE id=1",$anchor[\'sequence\'],$anchor[\'hash\']));\n',''],
  ["return self::anchor($anchor['sequence'],$anchor['hash'],$ledger['floor']);","return ['anchor'=>self::anchor($anchor['sequence'],$anchor['hash'],$ledger['floor']),'floor'=>$ledger['floor'],'rows'=>$ledger['rows']];"]
]));
const read=method('read'),begin=read.raw.indexOf("        $floor=['sequence'"),pure=read.raw.slice(begin,read.raw.lastIndexOf('\n    }'));
if(begin<0)throw Error('PREFERENCE_LEDGER_VALIDATION_ANCHOR');
parts.push('    public static function validate(array $ledger): array {\n'+
  "        Guard::keys($ledger,['anchor','floor','rows']);Guard::keys($ledger['floor'],['sequence','hash','generation','compacted_at']);\n"+
  "        if(!is_array($ledger['rows'])||!array_is_list($ledger['rows'])||count($ledger['rows'])>1000)Guard::fail('PREFERENCE_LEDGER_UNBOUNDED');\n"+
  "        $floorRow=['sequence_no'=>$ledger['floor']['sequence'],'chain_hash'=>$ledger['floor']['hash'],'generation'=>$ledger['floor']['generation'],'compacted_at'=>$ledger['floor']['compacted_at']];\n"+
  "        $checkpoint=['sequence_no'=>$ledger['anchor']['sequence'],'chain_hash'=>$ledger['anchor']['hash']];$rows=$ledger['rows'];\n"+pure+'\n    }');
receipts.push({method:'read-validation-only',source_start:read.start+begin,input_sha256:sha(pure),output_sha256:sha(pure),reverse_verified:true});
parts.push("    public static function empty(): array { $floor=['sequence'=>0,'hash'=>str_repeat('0',64),'generation'=>0,'compacted_at'=>0];return ['anchor'=>self::anchor(0,str_repeat('0',64),$floor),'floor'=>$floor,'rows'=>[]]; }",'}');
const bytes=Buffer.from(parts.join('\n')+'\n');
export const algebra={bytes,receipts,input_sha256:PIN};
if(process.argv[1]&&import.meta.url===pathToFileURL(process.argv[1]).href){
  writeFileSync(join(here,'candidate/plugin/includes/candidate/retention/PreferenceAlgebra.php'),bytes);
  writeFileSync(join(here,'ALGEBRA_DERIVATION.json'),JSON.stringify({source_path:'tools/consent-retention/RetirementLedger.php',source_sha256:PIN,output_sha256:sha(bytes),receipts,original_classes_unchanged:true,pure_algebra_not_authority:true},null,2)+'\n');
  process.stdout.write(JSON.stringify({output_sha256:sha(bytes),methods:receipts.length,reverse_verified:true})+'\n');
}
