import {readFileSync,writeFileSync,mkdirSync} from 'node:fs';
import {createHash} from 'node:crypto';
import {fileURLToPath} from 'node:url';
export const sha=b=>createHash('sha256').update(b).digest('hex');
const here=fileURLToPath(new URL('.',import.meta.url));
export function derive(input){
 const bytes=Buffer.from(input);if(sha(bytes)!=='5e9c7d4b0816f83b6349d08051a8dac552faa5af44a877966d2e042a635cb8f7')throw Error('WORKFLOW_PREIMAGE_CHANGED');
 let text=bytes.toString('utf8');const edits=[];
 function edit(a,b,label){if(text.split(a).length!==2)throw Error('ANCHOR_CHANGED:'+label);const offset=Buffer.byteLength(text.slice(0,text.indexOf(a)));edits.push({label,offset,before:a,after:b});text=text.replace(a,b);}
 edit(text.slice(0,text.indexOf('final class Workflow')),'<?php\ndeclare(strict_types=1);\nnamespace BSRE\\ActualRetention;\nuse BSRE\\ClosedRetention\\{Journal,ResourceAdapter,Authority,Admission,NoMailCopy,UnverifiedAdmission,UnverifiedNoMailCopy,NoMailCopyProof,RetirementIntent,RetirementWriter,ClosureCollectorWriter,ClosureCollection,Failure};\nrequire_once __DIR__.\'/PurgeBoundary.php\';\n','SEPARATE_HEADER');
 edit('final class Workflow','final class ActualPurgeEngine','SEPARATE_CLASS');
 edit('    public function __construct(Journal $journal, array $adapters, Authority $authority, ?Admission $admission = null,\n        ?NoMailCopy $noMailCopy = null)','    private PurgeBoundary $boundary;\n    public function __construct(Journal $journal, array $adapters, Authority $authority, Admission $admission,\n        ActualPurgeNoCopy $noMailCopy, PurgeBoundary $boundary)','TYPED_COMPOSITION');
 edit('        $this->journal = $journal;','        $this->boundary = $boundary;\n        $this->journal = $journal;','BOUNDARY');
 edit("                $record = ['plan' => $plan, 'revision' => 0, 'state' => 'PENDING', 'started_at' => $now,","                $now = time();\n                if ($now < $plan['created_at'] || $now >= $plan['expires_at']) self::fail('PLAN_EXPIRED');\n                $record = ['plan' => $plan, 'revision' => 0, 'state' => 'PENDING', 'started_at' => $now,",'FRESH_INITIAL_JOB_DEADLINE');
 edit("                        $record['intent_at'][$index] = $now;","                        $record['intent_at'][$index] = time();",'FRESH_DURABLE_INTENT');
 edit("                $record['completed_at'] = $now;","                $record['completed_at'] = time();",'FRESH_COMPLETION_TIME');
 for(const signature of ['private function proposal(string $closureId, int $now): array','private function recheck(array $plan, int $now, bool $cleanup = false, ?array $ticket = null, bool $requireIntakeAbsent = false): void','private function verifiedAdmission(int $now): array'])edit('    '+signature+'\n    {','    '+signature+'\n    {\n        $now = time();','FRESH_CLOCK_'+signature.split('(')[0]);
 // Replacements record every exact site and reverse in order; pure rules stay byte exact.
 const entries=text.split('self::lab();').length-1;if(entries!==7)throw Error('ENTRY_COUNT_CHANGED:'+entries);
 for(let i=0;i<entries;i++){const at=text.indexOf('self::lab();'),before='self::lab();',after='$this->boundary->check();';edits.push({label:'ENTRY_'+i,offset:Buffer.byteLength(text.slice(0,at)),before,after});text=text.slice(0,at)+after+text.slice(at+before.length);}
 edit('            $proofHash = NoMailCopyProof::verify($this->noMailCopy->readback($scope, $now), $scope, $now);','            $proofHash = $this->noMailCopy->verify($this->noMailCopy->readback($scope, time()), $scope, time());','ACTUAL_PREPARE_PROOF');
 edit('            $hash = NoMailCopyProof::verify($readback, $scope, $now, $cleanup);','            $hash = $this->noMailCopy->verify($readback, $scope, time(), $cleanup, $ticket);','ACTUAL_RECHECK_PROOF');
 edit("            if ($requireIntakeAbsent && $readback['row_state'] !== 'ABSENT') self::fail('NO_COPY_INTAKE_NOT_ABSENT');","            if ($requireIntakeAbsent && $this->noMailCopy->rowState($readback, $scope, time(), $cleanup, $ticket) !== 'ABSENT') self::fail('NO_COPY_INTAKE_NOT_ABSENT');",'ACTUAL_ROW_STATE');
 edit('        $hash = NoMailCopyProof::verify($this->noMailCopy->readback($scope, $now, true, $ticket), $scope, $now, true);','        $hash = $this->noMailCopy->verify($this->noMailCopy->readback($scope, time(), true, $ticket), $scope, time(), true, $ticket);','ACTUAL_CLEANUP_PROOF');
 edit("                    if ($record['steps'][$index] === 'PENDING') {","                    if ($record['steps'][$index] === 'INTENT_RECORDED' && $resource['store'] !== 'email') self::fail('ACTUAL_AMBIGUOUS_WRITE_REVIEW_REQUIRED');\n                    if ($record['steps'][$index] === 'PENDING') {",'NO_BLIND_RETRY');
 edit("        $record['state'] = 'HELD';\n        $record['completed_at'] = null;","        if ($record['state'] !== 'COMPLETE') { $record['state'] = 'HELD'; $record['completed_at'] = null; }",'IMMUTABLE_COMPLETED_DEADLINE');
 edit("'scope' => 'SYNTHETIC_CLOSED_RETENTION'","'scope' => 'ACTUAL_CLOSED_RETENTION_CANDIDATE'",'ACTUAL_SUMMARY');
 edit('\nfinal class Failure extends \\RuntimeException {}','\n','ORIGINAL_FAILURE_ONLY');
 // New derivative ends in one LF; preserve and reverse the exact old footer bytes.
 if(!text.endsWith('\n\n\n')||text.endsWith('\n\n\n\n'))throw Error('NEW_PROFILE_EOF_CHANGED');
 edits.push({label:'NEW_PROFILE_EOF',offset:Buffer.byteLength(text)-2,before:'\n\n',after:''});text=text.slice(0,-2);
 let reversed=Buffer.from(text);for(const e of [...edits].reverse()){const a=Buffer.from(e.after);if(!reversed.subarray(e.offset,e.offset+a.length).equals(a))throw Error('REVERSE_ANCHOR');reversed=Buffer.concat([reversed.subarray(0,e.offset),Buffer.from(e.before),reversed.subarray(e.offset+a.length)]);}
 if(!reversed.equals(bytes))throw Error('REVERSE_FAILED');return {bytes:Buffer.from(text),receipt:{preimage:sha(bytes),output:sha(Buffer.from(text)),reverse_verified:true,edits}};
}
if(process.argv[1]===fileURLToPath(import.meta.url)){
 const source=process.argv[2];if(!source)throw Error('EXACT_SOURCE_ROOT_REQUIRED');
 const out=derive(readFileSync(source+'/tools/closed-enquiry-retention/Workflow.php'));
 mkdirSync(here+'code',{recursive:true});writeFileSync(here+'code/ActualPurgeEngine.php',out.bytes);writeFileSync(here+'DERIVATION.json',JSON.stringify(out.receipt,null,2)+'\n');
 const capture=readFileSync(source+'/tools/website-tracking/g5-runtime-ports/candidate/plugin/includes/candidate/closed-enquiry-retention/ActualCaptureResource.php');
 if(sha(capture)!=='30685843d5b56551e15984150d7ec2ba83d9c4152b4a154ca40efe71bedbf177')throw Error('CAPTURE_PREIMAGE_CHANGED');
 let c=capture.toString('utf8');const ce=[];
 for(const [a,b] of [["require_once __DIR__ . '/ActualJournal.php';","require_once __DIR__ . '/ActualPurgeJournal.php';"],['final class ActualCaptureResource','final class ActualPurgeCaptureResource'],['private ActualJournal $journal','private ActualPurgeJournal $journal'],['private RuntimePolicy $policy, private CaptureProducer $producer)','private RuntimePolicy $policy, private CanonicalCaptureProducer $producer, private PurgeBoundary $boundary)'],["        $this->table=$policy->prefix.'bsre_consent_captures'; $this->guard();","        if (!$boundary->boundTo($db,$producer,$policy) || $journal->purgeBoundary()!==$boundary) RuntimePolicy::fail('ACTUAL_PURGE_CAPTURE_COMPOSITION_CONFLICT');\n        $this->table=$policy->prefix.'bsre_consent_captures'; $this->guard();"],['    private function guard(): void',"    public function boundTo(ActualPurgeJournal $j,PurgeBoundary $b,RuntimePolicy $p): bool { return $this->journal===$j && $this->boundary===$b && $this->policy===$p; }\n    private function guard(): void"],['        $this->journal->assertProviderCustody($this->db,$this->activeRequest,$this->mutating);',"        $this->journal->assertProviderCustody($this->db,$this->activeRequest,$this->mutating);\n        $this->boundary->check('capture_sql_boundary');"]]){
  if(c.split(a).length!==2)throw Error('CAPTURE_ANCHOR_CHANGED');const offset=Buffer.byteLength(c.slice(0,c.indexOf(a)));ce.push({offset,before:a,after:b});c=c.replace(a,b);
 }
 let cr=Buffer.from(c);for(const e of [...ce].reverse())cr=Buffer.concat([cr.subarray(0,e.offset),Buffer.from(e.before),cr.subarray(e.offset+Buffer.byteLength(e.after))]);if(!cr.equals(capture))throw Error('CAPTURE_REVERSE_FAILED');
 writeFileSync(here+'code/ActualPurgeCaptureResource.php',c);writeFileSync(here+'CAPTURE_DERIVATION.json',JSON.stringify({preimage:sha(capture),output:sha(c),reverse_verified:true,edits:ce},null,2)+'\n');
 const jbytes=readFileSync(source+'/tools/website-tracking/g5-receiver-runtime/candidate/plugin/includes/candidate/closed-enquiry-retention/ActualReceiverJournal.php');
 if(sha(jbytes)!=='b6a4a8b011e6215237360637eabe6db38ae46494a184e6fb335041169f9344f9')throw Error('JOURNAL_PREIMAGE_CHANGED');
 let j=jbytes.toString('utf8');const je=[];for(const [a,b] of [
  ['final class ActualReceiverJournal','final class ActualPurgeJournal'],
  ['private ?CanonicalCaptureProducer $receiverProducer = null)','private ?CanonicalCaptureProducer $receiverProducer, private PurgeBoundary $purgeBoundary)'],
  ['    private function query(string $sql): int\n    {\n        $this->guard();',"    public function purgeBoundary(): PurgeBoundary { return $this->purgeBoundary; }\n    public function purgeAuthority(): OwnerAuthority { return $this->authority; }\n    private function query(string $sql): int\n    {\n        $this->guard();\n        $this->purgeBoundary->check('journal_sql_boundary');"],
  ["        $receiverProducer->assertCurrent($db);","        if (!$purgeBoundary->boundTo($db,$receiverProducer,$policy)) RuntimePolicy::fail('ACTUAL_PURGE_JOURNAL_COMPOSITION_CONFLICT');\n        $receiverProducer->assertCurrent($db);"],
  ["        $next=$record; $next['revision']++; $s['jobs'][$digest]=$next; $this->write($s);","        if ($old!==null && ($old['completed_at']??null)!==null && ($record['completed_at']??null)!==$old['completed_at']) RuntimePolicy::fail('ACTUAL_PURGE_COMPLETION_DEADLINE_CHANGED');\n        $next=$record; $next['revision']++; $s['jobs'][$digest]=$next; $this->write($s);"],
  ["            $this->custody->advance($before, ['revision'=>$revision,'hash'=>$hash]);","            $transition=['before'=>$before,'after'=>['revision'=>$revision,'hash'=>$hash],'encrypted_body'=>$body];\n            $this->purgeBoundary->check('journal_anchor_advance',null,$transition);\n            $this->custody->advance($before, ['revision'=>$revision,'hash'=>$hash]);\n            $this->purgeBoundary->check('journal_anchor_advance:readback',null,$transition);"]
 ]){if(j.split(a).length!==2)throw Error('JOURNAL_ANCHOR_CHANGED');const offset=Buffer.byteLength(j.slice(0,j.indexOf(a)));je.push({offset,before:a,after:b});j=j.replace(a,b);}
 let jr=Buffer.from(j);for(const e of [...je].reverse())jr=Buffer.concat([jr.subarray(0,e.offset),Buffer.from(e.before),jr.subarray(e.offset+Buffer.byteLength(e.after))]);if(!jr.equals(jbytes))throw Error('JOURNAL_REVERSE_FAILED');
 writeFileSync(here+'code/ActualPurgeJournal.php',j);writeFileSync(here+'JOURNAL_DERIVATION.json',JSON.stringify({preimage:sha(jbytes),output:sha(j),reverse_verified:true,edits:je},null,2)+'\n');
}
