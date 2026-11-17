<?php
declare(strict_types=1);
namespace {if(PHP_SAPI!=='cli'||defined('ABSPATH'))throw new \RuntimeException('G39_PURE_CONTRACT_CONTEXT_REQUIRED');define('ARRAY_A','ARRAY_A');}
namespace BSRE\ActualRetention\PreferenceV1 {
    final class Policy {}
    final class Guard {public static function fail(string $code):never {throw new \RuntimeException($code);}}
}
namespace BSRE\ActualRetention\HistoryLocalV1 {
    use BSRE\ActualRetention\PreferenceV1 as V;
    // Only the exact pinned assertCurrent and cleanup bodies are executed. All SQL is an in-memory script.
    final class LocalHistoryObserver {
        public static bool $stale=false;
        public static function wholeObservationDeadline(int $started,int $snapshot,int $observed,int $elapsed):int {
            if($started!==100||$snapshot!==101||$elapsed!==1)throw new \RuntimeException('G39_UNIT_CLOCK_RESET');
            if(self::$stale)throw new \RuntimeException('G39_OBSERVATION_SNAPSHOT_STALE');return 130;
        }
    }
    final class ScriptedDatabase {
        public string $last_error='';public bool $suppressed=false;public array $queries=[];
        public bool $marker=true;public bool $transaction=true;public bool $readonly=true;
        public function __construct(public string $fault=''){}
        public function suppress_errors(bool $next):bool {$old=$this->suppressed;$this->suppressed=$next;return$old;}
        public function query(string $sql):int|false {
            $this->queries[]=$sql;
            if($sql==='RELEASE SAVEPOINT g39_unit_marker'){
                if($this->fault==='release_throw')throw new \RuntimeException('UNIT_RELEASE_THROW');
                if(!$this->marker||$this->fault==='release_error'){$this->last_error='missing marker';return$this->fault==='release_error'?0:false;}
                $this->marker=false;return 0;
            }
            if($sql==='SAVEPOINT g39_unit_marker'){
                if($this->fault==='recreate_throw')throw new \RuntimeException('UNIT_RECREATE_THROW');
                if(in_array($this->fault,['recreate_false','recreate_error','cleanup_false'],true)){$this->last_error='cannot recreate';return$this->fault==='recreate_error'?0:false;}
                $this->marker=true;return 0;
            }
            if($sql==='ROLLBACK'){
                if($this->fault==='cleanup_false'){$this->last_error='rollback failed';return false;}
                $this->transaction=false;$this->marker=false;return 0;
            }
            if($sql==='SET SESSION TRANSACTION READ WRITE'){$this->readonly=false;return 0;}
            throw new \RuntimeException('UNIT_UNEXPECTED_SQL');
        }
        public function get_row(string $sql,string $shape):array {
            if($sql!=='SELECT CONNECTION_ID() AS connection_id,@@session.in_transaction AS in_transaction,@@session.tx_read_only AS tx_read_only'||$shape!=='ARRAY_A')throw new \RuntimeException('UNIT_UNEXPECTED_FACT_SQL');
            return['connection_id'=>'7','in_transaction'=>$this->transaction?'1':'0','tx_read_only'=>$this->readonly?'1':'0'];
        }
    }
    final class ScriptedJournal {public bool $quarantined=false;public function quarantineLocalHistoryRead(ScriptedDatabase $db):void {$this->quarantined=true;}}
    $file=dirname(__DIR__).'/history/LocalHistoryObserver.php';$source=file_get_contents($file);
    if(!is_string($source)||hash('sha256',$source)!=='648b6851f5e0a012b27369b5de1dde3fe016a7171828937be3a8c0843f411be7')throw new \RuntimeException('G39_UNIT_SOURCE_PIN_CHANGED');
    $a=strpos($source,'    public function assertCurrent(?V\\Policy $preference=null): void {');$b=strpos($source,"}\n\n/** Current local state only.",$a===false?0:$a);
    $c=strpos($source,'                $clean=true;');$d=strpos($source,"            }\n        });",$c===false?0:$c);
    if($a===false||$b===false||$c===false||$d===false)throw new \RuntimeException('G39_UNIT_EXACT_EXTRACTION_REQUIRED');
    $method=substr($source,$a,$b-$a);$cleanup=substr($source,$c,$d-$c);
    eval('namespace BSRE\\ActualRetention\\HistoryLocalV1;use BSRE\\ActualRetention\\PreferenceV1 as V; final class MarkerHarness {
        private string $savepoint="g39_unit_marker";private int $startedAt=100;private int $snapshotAt=101;
        public array $events=[];public bool $identityFails=false;public function __construct(public ScriptedDatabase $db,public ScriptedJournal $journal){}
        private function facts(?V\\Policy $p):void {$this->events[]="full_facts";}
        private function sessionFacts():void {$this->events[]="fresh_identity";if($this->identityFails)V\\Guard::fail("G39_SNAPSHOT_REPLACED");}
        private function elapsedMs():int {return 1;}
        '.$method.'
        public function attempt():void {$started=true;$changedReadOnly=true;$connection="7";$originalReadOnly="0";try{$this->assertCurrent();}finally{'.$cleanup.'}}
    }');
    $cases=0;
    $check=static function(bool $ok):void {if(!$ok)throw new \RuntimeException('G39_UNIT_ASSERTION_FAILED');};
    $run=static function(string $fault,?string $expected,bool $missing=false,bool $identity=false,bool $stale=false)use($check,&$cases):array {
        $db=new ScriptedDatabase($fault);$db->marker=!$missing;$journal=new ScriptedJournal();$h=new MarkerHarness($db,$journal);$h->identityFails=$identity;LocalHistoryObserver::$stale=$stale;$caught=null;
        try{$h->attempt();}catch(\RuntimeException $e){$caught=$e->getMessage();}finally{LocalHistoryObserver::$stale=false;}
        $check($caught===$expected);$check($db->suppressed===false);$check($h->events[0]==='full_facts');
        $check(in_array('ROLLBACK',$db->queries,true)&&in_array('SET SESSION TRANSACTION READ WRITE',$db->queries,true));
        if($fault!=='cleanup_false'){$check(!$db->transaction&&!$db->readonly&&!$journal->quarantined);}else $check($journal->quarantined);
        $cases++;return[$db,$h,$journal];
    };
    [$db,$h]=$run('',null);$check($db->queries===['RELEASE SAVEPOINT g39_unit_marker','SAVEPOINT g39_unit_marker','ROLLBACK','SET SESSION TRANSACTION READ WRITE']);$check($h->events===['full_facts','fresh_identity']);
    [$db]=$run('','G39_SNAPSHOT_REPLACED',true);$check(!in_array('SAVEPOINT g39_unit_marker',$db->queries,true));
    [$db]=$run('release_error','G39_SNAPSHOT_REPLACED');$check(!in_array('SAVEPOINT g39_unit_marker',$db->queries,true));
    [$db]=$run('release_throw','UNIT_RELEASE_THROW');$check(!in_array('SAVEPOINT g39_unit_marker',$db->queries,true));
    $run('recreate_false','G39_SNAPSHOT_REPLACED');
    $run('recreate_error','G39_SNAPSHOT_REPLACED');
    $run('recreate_throw','UNIT_RECREATE_THROW');
    $run('','G39_SNAPSHOT_REPLACED',false,true);
    $run('','G39_OBSERVATION_SNAPSHOT_STALE',false,false,true);
    $run('cleanup_false','G39_READ_CLEANUP_UNCONFIRMED');
    $check($cases===10);
    echo "Snapshot marker contract PASS (10 cases; no WordPress, database or provider started).\n";
}
