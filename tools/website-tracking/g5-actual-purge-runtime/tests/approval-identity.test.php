<?php
declare(strict_types=1);
if(PHP_SAPI!=='cli')throw new RuntimeException('CLI_ONLY');
require_once __DIR__.'/approval-identity.php';
require_once dirname(__DIR__,3).'/closed-enquiry-retention/Workflow.php';
require_once dirname(__DIR__,2).'/g5-receiver-runtime/candidate/plugin/includes/candidate/receiver/ReceiverContracts.php';
use BSRE\PurgeNative\ApprovalIdentity as I;
use BSRE\ActualRetention\ReceiverV1\Guard;
$checks=0;
function verify(bool $ok):void {global $checks;$checks++;if(!$ok)throw new RuntimeException('APPROVAL_IDENTITY_CONTRACT_FAILED');}
$grant=['actor'=>'wp-user:7','action'=>'PURGE','plan_digest'=>str_repeat('a',64),'approved_at'=>1700000000,'approval_expires_at'=>1700000900];
$roundtrip=json_decode(Guard::canonical($grant),true,32,JSON_THROW_ON_ERROR);
verify($roundtrip!==$grant); // Reproduces the old order-sensitive PHP comparison.
verify(I::same($roundtrip,$grant));verify(I::same($grant,$roundtrip));
verify(I::same(array_reverse($grant,true),$grant));
foreach($grant as $field=>$value){
    $changed=$roundtrip;$changed[$field]=is_int($value)?$value+1:$value.'x';verify(!I::same($changed,$grant));
    $wrongType=$roundtrip;$wrongType[$field]=is_int($value)?(string)$value:1;verify(!I::same($wrongType,$grant));
    $missing=$roundtrip;unset($missing[$field]);verify(!I::same($missing,$grant));
}
$extra=$roundtrip;$extra['unreviewed']=true;verify(!I::same($extra,$grant));
$float=$roundtrip;$float['approved_at']=1700000000.0;verify(!I::same($float,$grant));
foreach([[null,$grant],[array_values($roundtrip),$grant],[$grant,null]] as [$candidate,$known])verify(!I::same($candidate,$known));
verify($grant['actor']==='wp-user:7'&&array_keys($grant)[0]==='actor');
echo 'Approval identity contract PASS ('.$checks.' assertions; no WordPress, database or provider started).' ."\n";
