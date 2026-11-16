<?php
declare(strict_types=1);
namespace BSRE\SharedRepository;
use BSRE\Enquiries as E;
use BSRE\PurposeAttribution as P;

const SCHEMA_OPTION = 'bsre_g2_shared_repository_schema';
const SCHEMA_VERSION = '1';
final class Runtime {
    public static ?object $db = null;
    public static string $prefix = '';
    public static string $database = '';
    public static ?P\ConsentRepository $store = null;
    public static bool $schemaChecked = false;
}
function enabled(): bool {
    return defined('BSRE_G2_SHARED_REPOSITORY_ENABLED') && BSRE_G2_SHARED_REPOSITORY_ENABLED === true;
}
function tables($db): array {
    if (!is_object($db) || !is_string($db->prefix ?? null) || !preg_match('/^[A-Za-z0-9_]+$/D',$db->prefix)) throw new \RuntimeException('G2_DATABASE_INVALID');
    foreach (['prepare','get_results','get_var','query','suppress_errors'] as $method) if (!method_exists($db,$method)) throw new \RuntimeException('G2_DATABASE_INVALID');
    $names=[];
    foreach (['state','history','captures'] as $kind) {
        $names[$kind]=$db->prefix.'bsre_consent_'.$kind;
        if (strlen($names[$kind])>64) throw new \RuntimeException('G2_DATABASE_INVALID');
    }
    return $names;
}
/** SELECT DATABASE is connection metadata, not the mutable wpdb dbname field. */
function selected_database($db): string {
    tables($db);
    if (!defined('DB_NAME') || !is_string(DB_NAME) || DB_NAME==='') throw new \RuntimeException('G2_DATABASE_UNVERIFIED');
    $suppressed=$db->suppress_errors(true);
    try {
        $db->last_error=''; $actual=$db->get_var('SELECT DATABASE()');
        if ($db->last_error!=='' || !is_string($actual) || $actual==='') throw new \RuntimeException('G2_DATABASE_UNVERIFIED');
    } catch (\Throwable $error) { throw new \RuntimeException('G2_DATABASE_UNVERIFIED'); }
    finally { $db->suppress_errors($suppressed); }
    // Never include actual/configured names, DSNs or SQL error text in reports.
    if ($actual!==DB_NAME) throw new \RuntimeException('G2_DATABASE_CHANGED');
    return $actual;
}
/** Keep already-issued handles bound too; callers may retain them across a USE. */
final class BoundRepository implements P\ConsentRepository {
    private P\ConsentRepository $inner;
    private object $db;
    private string $prefix;
    private string $database;
    public function __construct(P\ConsentRepository $inner,object $db,string $database) {
        $this->inner=$inner; $this->db=$db; $this->prefix=$db->prefix; $this->database=$database;
    }
    private function guard(): void {
        global $wpdb;
        if (!enabled()) throw new \RuntimeException('G2_PROFILE_DISABLED');
        $database=selected_database($this->db);
        if ($wpdb!==$this->db || $this->db->prefix!==$this->prefix || $database!==$this->database) throw new \RuntimeException('G2_DATABASE_CHANGED');
        if (get_option('bsre_consent_schema_version')!=='2' || get_option(SCHEMA_OPTION)!==SCHEMA_VERSION) throw new \RuntimeException('G2_SCHEMA_NOT_READY');
    }
    public function database() { $this->guard(); return $this->db; }
    public function admissionContract(): string { $this->guard(); return $this->inner->admissionContract(); }
    public function current(string $subject): ?array { $this->guard(); return $this->inner->current($subject); }
    public function choose(string $subject,array $flags,string $notice,int $now,bool $uncertain=false): array { $this->guard(); return $this->inner->choose($subject,$flags,$notice,$now,$uncertain); }
    public function stage(array $capture): array { $this->guard(); return $this->inner->stage($capture); }
    public function link(string $request,string $fingerprint,string $lead,string $event): array { $this->guard(); return $this->inner->link($request,$fingerprint,$lead,$event); }
    public function uncertain(string $request,string $fingerprint): void { $this->guard(); $this->inner->uncertain($request,$fingerprint); }
    public function revoked(string $subject,int $revision,string $purpose): bool { $this->guard(); return $this->inner->revoked($subject,$revision,$purpose); }
    public function exportRows(array $requests): array { $this->guard(); return $this->inner->exportRows($requests); }
}
function query_rows($db,string $sql): array {
    $db->last_error=''; $rows=$db->get_results($sql,ARRAY_A);
    if ($db->last_error!=='' || !is_array($rows) || count($rows)>128) throw new \RuntimeException('G2_SCHEMA_UNAVAILABLE');
    return $rows;
}
function additions(): array {
    return ['purpose_version'=>"tinyint unsigned NOT NULL DEFAULT 0",'purpose_hash'=>"char(64) NOT NULL DEFAULT ''",
        'purpose_record_hash'=>"char(64) NOT NULL DEFAULT ''",'purpose_json'=>"mediumtext NULL"];
}
/** Read-only metadata. No schema marker alone is accepted as schema proof. */
function inspect($db,bool $complete): array {
    $names=tables($db);
    $engines=query_rows($db,$db->prepare('SHOW TABLE STATUS WHERE Name IN (%s,%s,%s)',...array_values($names)));
    $byName=[];
    foreach ($engines as $row) {
        if (!isset($row['Name'],$row['Engine']) || isset($byName[$row['Name']])) throw new \RuntimeException('G2_SCHEMA_UNAVAILABLE');
        $byName[$row['Name']]=strtolower($row['Engine']);
    }
    $required=[
        'state'=>['subject_key','revision','receipt','analytics','ad_measurement','personalization','notice_version','changed_at','expires_at','uncertain'],
        'history'=>['receipt','subject_key','revision','analytics','ad_measurement','personalization','notice_version','changed_at','uncertain'],
        'captures'=>['request_id','fingerprint','subject_key','original_revision','decision_version','notice_version','analytics','ad_measurement','personalization','preference_expires_at','eligible','known','created_at','state','uncertain','delivery_pending','click_capture_state','gclid_first','gclid_last','gclid_first_captured_ms','gclid_last_captured_ms','lead_id','event_id'],
    ];
    $captureColumns=[];
    foreach ($names as $kind=>$table) {
        if (($byName[$table]??'')!=='innodb') throw new \RuntimeException('G2_TRANSACTIONAL_SCHEMA_REQUIRED');
        $columns=[];
        foreach (query_rows($db,"SHOW COLUMNS FROM `{$table}`") as $row) {
            if (!isset($row['Field']) || isset($columns[$row['Field']])) throw new \RuntimeException('G2_SCHEMA_UNAVAILABLE');
            $columns[$row['Field']]=$row;
        }
        foreach ($required[$kind] as $field) if (!isset($columns[$field])) throw new \RuntimeException('G2_BASE_SCHEMA_INCOMPLETE');
        $unique=[];
        foreach (query_rows($db,"SHOW INDEX FROM `{$table}`") as $row) {
            if ((string)($row['Non_unique']??'')!=='0') continue;
            $seq=(int)($row['Seq_in_index']??0); $key=$row['Key_name']??'';
            if ($key==='' || $seq<1 || !is_string($row['Column_name']??null) || isset($unique[$key][$seq])) throw new \RuntimeException('G2_SCHEMA_UNAVAILABLE');
            if (!array_key_exists('Sub_part',$row) || $row['Sub_part']!==null || isset($row['Expression'])) throw new \RuntimeException('G2_IDENTITY_INDEX_REQUIRED');
            $unique[$key][$seq]=$row['Column_name'];
        }
        foreach ($unique as &$parts) {
            ksort($parts);
            if (array_keys($parts)!==range(1,count($parts))) throw new \RuntimeException('G2_IDENTITY_INDEX_REQUIRED');
            $parts=array_values($parts);
        } unset($parts);
        $pk=['state'=>['subject_key'],'history'=>['receipt'],'captures'=>['request_id']][$kind];
        if (($unique['PRIMARY']??[])!==$pk || ($kind==='history' && !in_array(['subject_key','revision'],$unique,true))) throw new \RuntimeException('G2_IDENTITY_INDEX_REQUIRED');
        if ($kind==='captures') $captureColumns=$columns;
    }
    $missing=[];
    foreach (additions() as $field=>$ddl) {
        if (!isset($captureColumns[$field])) { $missing[]=$field; continue; }
        $col=$captureColumns[$field]; $type=strtolower((string)($col['Type']??''));
        $type=preg_replace('/^tinyint\([0-9]+\)/','tinyint',$type);
        $expected=['purpose_version'=>'tinyint unsigned','purpose_hash'=>'char(64)','purpose_record_hash'=>'char(64)','purpose_json'=>'mediumtext'][$field];
        $nullable=$field==='purpose_json';
        if ($type!==$expected || ($col['Null']??'')!==($nullable?'YES':'NO') || !array_key_exists('Default',$col)
            || ($nullable ? $col['Default']!==null : ($field==='purpose_version' ? !in_array($col['Default'],[0,'0'],true) : $col['Default']!==''))) throw new \RuntimeException('G2_ADDITIVE_SCHEMA_CONFLICT');
    }
    if ($complete && $missing) throw new \RuntimeException('G2_ADDITIVE_SCHEMA_INCOMPLETE');
    return $missing;
}
/** Validate actual selected DB before every cached-store reuse/options lookup. */
function repository(?E\ConsentRepository $requested=null): P\ConsentRepository {
    global $wpdb;
    if (!enabled()) throw new \RuntimeException('G2_PROFILE_DISABLED');
    $database=selected_database($wpdb);
    if (Runtime::$db!==null && (Runtime::$db!==$wpdb || Runtime::$prefix!==$wpdb->prefix || Runtime::$database!==$database)) throw new \RuntimeException('G2_DATABASE_CHANGED');
    if (get_option('bsre_consent_schema_version')!=='2' || get_option(SCHEMA_OPTION)!==SCHEMA_VERSION) throw new \RuntimeException('G2_SCHEMA_NOT_READY');
    if (!Runtime::$schemaChecked || Runtime::$db===null) { inspect($wpdb,true); Runtime::$schemaChecked=true; }
    if (Runtime::$store===null) {
        $store=new BoundRepository(new P\WpConsentRepository($wpdb),$wpdb,$database);
        if ($store->database()!==$wpdb || $store->admissionContract()!==\BSRE\RetentionAdmission\CONTRACT) throw new \RuntimeException('G2_STORE_CONTRACT');
        Runtime::$db=$wpdb; Runtime::$prefix=$wpdb->prefix; Runtime::$database=$database; Runtime::$store=$store;
    }
    if (($requested!==null && $requested!==Runtime::$store) || (P\Runtime::$store!==null && P\Runtime::$store!==Runtime::$store)) throw new \RuntimeException('G2_STORE_CONFLICT');
    P\Runtime::$store=Runtime::$store;
    return Runtime::$store;
}
/** Explicit admin-capability path only. Existing baseline version/rows are not rewritten. */
function migrate(): bool {
    global $wpdb;
    if (!enabled()) return false;
    try {
        $database=selected_database($wpdb);
        if (Runtime::$db!==null && (Runtime::$db!==$wpdb || Runtime::$prefix!==$wpdb->prefix || Runtime::$database!==$database)) return false;
        if (!current_user_can('manage_options')) return false;
        Runtime::$schemaChecked=false;
        if (get_option('bsre_consent_schema_version')!=='2') return false;
        $names=tables($wpdb); $missing=inspect($wpdb,false);
        if ($missing) {
            $parts=[]; $ddl=additions();
            foreach ($missing as $field) $parts[]='ADD COLUMN `'.$field.'` '.$ddl[$field];
            if ($wpdb->query('ALTER TABLE `'.$names['captures'].'` '.implode(', ',$parts))===false) return false;
        }
        inspect($wpdb,true);
        if (get_option(SCHEMA_OPTION)!==SCHEMA_VERSION) update_option(SCHEMA_OPTION,SCHEMA_VERSION,false);
        return get_option(SCHEMA_OPTION)===SCHEMA_VERSION;
    } catch (\Throwable $e) { return false; }
}
