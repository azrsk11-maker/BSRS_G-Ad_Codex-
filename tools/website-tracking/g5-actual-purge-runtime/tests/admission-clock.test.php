<?php
declare(strict_types=1);
if(PHP_SAPI!=='cli')throw new RuntimeException('CLI_ONLY');
require_once dirname(__DIR__,3).'/closed-enquiry-retention/Workflow.php';
require_once dirname(__DIR__).'/code/ActualPurgeEngine.php';

/** Read-only unit seam: invoke only admission-value validation, never a workflow/mutation. */
final class ClockAdmissionFixture implements \BSRE\ClosedRetention\Admission {
    public function __construct(private string $mode){}
    public function readback(int $now):?array {
        if($this->mode==='after_io')sleep(1); // Real elapsed time, no clock override.
        $observed=time()+($this->mode==='future'?5:($this->mode==='expired'?-301:0));
        $gate=['contract'=>'bsre-retention-admission-v1','mode'=>'ENFORCED','generation'=>str_repeat('a',64),
            'activated_at'=>time()-1000,'max_age_seconds'=>900,'audience'=>str_repeat('b',64)];
        return ['wp'=>$gate+['routes_installed'=>true,'store_installed'=>true],'receiver'=>$gate,
            'source_hashes'=>['wp'=>str_repeat('c',64),'receiver'=>str_repeat('d',64)],
            'restore_policy_hash'=>str_repeat('e',64),'evidence_reference'=>'SYNTHETIC_CLOCK_UNIT',
            'evidence_hash'=>str_repeat('f',64),'observed_at'=>$observed,'expires_at'=>$observed+($this->mode==='overlong'?301:300)];
    }
}
$class=new ReflectionClass(\BSRE\ActualRetention\ActualPurgeEngine::class);
$validator=$class->getMethod('verifiedAdmission');$property=$class->getProperty('admission');
foreach(['after_io','future','expired','overlong'] as $mode){
    $engine=$class->newInstanceWithoutConstructor();$property->setValue($engine,new ClockAdmissionFixture($mode));$code=null;
    try{$result=$validator->invoke($engine,time());}catch(\BSRE\ClosedRetention\Failure $error){$code=$error->getMessage();}
    if($mode==='after_io'?$code!==null:$code!=='ADMISSION_STALE')throw new RuntimeException('ADMISSION_CLOCK_CONTRACT_FAILED');
}
echo "Admission clock contract PASS (4 cases; no WordPress, database or provider started).\n";
