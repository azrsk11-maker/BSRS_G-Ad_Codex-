<?php
declare(strict_types=1);
namespace BSRE\RetentionReview;
require_once __DIR__.'/RetentionInventory.php';

/** Read-only, bounded diagnostics. No supplied snapshot proves live coverage. */
final class LinkageReconciliation {
    public const HEADERS=['request_id','lead_id','event_id','accepted_at_utc','payload_sha256','payload_json','email_status','email_attempts','email_next_attempt_at','email_last_error','email_sent_at_utc','name','phone','email','role','campaign','landing_page','contact_consent','marketing_consent','lead_status','assigned_to','qualification_status','qualified_at_utc','person_duplicate_of','staff_notes','email_attempt_started_at_utc'];
    private static function invalid(): never { throw new \InvalidArgumentException('INVALID_OR_UNBOUNDED_LINKAGE_SNAPSHOT'); }
    private static function uuid($v): string {
        return is_string($v) && preg_match('/^[a-f0-9]{8}-[a-f0-9]{4}-4[a-f0-9]{3}-[89ab][a-f0-9]{3}-[a-f0-9]{12}$/Di',$v) ? strtolower($v) : '';
    }
    private static function receipt($v,string $prefix): bool { return is_string($v) && str_starts_with($v,$prefix) && self::uuid(substr($v,strlen($prefix)))!==''; }
    private static function digest($v): bool { return is_string($v) && preg_match('/^[a-f0-9]{64}$/D',$v)===1; }
    private static function bit($v): bool { return in_array($v,[0,1,'0','1',false,true],true); }
    public static function assess(array $snapshot): array {
        $keys=array_keys($snapshot); sort($keys);
        if ($keys!==['captures','receiver_headers','receiver_rows','source'] || $snapshot['source']!=='SYNTHETIC_PIPE_SESSION' || $snapshot['receiver_headers']!==self::HEADERS) self::invalid();
        foreach(['captures','receiver_rows'] as $k) if (!is_array($snapshot[$k]) || !array_is_list($snapshot[$k])) self::invalid();
        if (count($snapshot['captures'])+count($snapshot['receiver_rows'])>1000) self::invalid();
        $bytes=0;
        foreach(['captures','receiver_rows'] as $part) foreach($snapshot[$part] as $row) {
            if(!is_array($row)) self::invalid();
            foreach($row as $value) {
                if(!is_string($value) && !is_int($value) && !is_bool($value)) self::invalid();
                $bytes+=is_string($value)?strlen($value):8;
                if($bytes>8*1024*1024) self::invalid();
            }
        }
        try { RetentionInventory::plan(['kind'=>RetentionInventory::KIND,'state'=>[],'history'=>[],'captures'=>$snapshot['captures']],time(),true); }
        catch(\InvalidArgumentException $e) { self::invalid(); }
        $issues=[]; $captures=[]; $receiver=[]; $leadOwners=[]; $eventOwners=[]; $invalidReceiver=[];
        $add=function(string $code)use(&$issues):void{$issues[$code]=($issues[$code]??0)+1;};
        $captureColumns=RetentionInventory::COLUMNS['captures']; sort($captureColumns);
        $permissionHolds=0; $outboxHolds=0; $globalHold=false;
        foreach($snapshot['captures'] as $capture) {
            if (!is_array($capture)) self::invalid(); $cols=array_keys($capture); sort($cols);
            if ($cols!==$captureColumns) self::invalid();
            $id=self::uuid($capture['request_id']);
            if ($id==='' || !self::digest($capture['fingerprint']) || !is_string($capture['subject_key']) || ($capture['subject_key']!=='' && !self::digest($capture['subject_key']))) self::invalid();
            foreach(['known','uncertain','delivery_pending','analytics','ad_measurement','personalization','eligible'] as $k) if(!self::bit($capture[$k])) self::invalid();
            if(!in_array($capture['state'],['STAGED','ACCEPTED'],true)) self::invalid();
            if($capture['state']==='ACCEPTED' && (!self::receipt($capture['lead_id'],'BSRE-') || !self::receipt($capture['event_id'],'evt_'))) self::invalid();
            if (isset($captures[$id])) { $add('DUPLICATE_CAPTURE_REQUEST'); $globalHold=true; }
            $captures[$id][]=$capture;
            if ($capture['subject_key']==='') { $add('CAPTURE_SUBJECT_UNKNOWN'); $globalHold=true; }
            if ((int)$capture['known']!==1 || (int)$capture['uncertain']!==0 || (int)$capture['delivery_pending']!==0 || (int)$capture['ad_measurement']!==1 || (int)$capture['eligible']!==1 || (int)$capture['preference_expires_at']<=time() ||
                (int)$capture['personalization']!==0 || trim($capture['notice_version'])==='' || (int)$capture['original_revision']<1 || (int)$capture['created_at']<=0 || (int)$capture['created_at']>time() || $capture['state']!=='ACCEPTED') $permissionHolds++;
        }
        foreach($snapshot['receiver_rows'] as $row) {
            if (!is_array($row) || !array_is_list($row) || count($row)!==26) self::invalid();
            $id=self::uuid($row[0]);
            if ($id==='' || !self::receipt($row[1],'BSRE-') || !self::receipt($row[2],'evt_') || !self::digest($row[4]) || !is_string($row[5]) || strlen($row[5])>26000 || !is_string($row[6])) self::invalid();
            if (!in_array($row[6],['QUEUED','RETRY_WAIT','SENDING','SENT','AMBIGUOUS','NEEDS_REVIEW'],true)) self::invalid();
            if (isset($receiver[$id])) { $add('DUPLICATE_RECEIVER_REQUEST'); $globalHold=true; $invalidReceiver[$id]=true; }
            $receiver[$id][]=$row;
            foreach([1,2] as $column) {
                $receipt=strtolower($row[$column]);
                $previous=$column===1?($leadOwners[$receipt]??null):($eventOwners[$receipt]??null);
                if ($previous!==null) { $add($column===1?'DUPLICATE_LEAD_ID':'DUPLICATE_EVENT_ID'); $globalHold=true; $invalidReceiver[$id]=true; $invalidReceiver[$previous]=true; }
                if($column===1) $leadOwners[$receipt]=$id; else $eventOwners[$receipt]=$id;
            }
            if (!hash_equals($row[4],hash('sha256',$row[5]))) { $add('RECEIVER_PAYLOAD_DIGEST_MISMATCH'); $globalHold=true; $invalidReceiver[$id]=true; }
            try { $payload=json_decode($row[5],false,32,JSON_THROW_ON_ERROR); }
            catch(\Throwable $e) { $payload=null; }
            if (!is_object($payload) || self::uuid($payload->request_id??null)!==$id || ($payload->role??null)!==$row[14]) { $add('RECEIVER_PAYLOAD_IDENTITY_MISMATCH'); $globalHold=true; $invalidReceiver[$id]=true; }
            if ($row[6]!=='SENT') $outboxHolds++;
        }
        $matched=0;
        foreach($receiver as $id=>$rows) {
            if (!isset($captures[$id])) { $add('CAPTURE_MISSING'); $globalHold=true; continue; }
            if(count($rows)!==1 || count($captures[$id])!==1 || isset($invalidReceiver[$id])) continue;
            $capture=$captures[$id][0]; $row=$rows[0];
            if ($capture['state']!=='ACCEPTED') { $add('RECEIPT_NOT_LINKED'); $globalHold=true; continue; }
            if ($capture['lead_id']!==$row[1] || $capture['event_id']!==$row[2]) { $add('RECEIPT_ID_CONFLICT'); $globalHold=true; continue; }
            $matched++;
        }
        foreach($captures as $id=>$rows) if(!isset($receiver[$id])) {
            $accepted=false; foreach($rows as $capture) if($capture['state']==='ACCEPTED') $accepted=true;
            $add($accepted?'RECEIVER_ROW_MISSING':'CAPTURE_OUTCOME_UNRESOLVED'); $globalHold=true;
        }
        ksort($issues);
        return ['scope'=>'SYNTHETIC_SNAPSHOT_ONLY','capture_rows'=>count($snapshot['captures']),'receiver_rows'=>count($snapshot['receiver_rows']),'matched_request_receipts'=>$matched,
            'issues'=>$issues,'original_measurement_holds'=>$permissionHolds,'outbox_holds'=>$outboxHolds,'global_linkage_hold'=>$globalHold,
            'fingerprint_domains'=>'WORDPRESS_RAW_AND_RECEIVER_NORMALIZED_DISTINCT','historical_coverage_verified'=>false,'mail_delivery_verified'=>false,'deletion_authorized'=>false,'import_authorized'=>false];
    }
}
