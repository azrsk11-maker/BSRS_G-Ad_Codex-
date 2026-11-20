<?php
declare(strict_types=1);
namespace BSRE\RetentionReview\PerChoice\PurposeV1;
require_once __DIR__.'/PerChoicePlanner.php';
use BSRE\RetentionReview\PerChoice\PerChoicePlanner as Base;
use BSRE\RetentionReview\RetentionInventory;

/** Pure, bounded extension for actual persisted purpose captures. No source/authentication authority. */
final class PurposeChoicePlanner {
    public const EXTRA=['purpose_version','purpose_hash','purpose_record_hash','purpose_json'];
    public const SOURCE_ORIGIN='https://blackswanrealestate.ae';
    private const WINDOW=15552000;
    private static function need(bool $ok): void {if(!$ok)throw new \InvalidArgumentException('PURPOSE_CHOICE_LINEAGE_UNRESOLVED');}
    private static function keys($value,array $expected): void {
        self::need(is_array($value));$actual=array_keys($value);sort($actual);sort($expected);self::need($actual===$expected);
    }
    private static function object($value,array $expected): void {
        self::need($value instanceof \stdClass);self::keys(get_object_vars($value),$expected);
    }
    private static function canonical($value): string {return json_encode($value,JSON_THROW_ON_ERROR|JSON_UNESCAPED_SLASHES|JSON_UNESCAPED_UNICODE);}
    /** Base digest bounds scalar-only inputs; JSON roundtrip detaches PHP references without changing supported scalar types. */
    private static function copy(array $value): array {
        Base::digest($value);
        return json_decode(json_encode($value,JSON_THROW_ON_ERROR|JSON_PRESERVE_ZERO_FRACTION),true,64,JSON_THROW_ON_ERROR);
    }
    private static function text($value): bool {
        if(!is_string($value)||trim($value)===''||strlen($value)>1024||preg_match('//u',$value)!==1||preg_match('/[\p{C}]/u',$value))return false;
        preg_match_all('/./us',$value,$characters);$units=0;
        foreach($characters[0]as$character)$units+=strlen($character)===4?2:1;
        return $units<=256;
    }
    private static function url($value,bool $empty=false): void {
        self::need(is_string($value)&&strlen($value)<=2000&&!preg_match('/[\\\\\s\x00-\x1f\x7f]/u',$value));
        if($value===''&&$empty)return;$p=parse_url($value);
        self::need(is_array($p)&&in_array($p['scheme']??'', ['http','https'],true)&&preg_match('/^[a-z0-9.-]+$/iD',$p['host']??'')===1&&!array_intersect(['query','fragment','user','pass'],array_keys($p)));
    }
    /** Validate every nested field; record hashes detect consistency, never hostile-owner changes. */
    private static function record(array $capture): \stdClass {
        self::need(in_array($capture['purpose_version'],[1,'1'],true)); // Legacy/unknown cannot establish complete purpose coverage.
        foreach(['purpose_hash','purpose_record_hash']as$key)self::need(is_string($capture[$key])&&preg_match('/^[a-f0-9]{64}$/D',$capture[$key])===1);
        self::need(is_string($capture['purpose_json'])&&strlen($capture['purpose_json'])<=48000);
        self::need(hash_equals(hash('sha256',$capture['fingerprint']."\n".$capture['purpose_hash']."\n".$capture['purpose_json']),$capture['purpose_record_hash']));
        $record=json_decode($capture['purpose_json'],false,12,JSON_THROW_ON_ERROR);
        self::object($record,['version','analytics','advertising']);self::need($record->version===1&&self::canonical($record)===$capture['purpose_json']);
        return $record;
    }
    private static function touch($touch,string $purpose,array $capture,array $history): int {
        self::object($touch,['capture_id','decision_version','notice_version','landing_page','referrer','timestamp','parameters','original_revision','expires_at']);
        self::need(is_string($touch->capture_id)&&preg_match('/^[a-f0-9]{8}-[a-f0-9]{4}-4[a-f0-9]{3}-[89ab][a-f0-9]{3}-[a-f0-9]{12}$/D',$touch->capture_id)===1);
        self::need(is_string($touch->decision_version)&&preg_match('/^[a-f0-9]{32}$/D',$touch->decision_version)===1&&is_int($touch->original_revision)&&$touch->original_revision>0&&$touch->original_revision<=(int)$capture['original_revision']);
        $row=$history[$touch->original_revision]??null;$flag=$purpose==='analytics'?'analytics':'ad_measurement';
        self::need($row!==null&&$row['receipt']===$touch->decision_version&&$row['subject_key']===$capture['subject_key']&&$row['notice_version']===$touch->notice_version&&$touch->notice_version===$capture['notice_version']);
        self::need(is_int($touch->expires_at)&&$touch->expires_at===(int)$row['changed_at']+self::WINDOW&&is_int($touch->timestamp)&&$touch->timestamp>=(int)$row['changed_at']*1000&&$touch->timestamp<$touch->expires_at*1000&&$touch->timestamp<((int)$capture['created_at']+1)*1000&&(int)$capture['created_at']<$touch->expires_at);
        $next=$history[$touch->original_revision+1]??null;self::need($next===null||$touch->timestamp<(int)$next['changed_at']*1000);
        // At capture time every intervening decision must preserve this purpose; later withdrawals stay retained.
        for($revision=$touch->original_revision;$revision<=(int)$capture['original_revision'];$revision++){
            $decision=$history[$revision]??null;self::need($decision!==null&&(int)$decision[$flag]===1&&(int)$decision['uncertain']===0&&$decision['notice_version']===$touch->notice_version);
        }
        self::need((int)$capture['eligible']===1&&(int)$capture[$flag]===1);self::url($touch->landing_page);self::url($touch->referrer,true);self::need($purpose==='analytics'||$touch->referrer==='');
        $landing=parse_url($touch->landing_page);
        $origin=$landing['scheme'].'://'.strtolower($landing['host']).(isset($landing['port'])?':'.$landing['port']:'');
        self::need($origin===self::SOURCE_ORIGIN);
        self::need($touch->parameters instanceof \stdClass);$allowed=['utm_source','utm_medium','utm_campaign','utm_id','utm_term','utm_content','google_campaign_id','ad_group_id','creative_id'];
        if($purpose==='advertising')$allowed=array_merge($allowed,['gclid','gbraid','wbraid']);
        foreach(get_object_vars($touch->parameters)as$key=>$value){
            self::need(in_array($key,$allowed,true)&&self::text($value));
            if(in_array($key,['gclid','gbraid','wbraid'],true))self::need(preg_match('/^[A-Za-z0-9._~-]{1,256}$/D',$value)===1);
            if(in_array($key,['google_campaign_id','ad_group_id','creative_id'],true))self::need(preg_match('/^[0-9]{1,32}$/D',$value)===1);
        }
        return $touch->original_revision;
    }
    public static function plan(array $snapshot,array $coverage,int $now,bool $enabled=false): array {
        if(!$enabled)return Base::plan([],[],0,false);
        $snapshot=self::copy($snapshot);$coverage=self::copy($coverage);
        $fullHash=Base::digest($snapshot);$projection=self::copy($snapshot);
        self::need(isset($snapshot['captures'])&&is_array($snapshot['captures'])&&array_is_list($snapshot['captures']));
        foreach($snapshot['captures']as$i=>$capture){self::keys($capture,array_merge(RetentionInventory::COLUMNS['captures'],self::EXTRA));foreach(self::EXTRA as$key)unset($projection['captures'][$i][$key]);}
        $projectedCoverage=$coverage;$projectedCoverage['snapshot_sha256']=Base::digest($projection);
        $review=Base::plan($projection,$projectedCoverage,$now,true);$global=$review['global_reasons'];
        if(($coverage['snapshot_sha256']??null)!==$fullHash)$global[]='COVERAGE_SNAPSHOT_MISMATCH';
        $histories=[];foreach($projection['history']as$row)$histories[$row['subject_key']][(int)$row['revision']]=$row;
        $protect=[];
        foreach($snapshot['captures']as$capture){
            self::need((int)$capture['known']===1&&(int)$capture['uncertain']===0&&$capture['subject_key']!=='');$record=self::record($capture);
            foreach(['analytics','advertising']as$purpose){
                self::object($record->$purpose,['first','last']);$first=$record->$purpose->first;$last=$record->$purpose->last;
                self::need(($first===null)===($last===null));if($first===null)continue;
                $history=$histories[$capture['subject_key']]??[];
                foreach([$first,$last]as$touch){$revision=self::touch($touch,$purpose,$capture,$history);$protect[$capture['subject_key']]=min($protect[$capture['subject_key']]??PHP_INT_MAX,$revision);}
                self::need($first->timestamp<=$last->timestamp&&($first->capture_id!==$last->capture_id||self::canonical($first)===self::canonical($last)));
            }
        }
        $references=[];foreach($projection['history']as$row)$references['bsre_consent_history:'.$row['receipt']]=$row;
        $counts=['due_unreferenced_choice_rows'=>0,'held_choice_rows'=>0,'protected_capture_rows'=>0];
        foreach($review['rows']as&$row){
            $reference=$references[$row['row_ref']]??null;
            if($reference&&isset($protect[$reference['subject_key']])&&(int)$reference['revision']>=$protect[$reference['subject_key']])$row['reasons'][]='NESTED_PURPOSE_AND_WITHDRAWAL_HISTORY_REQUIRED';
            $row['reasons']=array_values(array_unique(array_merge($row['reasons'],$global)));sort($row['reasons']);
            if($row['classification']==='PROTECTED_CAPTURE_OUTSIDE_SCOPE')++$counts['protected_capture_rows'];
            else{$row['classification']=$row['reasons']?'HOLD':'DUE_UNREFERENCED_SYNTHETIC_REVIEW';++$counts[$row['classification']==='HOLD'?'held_choice_rows':'due_unreferenced_choice_rows'];}
        }unset($row);
        $review['schema']='SYNTHETIC_PURPOSE_PER_CHOICE_PLAN_V1';$review['snapshot_sha256']=$fullHash;$review['coverage_sha256']=Base::digest($coverage);$review['counts']=$counts;
        $review['global_reasons']=array_values(array_unique($global));sort($review['global_reasons']);unset($review['plan_sha256']);$review['plan_sha256']=Base::digest($review);return $review;
    }
}
