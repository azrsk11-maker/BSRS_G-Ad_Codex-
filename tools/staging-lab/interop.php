<?php
/** Real WP /lead dispatch, synthetic pages/data, preempted mock receiver only. */
use BSRE\Enquiries as E;
$_SERVER['HTTPS'] = 'on'; $_SERVER['SERVER_PORT'] = '443';
$_SERVER['REQUEST_METHOD'] = 'POST';
require '/opt/wordpress/wp-load.php';
require '/opt/lab/consent-retention/LinkageReconciliation.php';
add_filter('home_url', fn($url, $path) => 'https://blackswanrealestate.ae' . ($path === '' ? '' : '/' . ltrim($path, '/')), 10, 2);
$checks = []; $calls = 0; $lose_ack = false; $last_receipt = null;
function receive_check(string $name, bool $ok): void {
    global $checks;
    if (!$ok) throw new RuntimeException('Receive check failed: ' . $name);
    $checks[$name] = true;
}
wp_set_current_user(get_user_by('login', 'synthetic_owner')->ID);
$GLOBALS['wp_rewrite']->set_permalink_structure('/%postname%/');
$drafts = E\ensure_drafts(false);
foreach ($drafts['pages'] as $id) wp_update_post(['ID' => $id, 'post_status' => 'publish']);
$privacy = wp_insert_post(['post_type' => 'page', 'post_status' => 'publish', 'post_name' => 'synthetic-privacy', 'post_title' => 'SYNTHETIC LAB NOTICE']);
define('BSRE_PRIVACY_NOTICE_PAGE_ID', $privacy);
define('BSRE_LEAD_RECEIVER_URL', 'https://script.google.com/macros/s/BSRE_SYNTHETIC_NOT_DEPLOYED/exec');
define('BSRE_LEAD_HMAC_SECRET', str_repeat('synthetic-key-', 4));
define('BSRE_ROUTING_ENABLED', true);
receive_check('five_synthetic_native_paths', count(E\live_paths()) === 5);
receive_check('synthetic_routing_ready', E\ready());
wp_set_current_user(0);

$process = proc_open(['node', '/opt/lab/receiver-bridge.mjs'], [0=>['pipe','r'],1=>['pipe','w'],2=>STDERR], $pipes);
if (!is_resource($process)) throw new RuntimeException('Bridge could not start');
stream_set_timeout($pipes[1], 5);
function receiver_bridge(array $command): array {
 global $pipes;
 $line = wp_json_encode($command) . "\n";
 if (fwrite($pipes[0], $line) !== strlen($line)) throw new RuntimeException('Bridge write failed');
 fflush($pipes[0]); $reply = fgets($pipes[1], 1000000);
 if ($reply === false || !str_ends_with($reply, "\n")) throw new RuntimeException('Bridge reply missing or truncated');
 return json_decode($reply, true, 512, JSON_THROW_ON_ERROR);
}
add_filter('pre_http_request', function($pre, $args, $url) use (&$calls, &$lose_ack, &$last_receipt) {
 receive_check('pipe_destination_only', $url === BSRE_LEAD_RECEIVER_URL); $calls++;
 $last_receipt = receiver_bridge(['op'=>'post','raw'=>$args['body']]);
 receive_check('pinned_receiver_accepts_wordpress_envelope', ($last_receipt['accepted'] ?? false) === true);
 if ($lose_ack) { $lose_ack = false; return new WP_Error('SYNTHETIC_LOST_ACK'); }
 return ['headers'=>[], 'body'=>wp_json_encode($last_receipt), 'response'=>['code'=>200]];
}, PHP_INT_MAX, 3);
function submit_synthetic(string $raw, ?string $csrf = null): WP_REST_Response {
    $r = new WP_REST_Request('POST', '/bsre/v1/lead');
    foreach (['origin' => 'https://blackswanrealestate.ae', 'content-type' => 'application/json', 'sec-fetch-site' => 'same-origin', 'x-bsre-csrf' => $csrf ?? E\csrf_token($_COOKIE[E\COOKIE], time() - 3, wp_salt('auth'))] as $k => $v) $r->set_header($k, $v);
    $r->set_body($raw);
    return rest_do_request($r);
}
$timelines = ['off-plan' => 'Within 1 month', 'resale' => 'Within 1 month', 'rent' => 'Immediate / move now', 'sell' => 'As soon as practical', 'let' => 'Vacant / available to discuss now'];
$requestIds = [];
$index = 110;
foreach (E\SERVICES as $slug => $service) {
    $_SERVER['REMOTE_ADDR'] = '198.51.100.' . $index++;
    $_COOKIE = [E\COOKIE => bin2hex(random_bytes(32))];
    $p = ['request_id' => wp_generate_uuid4(), 'role' => $service['role'], 'name' => 'TEST synthetic ' . $slug, 'phone' => '+971500000000', 'email' => 'fixture@example.invalid', 'country' => 'UAE', 'area' => 'Synthetic fixture', 'budget' => 'To discuss', 'timeline' => $timelines[$slug], 'funding' => 'To discuss', 'property_type' => 'Apartment', 'property_details' => 'SYNTHETIC NOT INVENTORY', 'authority' => in_array($slug, ['sell', 'let']) ? 'owner' : '', 'contact_consent' => true, 'marketing_consent' => false, 'campaign' => 'SYNTHETIC_LAB_ONLY', 'landing_page' => 'https://blackswanrealestate.ae/enquire/' . $slug . '/', 'website' => '', 'started_at' => (time() - 5) * 1000];

 $p['name'] = "TEST synthetic caf\u{00e9} \u{1f3e0}";
 $requestIds[] = $p['request_id'];
 $raw = wp_json_encode($p); $accepted = submit_synthetic($raw);
 receive_check($slug . '_actual_receipt', $accepted->get_status() === 200 && $accepted->get_data()['lead_id'] === $last_receipt['lead_id'] && $accepted->get_data()['event_id'] === $last_receipt['event_id']);
 receive_check($slug . '_measurement_excluded', $accepted->get_data()['measurement_eligible'] === false);
 $retry = submit_synthetic($raw);
 receive_check($slug . '_same_receipt', $retry->get_data()['lead_id'] === $accepted->get_data()['lead_id']);
}
$_SERVER['REMOTE_ADDR'] = '198.51.100.199'; $_COOKIE = [E\COOKIE => bin2hex(random_bytes(32))];
$p['request_id'] = wp_generate_uuid4(); $requestIds[] = $p['request_id']; $raw = wp_json_encode($p); $lose_ack = true;
$lost = submit_synthetic($raw); $stored_receipt = $last_receipt;
receive_check('lost_ack_retryable', $lost->get_status() === 503 && $lost->get_data()['retryable'] === true);
$recovered = submit_synthetic($raw);
receive_check('durable_receipt_reused', $recovered->get_status() === 200 && $recovered->get_data()['lead_id'] === $stored_receipt['lead_id']);
$state = receiver_bridge(['op'=>'outbox']);
receive_check('outbox_batch_cap', count($state['mail']) === 5);
$state = receiver_bridge(['op'=>'outbox']);
receive_check('one_row_mail_per_request', count($state['rows']) === 6 && count($state['mail']) === 6);
foreach ($state['rows'] as $i=>$row) {
 $body = $state['mail'][$i]['body']; $payload = json_decode($row[5], true, 512, JSON_THROW_ON_ERROR);
 receive_check('row_' . $i . '_schema_sent', count($row) === 26 && $row[6] === 'SENT' && $row[7] === 1);
 receive_check('row_' . $i . '_same_id_email', str_contains($body, 'Lead ID: ' . $row[1]) && str_contains($body, 'Event ID: ' . $row[2]));
 receive_check('row_' . $i . '_unicode', $payload['name'] === "TEST synthetic caf\u{00e9} \u{1f3e0}" && str_contains($body, $payload['name']));
}
$again = receiver_bridge(['op'=>'outbox']);
receive_check('no_duplicate_mail', count($again['mail']) === 6);

$slots=implode(',',array_fill(0,count($requestIds),'%s'));
$wpRows=$wpdb->get_results($wpdb->prepare("SELECT * FROM {$wpdb->prefix}bsre_consent_captures WHERE request_id IN ({$slots}) ORDER BY request_id",...$requestIds),ARRAY_A);
$linkage=['source'=>'SYNTHETIC_PIPE_SESSION','captures'=>$wpRows,'receiver_headers'=>$again['headers'],'receiver_rows'=>$again['rows']];
$report=BSRE\RetentionReview\LinkageReconciliation::assess($linkage);
receive_check('actual_capture_receiver_pairs_linked', count($wpRows)===6 && $report['matched_request_receipts']===6);
$rawHashes=array_column($wpRows,'fingerprint','request_id'); $distinct=0;
foreach($again['rows'] as $row)if($rawHashes[strtolower($row[0])]!==$row[4])$distinct++;
receive_check('actual_raw_normalized_domains_distinct', $distinct===6 && $report['fingerprint_domains']==='WORDPRESS_RAW_AND_RECEIVER_NORMALIZED_DISTINCT');
receive_check('unknown_actual_subjects_hold_exclusion', $report['global_linkage_hold'] && $report['issues']['CAPTURE_SUBJECT_UNKNOWN']===6 && !$report['deletion_authorized']);
$gap=$linkage; array_pop($gap['captures']); $diagnostic=BSRE\RetentionReview\LinkageReconciliation::assess($gap);
receive_check('missing_actual_capture_held', $diagnostic['issues']['CAPTURE_MISSING']===1 && $diagnostic['global_linkage_hold']);
$gap=$linkage; $gap['captures'][0]['event_id']='evt_77777777-7777-4777-8777-777777777777'; $diagnostic=BSRE\RetentionReview\LinkageReconciliation::assess($gap);
receive_check('conflicting_actual_receipt_held', $diagnostic['issues']['RECEIPT_ID_CONFLICT']===1);
$gap=$linkage; $gap['receiver_rows'][0][5].=' '; $diagnostic=BSRE\RetentionReview\LinkageReconciliation::assess($gap);
receive_check('corrupt_actual_normalized_payload_held', $diagnostic['issues']['RECEIVER_PAYLOAD_DIGEST_MISMATCH']===1);
$gap=$linkage; $gap['receiver_rows'][0][6]='AMBIGUOUS'; $diagnostic=BSRE\RetentionReview\LinkageReconciliation::assess($gap);
receive_check('actual_outbox_status_is_not_delivery_proof', $diagnostic['outbox_holds']===1 && !$diagnostic['mail_delivery_verified']);
$redacted=json_encode($report,JSON_THROW_ON_ERROR); $privateAbsent=true;
foreach($again['rows'] as $row)foreach([$row[0],$row[1],$row[2]] as $identifier)if(str_contains($redacted,$identifier))$privateAbsent=false;
receive_check('linkage_reports_omit_actual_identifiers', $privateAbsent && !$report['historical_coverage_verified'] && !$report['import_authorized']);
fclose($pipes[0]); fclose($pipes[1]);
receive_check('bridge_clean_exit', proc_close($process) === 0);
echo wp_json_encode(['phase'=>'wordpress_receiver_interop','status'=>'PASS','checks'=>$checks,'synthetic_only'=>true,'google_services_are_doubles'=>true,'network_transport_is_pipe'=>true,'live_delivery_accepted'=>false,'production_acceptance'=>false]) . "\n";
