<?php
declare(strict_types=1);
namespace BSRE\ActualRetention;
use BSRE\Enquiries as E;
use BSRE\PurposeAttribution as P;
use BSRE\SharedRepository as G;
use BSRE\ProfileTransport as T;
use BSRE\RetentionAdmission as A;
require_once __DIR__ . '/G5Contracts.php';

/** Code/store provenance only. No provider, owner-action, receiver or custody authority. */
final class CanonicalCaptureProducer implements CaptureProducer
{
    private const MANIFEST_SHA256='__BSRE_CODE_MANIFEST_SHA256__';
    private const MANIFEST_SCHEMA='bsre-canonical-lease-source-v1';
    private const MANIFEST_PROFILE='G35_CANONICAL_LEASE_CODE_ONLY';
    private const WPDB_CORE_SHA256='e15403e90032dd0508811301505e491d4212de5152581a98f51b744a1a3903bd';
    private string $prefix;
    private string $database;
    private ?array $admission=null;
    private const CLASSES=[
        'BSRE\\Enquiries\\ConsentRepository'=>'includes/consent-store.php',
        'BSRE\\Enquiries\\WpConsentRepository'=>'includes/consent-store.php',
        'BSRE\\PurposeAttribution\\ConsentRepository'=>'includes/g2-profile/purpose-store.php',
        'BSRE\\PurposeAttribution\\WpConsentRepository'=>'includes/g2-profile/purpose-store.php',
        'BSRE\\PurposeAttribution\\Runtime'=>'includes/g2-profile/purpose-attribution.php',
        'BSRE\\SharedRepository\\BoundRepository'=>'includes/g2-profile/shared-repository.php',
        'BSRE\\SharedRepository\\Runtime'=>'includes/g2-profile/shared-repository.php',
        'BSRE\\RetentionAdmission\\Runtime'=>'includes/g2-profile/retention-admission.php',
        'BSRE\\ClosedRetention\\LeaseBoundWpdb'=>'includes/candidate/closed-enquiry-retention/LeaseBoundWpdb.php',
        'BSRE\\ActualRetention\\CaptureProducer'=>'includes/candidate/runtime/G5Contracts.php'
    ];
    private const FUNCTIONS=[
        'BSRE\\Enquiries\\ready'=>'bsre-enquiries.php',
        'BSRE\\Enquiries\\validate_payload'=>'includes/protocol.php',
        'BSRE\\Enquiries\\same_origin_request'=>'bsre-enquiries.php',
        'BSRE\\Enquiries\\consent_repository'=>'includes/consent.php',
        'BSRE\\Enquiries\\consent_stage_submission'=>'includes/consent.php',
        'BSRE\\Enquiries\\consent_link_accepted'=>'includes/consent.php',
        'BSRE\\PurposeAttribution\\repository'=>'includes/g2-profile/purpose-attribution.php',
        'BSRE\\PurposeAttribution\\prepare_capture'=>'includes/g2-profile/purpose-attribution.php',
        'BSRE\\PurposeAttribution\\assert_record'=>'includes/g2-profile/purpose-attribution.php',
        'BSRE\\PurposeAttribution\\exact_object'=>'includes/g2-profile/purpose-attribution.php',
        'BSRE\\PurposeAttribution\\canonical'=>'includes/g2-profile/purpose-attribution.php',
        'BSRE\\PurposeAttribution\\normalize_touch'=>'includes/g2-profile/purpose-attribution.php',
        'BSRE\\PurposeAttribution\\stage_submission'=>'includes/g2-profile/purpose-intake.php',
        'BSRE\\PurposeAttribution\\receive_wire'=>'includes/g2-profile/purpose-intake.php',
        'BSRE\\ReceiptRecovery\\handle'=>'includes/g2-profile/receipt-recovery-wordpress.php',
        'BSRE\\ReceiptRecovery\\resolve_pending_capture'=>'includes/g2-profile/receipt-recovery-wordpress.php',
        'BSRE\\ReceiptRecovery\\recover'=>'includes/g2-profile/receipt-recovery.php',
        'BSRE\\ReceiptRecovery\\issue'=>'includes/g2-profile/receipt-recovery.php',
        'BSRE\\SharedRepository\\repository'=>'includes/g2-profile/shared-repository.php',
        'BSRE\\SharedRepository\\selected_database'=>'includes/g2-profile/shared-repository.php',
        'BSRE\\SharedRepository\\inspect'=>'includes/g2-profile/shared-repository.php',
        'BSRE\\RetentionAdmission\\configuration'=>'includes/g2-profile/retention-admission.php',
        'BSRE\\RetentionAdmission\\readback'=>'includes/g2-profile/retention-admission.php',
        'BSRE\\RetentionAdmission\\assert_capture'=>'includes/g2-profile/retention-admission.php',
        'BSRE\\ProfileTransport\\selected'=>'includes/g3-profile/route-context.php',
        'BSRE\\ProfileTransport\\ready'=>'includes/g3-profile/route-context.php',
        'BSRE\\ProfileTransport\\context'=>'includes/g3-profile/route-context.php',
        'BSRE\\ProfileTransport\\receive_legacy'=>'includes/g3-profile/route-context.php',
        'BSRE\\ProfileTransport\\receive_purpose'=>'includes/g3-profile/route-context.php',
        'BSRE\\ProfileTransport\\proof'=>'includes/g3-profile/route-context.php',
        'BSRE\\ProfileTransport\\status'=>'includes/g3-profile/route-context.php'
    ];
    public function __construct(private \BSRE\ClosedRetention\LeaseBoundWpdb $db)
    {
        if(!defined('DB_NAME') || !is_string(DB_NAME) || DB_NAME==='' || !is_string($db->prefix??null) || $db->prefix==='') self::fail('BINDING_REQUIRED');
        $this->database=DB_NAME; $this->prefix=$db->prefix;
        $this->assertCurrent($db);
    }
    private static function fail(string $code): never { throw new \BSRE\ClosedRetention\Failure('CANONICAL_PRODUCER_'.$code); }
    private function sources(): void
    {
        if(!defined('BSRE_CANONICAL_LEASE_ENABLED') || BSRE_CANONICAL_LEASE_ENABLED!==true
            || !defined('BSRE_CANONICAL_LEASE_BOOTSTRAPPED') || BSRE_CANONICAL_LEASE_BOOTSTRAPPED!==true
            || !defined('BSRE_CANONICAL_LEASE_SOURCE_SHA256') || BSRE_CANONICAL_LEASE_SOURCE_SHA256!==self::MANIFEST_SHA256
            || !defined('BSRE_CANONICAL_LEASE_PRODUCER_SHA256') || !is_string(BSRE_CANONICAL_LEASE_PRODUCER_SHA256)
            || !preg_match('/^[a-f0-9]{64}$/D',BSRE_CANONICAL_LEASE_PRODUCER_SHA256)) self::fail('DROPIN_BINDING_REQUIRED');
        $root=realpath(dirname(__DIR__,3)); $self=realpath(__FILE__);
        if($root===false || $self===false || $self!==$root.DIRECTORY_SEPARATOR.str_replace('/',DIRECTORY_SEPARATOR,'includes/candidate/runtime/CanonicalCaptureProducer.php')
            || !hash_equals(BSRE_CANONICAL_LEASE_PRODUCER_SHA256,(string)hash_file('sha256',$self))) self::fail('SELF_SOURCE_CHANGED');
        $manifestPath=$root.DIRECTORY_SEPARATOR.str_replace('/',DIRECTORY_SEPARATOR,'includes/candidate/runtime/canonical-source.json');
        if(!is_file($manifestPath) || is_link($manifestPath) || filesize($manifestPath)>65536) self::fail('SOURCE_MANIFEST_REQUIRED');
        $raw=file_get_contents($manifestPath);
        if(!is_string($raw) || !hash_equals(self::MANIFEST_SHA256,hash('sha256',$raw))) self::fail('SOURCE_MANIFEST_CHANGED');
        try { $manifest=json_decode($raw,true,16,JSON_THROW_ON_ERROR); }
        catch(\Throwable $error) { self::fail('SOURCE_MANIFEST_INVALID'); }
        if(!is_array($manifest)) self::fail('SOURCE_MANIFEST_INVALID');
        $keys=array_keys($manifest);sort($keys);
        if($keys!==['deployment_prohibited','files','profile','schema'] || $manifest['schema']!==self::MANIFEST_SCHEMA
            || $manifest['profile']!==self::MANIFEST_PROFILE || $manifest['deployment_prohibited']!==true
            || !is_array($manifest['files']) || count($manifest['files'])!==55) self::fail('SOURCE_MANIFEST_INVALID');
        $expected=[];
        foreach($manifest['files'] as $relative=>$hash) {
            if(!is_string($relative) || !preg_match('~^[A-Za-z0-9_./-]{1,240}$~D',$relative) || str_starts_with($relative,'/')
                || array_intersect(explode('/',$relative),['','.','..'])!==[] || !is_string($hash) || !preg_match('/^[a-f0-9]{64}$/D',$hash)
                || in_array($relative,['includes/candidate/runtime/CanonicalCaptureProducer.php','includes/candidate/runtime/canonical-source.json'],true)) self::fail('SOURCE_MANIFEST_INVALID');
            $path=$root.DIRECTORY_SEPARATOR.str_replace('/',DIRECTORY_SEPARATOR,$relative);
            if(!is_file($path) || is_link($path) || realpath($path)!==$path) self::fail('SOURCE_PATH_CHANGED');
            $parent=dirname($path);
            while($parent!==$root) { if(is_link($parent)) self::fail('SOURCE_PATH_CHANGED'); $next=dirname($parent);if($next===$parent) self::fail('SOURCE_PATH_CHANGED');$parent=$next; }
            if(!hash_equals($hash,(string)hash_file('sha256',$path))) self::fail('SOURCE_BYTES_CHANGED');
            $expected[$relative]=$path;
        }
        foreach(self::CLASSES as $name=>$relative) {
            if(!isset($expected[$relative]) || (!class_exists($name,false)&&!interface_exists($name,false))) self::fail('LOADED_SOURCE_UNVERIFIED');
            $reflection=new \ReflectionClass($name);
            if($reflection->getName()!==$name || realpath((string)$reflection->getFileName())!==$expected[$relative]) self::fail('LOADED_SOURCE_UNVERIFIED');
        }
        foreach(self::FUNCTIONS as $name=>$relative) {
            if(!isset($expected[$relative]) || !function_exists($name)) self::fail('LOADED_SOURCE_UNVERIFIED');
            $reflection=new \ReflectionFunction($name);
            if($reflection->getName()!==$name || realpath((string)$reflection->getFileName())!==$expected[$relative]) self::fail('LOADED_SOURCE_UNVERIFIED');
        }
    }
    public function assertCurrent(\BSRE\ClosedRetention\LeaseBoundWpdb $db): void
    {
        global $wpdb;
        $this->sources();
        if($db!==$this->db || $wpdb!==$db || get_class($db)!=='BSRE\\ClosedRetention\\LeaseBoundWpdb'
            || $db->prefix!==$this->prefix || !defined('DB_NAME') || DB_NAME!==$this->database) self::fail('CONNECTION_CHANGED');
        $this->executionContext();
        try {
            if(!G\enabled() || !T\selected() || !T\ready()) self::fail('PROFILE_UNREADY');
            $this->noInterceptors();
            $store=G\repository();
            if(get_class($store)!=='BSRE\\SharedRepository\\BoundRepository' || G\Runtime::$db!==$db || G\Runtime::$prefix!==$this->prefix
                || G\Runtime::$database!==$this->database || G\Runtime::$store!==$store || G\Runtime::$schemaChecked!==true || P\Runtime::$store!==$store
                || $store->database()!==$db || E\consent_repository()!==$store || P\repository()!==$store
                || $store->admissionContract()!==A\CONTRACT || get_option('bsre_consent_schema_version')!=='2'
                || get_option(G\SCHEMA_OPTION)!==G\SCHEMA_VERSION) self::fail('COMMON_STORE_UNVERIFIED');
            $this->noInterceptors();
            if(G\inspect($db,true)!==[]) self::fail('COMMON_STORE_UNVERIFIED');
            $this->noInterceptors();
            $gate=A\configuration();
            if(($gate['mode']??null)!=='ENFORCED' || ($gate['contract']??null)!=='bsre-retention-admission-v1'
                || ($gate['max_age_seconds']??null)!==900 || !is_string($gate['generation']??null) || !preg_match('/^[a-f0-9]{64}$/D',$gate['generation'])
                || !is_string($gate['audience']??null) || !preg_match('/^[a-f0-9]{64}$/D',$gate['audience'])
                || !is_int($gate['activated_at']??null) || $gate['activated_at']<1 || $gate['activated_at']>time()) self::fail('ADMISSION_UNVERIFIED');
            if($this->admission!==null && $this->admission!==$gate) self::fail('ADMISSION_CHANGED');
            $readback=A\readback();
            if(($readback['store_installed']??null)!==true || array_intersect_key($readback,$gate)!==$gate) self::fail('ADMISSION_STORE_UNVERIFIED');
            // A.readback's routes_installed describes pre-G3 callbacks. Validate the five
            // final G3 owners directly; do not weaken a false readback into a true flag.
            $routes=rest_get_server()->get_routes();
            foreach(['/context'=>'context','/lead'=>'receive_legacy','/purpose-lead'=>'receive_purpose','/receipt-recovery/proof'=>'proof','/receipt-recovery/status'=>'status'] as $suffix=>$callback) {
                $callbacks=[];
                foreach($routes['/bsre/v1'.$suffix]??[] as $handler) if(is_array($handler) && is_array($handler['methods']??null) && ($handler['methods']['POST']??false)) $callbacks[]=$handler['callback']??null;
                if($callbacks!==['BSRE\\ProfileTransport\\'.$callback]) self::fail('ROUTE_OWNER_CHANGED');
            }
            $this->executionContext();
            $this->admission??=$gate;
        } catch(\Throwable $error) {
            if($error instanceof \BSRE\ClosedRetention\Failure && str_starts_with($error->getMessage(),'CANONICAL_PRODUCER_')) throw $error;
            self::fail('PROFILE_READBACK_UNVERIFIED');
        }
    }
    private function noInterceptors(): void
    {
        if((defined('SAVEQUERIES')&&SAVEQUERIES) || ($this->db->save_queries??false)) self::fail('QUERY_LOGGING_ENABLED');
        global $wp_filter;
        if(!function_exists('has_filter') || !is_array($wp_filter)) self::fail('QUERY_INTERCEPTOR_UNVERIFIED');
        // No global observer is accepted. Inspect the raw core hook container rather
        // than treating a callback's priority 0 as falsy absence.
        $all=$wp_filter['all']??null;
        if($all!==null && (!is_object($all) || get_class($all)!=='WP_Hook' || !is_array($all->callbacks) || $all->callbacks!==[])) self::fail('QUERY_INTERCEPTOR_UNVERIFIED');
        $hook=$wp_filter['query']??null;
        if($hook===null) return;
        if(!is_object($hook) || get_class($hook)!=='WP_Hook' || !is_array($hook->callbacks)) self::fail('QUERY_INTERCEPTOR_UNVERIFIED');
        if($hook->callbacks===[]) return;
        if(array_keys($hook->callbacks)!==[0] || !is_array($hook->callbacks[0]) || count($hook->callbacks[0])!==1) self::fail('QUERY_INTERCEPTOR_UNVERIFIED');
        $entries=array_values($hook->callbacks[0]);$entry=$entries[0];
        if(!is_array($entry)) self::fail('QUERY_INTERCEPTOR_UNVERIFIED');
        $keys=array_keys($entry);sort($keys);
        $callback=$entry['function']??null;
        if($keys!==['accepted_args','function'] || ($entry['accepted_args']??null)!==1 || !is_array($callback) || array_keys($callback)!==[0,1]
            || $callback[0]!==$this->db || $callback[1]!=='remove_placeholder_escape') self::fail('QUERY_INTERCEPTOR_UNVERIFIED');
        // prepare() itself installs this sole mandatory core unescape callback.
        // It is not an arbitrary query interceptor: bind inherited methods to the
        // exact class-wpdb.php bytes from the pinned WordPress 7.1.4 archive.
        if(!defined('ABSPATH') || !is_string(ABSPATH) || !defined('WPINC') || !is_string(WPINC)) self::fail('QUERY_INTERCEPTOR_UNVERIFIED');
        $core=realpath(ABSPATH.WPINC.'/class-wpdb.php');
        if($core===false || !is_file($core) || !hash_equals(self::WPDB_CORE_SHA256,(string)hash_file('sha256',$core))) self::fail('QUERY_INTERCEPTOR_UNVERIFIED');
        try {
            foreach(['prepare','add_placeholder_escape','placeholder_escape','remove_placeholder_escape'] as $name) {
                $method=new \ReflectionMethod($this->db,$name);
                if($method->getDeclaringClass()->getName()!=='wpdb' || !$method->isPublic() || $method->isStatic()
                    || realpath((string)$method->getFileName())!==$core) self::fail('QUERY_INTERCEPTOR_UNVERIFIED');
            }
        } catch(\Throwable $error) { self::fail('QUERY_INTERCEPTOR_UNVERIFIED'); }
    }
    /** Inspection only: never starts a transaction, takes a lock or grants custody. */
    private function executionContext(): void
    {
        global $wpdb;
        $db=$this->db;
        if($wpdb!==$db || $db->prefix!==$this->prefix || !defined('DB_NAME') || DB_NAME!==$this->database) self::fail('CONNECTION_CHANGED');
        $this->noInterceptors();$db->last_error='';
        $state=$db->get_row('SELECT DATABASE() AS selected_database,CONNECTION_ID() AS connection_id,@@session.in_transaction AS in_transaction',ARRAY_A);
        if($db->last_error!=='' || !is_array($state) || ($state['selected_database']??null)!==$this->database
            || !preg_match('/^[1-9][0-9]*$/D',(string)($state['connection_id']??'')) || !in_array((string)($state['in_transaction']??''),['0','1'],true)) self::fail('DATABASE_OR_TRANSACTION_UNVERIFIED');
        if(!$db->custodyIsActive()) {
            if((string)$state['in_transaction']!=='0') self::fail('TRANSACTION_CUSTODY_REQUIRED');
            return;
        }
        $id=$db->custodyConnectionId();
        if($id===null || (string)$state['connection_id']!==$id || !function_exists('home_url')) self::fail('CUSTODY_LOCK_UNVERIFIED');
        $origin=rtrim(home_url(),'/');
        if(!in_array($origin,['https://blackswanrealestate.ae','https://www.blackswanrealestate.ae'],true)) self::fail('CUSTODY_ORIGIN_UNVERIFIED');
        $name='bsre-g5-'.substr(hash('sha256','bsre-g5-durable-v1|'.$this->database.'|'.$this->prefix.'|'.$origin),0,48);
        $this->noInterceptors();$db->last_error='';
        $owner=$db->get_var($db->prepare('SELECT IS_USED_LOCK(%s)',$name));
        if($db->last_error!=='' || (string)$owner!==$id) self::fail('CUSTODY_LOCK_UNVERIFIED');
    }
    public function assertPurposeRecord(array $row): void
    {
        $this->assertCurrent($this->db);
        $version=$row['purpose_version']??null;
        if(!in_array($version,[0,1,'0','1'],true)) self::fail('PURPOSE_RECORD_INVALID');
        foreach(['purpose_hash','purpose_record_hash','purpose_json'] as $key) if(!array_key_exists($key,$row)) self::fail('PURPOSE_RECORD_INVALID');
        foreach(['known','eligible','analytics','ad_measurement'] as $key) if(!in_array($row[$key]??null,[0,1,'0','1'],true)) self::fail('PURPOSE_RECORD_INVALID');
        if((int)$row['known']===0 && ((int)$row['eligible']!==0 || (int)$row['analytics']!==0 || (int)$row['ad_measurement']!==0
            || (array_key_exists('preference_expires_at',$row) && self::uint($row['preference_expires_at'])!==0))) self::fail('PURPOSE_RECORD_INVALID');
        if(array_key_exists('personalization',$row) && !in_array($row['personalization'],[0,'0'],true)) self::fail('PURPOSE_RECORD_INVALID');
        if((int)$version===0) {
            if($row['purpose_hash']!=='' || $row['purpose_record_hash']!=='' || !in_array($row['purpose_json'],['',null],true)) self::fail('PURPOSE_RECORD_INVALID');
            return;
        }
        try {
            P\assert_record($row);
            $record=json_decode($row['purpose_json'],false,16,JSON_THROW_ON_ERROR);
            $created=self::uint($row['created_at']??null);
            if(!P\exact_object($record,['version','analytics','advertising']) || $record->version!==1
                || $created<1 || $created>time() || !is_string($row['fingerprint']??null) || !preg_match('/^[a-f0-9]{64}$/D',$row['fingerprint'])) self::fail('PURPOSE_RECORD_INVALID');
            $receipts=[];
            foreach(['analytics'=>'analytics','advertising'=>'ad_measurement'] as $purpose=>$flag) {
                if(!P\exact_object($record->$purpose,['first','last'])) self::fail('PURPOSE_RECORD_INVALID');
                foreach(['first','last'] as $slot) {
                    $touch=$record->$purpose->$slot; if($touch===null) continue;
                    if(!P\exact_object($touch,['capture_id','decision_version','notice_version','landing_page','referrer','timestamp','parameters','original_revision','expires_at'])
                        || !is_int($touch->original_revision) || $touch->original_revision<1 || !is_int($touch->expires_at)
                        || !is_int($touch->timestamp) || $touch->timestamp<1 || $touch->expires_at<=$created
                        || $touch->expires_at<=intdiv($touch->timestamp,1000)
                        || $touch->expires_at-E\CONSENT_PREFERENCE_SECONDS>intdiv($touch->timestamp,1000)
                        || (int)($row['known']??0)!==1 || (int)($row['eligible']??0)!==1 || (int)($row[$flag]??0)!==1
                        || !is_string($row['subject_key']??null) || !preg_match('/^[a-f0-9]{64}$/D',$row['subject_key'])) self::fail('PURPOSE_RECORD_INVALID');
                    $input=clone $touch;unset($input->original_revision,$input->expires_at);
                    $normalized=P\normalize_touch($input,$purpose,$created);
                    if($normalized===null || P\canonical($normalized+['original_revision'=>$touch->original_revision,'expires_at'=>$touch->expires_at])!==P\canonical($touch)) self::fail('PURPOSE_RECORD_INVALID');
                    $identity=[$touch->original_revision,$touch->expires_at];
                    if(isset($receipts[$touch->decision_version]) && $receipts[$touch->decision_version]!==$identity) self::fail('PURPOSE_RECORD_INVALID');
                    $receipts[$touch->decision_version]=$identity;
                }
                $first=$record->$purpose->first;$last=$record->$purpose->last;
                if($first!==null && $last!==null && ($first->timestamp>$last->timestamp
                    || ($first->capture_id===$last->capture_id && P\canonical($first)!==P\canonical($last)))) self::fail('PURPOSE_RECORD_INVALID');
            }
            if(P\canonical($record)!==$row['purpose_json']) self::fail('PURPOSE_RECORD_INVALID');
        } catch(\Throwable $error) { self::fail('PURPOSE_RECORD_INVALID'); }
    }
    private static function uint($value): int
    {
        if(is_int($value) && $value>=0) return $value;
        if(is_string($value) && preg_match('/^(0|[1-9][0-9]*)$/D',$value)
            && (strlen($value)<strlen((string)PHP_INT_MAX) || (strlen($value)===strlen((string)PHP_INT_MAX) && strcmp($value,(string)PHP_INT_MAX)<=0))) return (int)$value;
        self::fail('PURPOSE_RECORD_INVALID');
    }
}
