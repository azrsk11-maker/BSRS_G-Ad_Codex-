<?php
declare(strict_types=1);
namespace BSRE\G38PurgeLab;
/** Fixed synthetic lab ONLY. Independent complete keyset snapshot; original G36 helper is unchanged. */
function snapshot():array {
    global $wpdb;
    \BSRE\G36Native\fixed();
    if($wpdb->custodyIsActive())throw new \RuntimeException('G38_FOREIGN_SNAPSHOT_LEASE_ACTIVE');
    $wpdb->last_error='';$connection=(string)$wpdb->get_var('SELECT CONNECTION_ID()');
    if($wpdb->last_error!==''||!preg_match('/^[1-9][0-9]*$/D',$connection))throw new \RuntimeException('G38_FOREIGN_SNAPSHOT_CONNECTION_UNVERIFIED');
    $same=static function()use($wpdb,$connection):void{
        $wpdb->last_error='';$now=(string)$wpdb->get_var('SELECT CONNECTION_ID()');
        if($wpdb->last_error!==''||$now!==$connection)throw new \RuntimeException('G38_FOREIGN_SNAPSHOT_CONNECTION_CHANGED');
    };
    $rows=static function(string $sql)use($wpdb,$same):array{
        $same();$wpdb->last_error='';$out=$wpdb->get_results($sql,ARRAY_A);
        if($wpdb->last_error!==''||!is_array($out))throw new \RuntimeException('G38_FOREIGN_SNAPSHOT_QUERY_FAILED');$same();return $out;
    };
    $scalar=static function(string $sql)use($rows):string{
        $out=$rows($sql);if(count($out)!==1||count($out[0])!==1)throw new \RuntimeException('G38_FOREIGN_SNAPSHOT_SCALAR_INVALID');
        $v=array_values($out[0])[0];if(!is_string($v)&&!is_int($v))throw new \RuntimeException('G38_FOREIGN_SNAPSHOT_SCALAR_INVALID');return (string)$v;
    };
    $query=static function(string $sql)use($wpdb,$same):void{
        $same();$wpdb->last_error='';if($wpdb->query($sql)===false||$wpdb->last_error!=='')throw new \RuntimeException('G38_FOREIGN_SNAPSHOT_QUERY_FAILED');$same();
    };
    if($scalar('SELECT @@session.in_transaction')!=='0')throw new \RuntimeException('G38_FOREIGN_SNAPSHOT_TRANSACTION_ACTIVE');
    if(strtoupper($scalar('SELECT @@session.tx_isolation'))!=='REPEATABLE-READ')throw new \RuntimeException('G38_FOREIGN_SNAPSHOT_ISOLATION_UNVERIFIED');
    $started=false;$committing=false;
    try{
        $started=true;$query('START TRANSACTION WITH CONSISTENT SNAPSHOT, READ ONLY');
        if($scalar('SELECT @@session.in_transaction')!=='1')throw new \RuntimeException('G38_FOREIGN_SNAPSHOT_TRANSACTION_UNVERIFIED');
        $inventory=static function()use($rows):array{
            $out=$rows("SELECT TABLE_NAME FROM information_schema.TABLES WHERE TABLE_SCHEMA=DATABASE() AND RIGHT(TABLE_NAME,22)='_bsre_consent_captures' ORDER BY TABLE_NAME LIMIT 257");
            if(count($out)>256)throw new \RuntimeException('G38_FOREIGN_CAPTURE_TABLE_BOUND');$names=[];
            foreach($out as $row){$name=$row['TABLE_NAME']??null;if(!is_string($name)||!preg_match('/^[a-z][a-z0-9_]{0,80}_bsre_consent_captures$/D',$name)||isset($names[$name]))throw new \RuntimeException('G38_FOREIGN_CAPTURE_TABLE_UNRECOGNIZED');$names[$name]=true;}
            return array_keys($names);
        };
        $tables=$inventory();$result=[];
        foreach($tables as $table){
            $status=$rows($wpdb->prepare('SHOW TABLE STATUS WHERE Name=%s',$table));
            if(count($status)!==1||strtolower((string)($status[0]['Engine']??''))!=='innodb')throw new \RuntimeException('G38_FOREIGN_CAPTURE_SNAPSHOT_ENGINE_REQUIRED');
            $columns=$rows('SHOW FULL COLUMNS FROM `'.$table.'`');$names=array_column($columns,'Field');
            if($names===[]||count($names)!==count(array_unique($names))||!in_array('request_id',$names,true))throw new \RuntimeException('G38_FOREIGN_CAPTURE_COLUMNS_UNVERIFIED');
            $primary=$rows("SHOW INDEX FROM `".$table."` WHERE Key_name='PRIMARY'");
            if(count($primary)!==1||($primary[0]['Column_name']??null)!=='request_id'||(string)($primary[0]['Seq_in_index']??'')!=='1'
                ||(string)($primary[0]['Non_unique']??'')!=='0'||($primary[0]['Sub_part']??null)!==null||strtoupper((string)($primary[0]['Index_type']??''))!=='BTREE')throw new \RuntimeException('G38_FOREIGN_CAPTURE_UNIQUE_KEY_REQUIRED');
            $rawCount=$scalar('SELECT COUNT(*) FROM `'.$table.'`');
            if(!preg_match('/^(0|[1-9][0-9]*)$/D',$rawCount)||strlen($rawCount)>strlen((string)PHP_INT_MAX)
                ||(strlen($rawCount)===strlen((string)PHP_INT_MAX)&&strcmp($rawCount,(string)PHP_INT_MAX)>0))throw new \RuntimeException('G38_FOREIGN_CAPTURE_COUNT_INVALID');
            $expected=(int)$rawCount;$seen=0;$pages=0;$last=null;$hash=hash_init('sha256');
            while(true){
                $sql='SELECT * FROM `'.$table.'`'.($last===null?'':$wpdb->prepare(' WHERE BINARY request_id > BINARY %s',$last)).' ORDER BY BINARY request_id LIMIT 256';
                $page=$rows($sql);$pages++;if(count($page)>256)throw new \RuntimeException('G38_FOREIGN_CAPTURE_PAGE_BOUND');
                if($page===[])break;
                foreach($page as $row){
                    $key=$row['request_id']??null;
                    if(array_keys($row)!==$names||!is_string($key)||$key===''||str_contains($key,"\0")||($last!==null&&strcmp($key,$last)<=0))throw new \RuntimeException('G38_FOREIGN_CAPTURE_KEYSET_UNVERIFIED');
                    if($seen>=$expected)throw new \RuntimeException('G38_FOREIGN_CAPTURE_COUNT_CONFLICT');
                    $raw=json_encode($row,JSON_THROW_ON_ERROR|JSON_UNESCAPED_SLASHES);hash_update($hash,strlen($raw).':'.$raw."\n");$seen++;$last=$key;
                }
            }
            if($seen!==$expected||(string)$seen!==$scalar('SELECT COUNT(*) FROM `'.$table.'`'))throw new \RuntimeException('G38_FOREIGN_CAPTURE_COUNT_CONFLICT');
            $result[$table]=['rows'=>$seen,'pages'=>$pages,'sha256'=>hash_final($hash),'schema_sha256'=>hash('sha256',json_encode($columns,JSON_THROW_ON_ERROR|JSON_UNESCAPED_SLASHES))];
        }
        if($inventory()!==$tables)throw new \RuntimeException('G38_FOREIGN_CAPTURE_INVENTORY_CHANGED');
        $committing=true;$query('COMMIT');$started=false;
        if($scalar('SELECT @@session.in_transaction')!=='0')throw new \RuntimeException('G38_FOREIGN_SNAPSHOT_COMMIT_UNVERIFIED');
        return $result;
    }catch(\Throwable $error){
        // A semantic hold cannot suppress transaction cleanup. No provider or data write exists here.
        if($started){try{$same();$wpdb->last_error='';$ok=$wpdb->query('ROLLBACK')!==false&&$wpdb->last_error===''&&(string)$wpdb->get_var('SELECT @@session.in_transaction')==='0';$same();}catch(\Throwable $ignored){$ok=false;}if(!$ok)throw new \RuntimeException('G38_FOREIGN_SNAPSHOT_ROLLBACK_UNCERTAIN');}
        if($committing)throw new \RuntimeException('G38_FOREIGN_SNAPSHOT_COMMIT_UNCERTAIN');throw $error;
    }
}
