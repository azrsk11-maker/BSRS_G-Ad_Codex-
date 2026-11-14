<?php
// Native WordPress acceptance. Run only AFTER the kernel-isolated disposable DB is installed.
if (PHP_SAPI !== 'cli' || !is_dir('/sys/class/net') ||
    array_values(array_diff(scandir('/sys/class/net'), ['.', '..'])) !== ['lo'] ||
    !is_readable('/proc/net/route') || count(preg_split('/\r?\n/', trim(file_get_contents('/proc/net/route')))) !== 1 ||
    !function_exists('posix_geteuid') || posix_geteuid() === 0 || !is_file('/opt/wordpress/wp-load.php')) {
    throw new RuntimeException('This acceptance harness requires the disposable network-none lab.');
}
require '/opt/wordpress/wp-load.php';
$writer = is_file(__DIR__ . '/native-draft-writer.php') ? __DIR__ . '/native-draft-writer.php' : dirname(__DIR__) . '/native-draft-writer.php';
require $writer;
use BSRE\NativeDraftLab as Writer;

$checks = [];
function writer_check(string $name, bool $ok): void {
    global $checks;
    if (!$ok) throw new RuntimeException('Native draft check failed: ' . $name);
    $checks[$name] = true;
}
function writer_reject(string $name, callable $callback, string $fragment): void {
    try { $callback(); }
    catch (RuntimeException $error) { writer_check($name, str_contains($error->getMessage(), $fragment)); return; }
    throw new RuntimeException('Expected native draft rejection: ' . $name);
}
function writer_content(string $label): array {
    return ['post_title' => 'SYNTHETIC LAB ' . $label,
        'post_content' => '<!-- BSRE SYNTHETIC LAB ONLY --><p>' . $label . '</p>', 'post_excerpt' => 'Synthetic fixture'];
}
function writer_request(string $key, string $campaign, string $action, ?array $state, string $label = 'First'): array {
    return ['operation_key' => $key, 'campaign_key' => $campaign, 'action' => $action,
        'expected' => Writer\expectation($state), 'content' => writer_content($label)];
}
function writer_other_connection(): mysqli {
    $connection = new mysqli('localhost', 'root', '', 'bsre_synthetic', 0, '/tmp/bsre.sock');
    $connection->query('SET SESSION innodb_lock_wait_timeout=1');
    return $connection;
}
function writer_blocked(mysqli $connection, string $query): bool {
    try { return $connection->query($query) === false && $connection->errno === 1205; }
    catch (mysqli_sql_exception $error) { return $error->getCode() === 1205; }
}

$owner = get_user_by('login', 'synthetic_owner');
writer_check('synthetic_owner_exists', $owner !== false);
wp_set_current_user($owner->ID);
$nonce = wp_create_nonce('bsre_native_draft_lab');
writer_reject('disabled_by_default', fn() => Writer\initialize($nonce), 'disabled');
define('BSRE_NATIVE_DRAFT_WRITER_ENABLED', true);
writer_reject('nonce_required', fn() => Writer\initialize('invalid'), 'administrator and nonce');
wp_set_current_user(0);
writer_reject('administrator_required', fn() => Writer\initialize($nonce), 'administrator and nonce');
wp_set_current_user($owner->ID);
Writer\initialize($nonce);

$protected_id = wp_insert_post(['post_type' => 'page', 'post_status' => 'publish', 'post_name' => 'writer-protected-main',
    'post_title' => 'Synthetic published main-site control', 'post_content' => 'Preserve this fixture.'], true);
$protected = Writer\snapshot((int) $protected_id);
$parent = wp_insert_post(['post_type' => 'page', 'post_status' => 'draft', 'post_name' => 'synthetic-native-writer',
    'post_title' => 'SYNTHETIC LAB explicitly supplied parent', 'meta_input' => ['_bsre_native_lab_parent' => Writer\SCHEMA]], true);
writer_check('explicit_parent_created_by_harness_only', is_int($parent) && $parent > 0);
$manifest = ['schema' => Writer\SCHEMA, 'mode' => 'SYNTHETIC_LAB_ONLY', 'site_origin' => 'http://bsre.invalid', 'pages' => []];
foreach ([1,2,3,4,5] as $number) {
    $campaign = sprintf('BSRE-C%04d', $number);
    $manifest['pages'][] = ['campaign_key' => $campaign, 'landing_page_id' => sprintf('BSRE-LP%04d', $number),
        'parent_cms_id' => $parent, 'parent_state_sha256' => Writer\digest(Writer\snapshot($parent)),
        'post_name' => strtolower($campaign), 'path' => '/synthetic-native-writer/' . strtolower($campaign) . '/'];
}
$apply = fn(array $request, ?array $plan = null) => Writer\apply($plan ?? $manifest, $request, $nonce);
$create = writer_request('lab-create-0001', 'BSRE-C0001', 'create', null);
$bad = $manifest; $bad['site_origin'] = 'https://blackswanrealestate.ae';
writer_reject('production_manifest_rejected', fn() => $apply($create, $bad), 'synthetic allowlist');
$bad = $manifest; $bad['pages'][0]['parent_cms_id'] = $protected_id;
writer_reject('published_parent_rejected', fn() => $apply($create, $bad), 'synthetic parent');
$bad = $manifest; $bad['pages'][0]['path'] = '/invented/route/';
writer_reject('invented_route_rejected', fn() => $apply($create, $bad), 'synthetic parent');
$bad = $manifest; $bad['pages'][0]['landing_page_id'] = 'BSRE-LP0002';
writer_reject('swapped_identity_rejected', fn() => $apply($create, $bad), 'binding');
$bad_request = $create; $bad_request['post_status'] = 'publish';
writer_reject('publication_field_rejected', fn() => $apply($bad_request), 'Unexpected');
$bad_request = $create; $bad_request['content']['post_content'] .= '<script>alert(1)</script>';
writer_reject('active_content_rejected', fn() => $apply($bad_request), 'Inert synthetic');
foreach (['<svg onload="alert(1)"></svg>', '<p onclick="alert(1)">Bad</p>', '<input value="Bad">', '[synthetic_shortcode]'] as $active) {
    $bad_request = $create; $bad_request['content']['post_content'] .= $active;
    writer_reject('positive_content_allowlist_' . count($checks), fn() => $apply($bad_request), 'Inert synthetic');
}
$lock_probe = static function ($data) use ($parent, $protected_id) {
    if (($data['post_name'] ?? '') !== 'bsre-c0001') return $data;
    $other = writer_other_connection();
    writer_check('second_connection_parent_metadata_blocked', writer_blocked($other,
        "UPDATE synthetic_postmeta SET meta_value='outside-parent-change' WHERE post_id=" . $parent . " AND meta_key='_bsre_native_lab_parent'"));
    writer_check('second_connection_new_ownership_row_blocked', writer_blocked($other,
        "INSERT INTO synthetic_postmeta(post_id,meta_key,meta_value) VALUES(" . $protected_id . ",'_bsre_campaign_key','BSRE-C0001')"));
    $other->close();
    return $data;
};
add_filter('wp_insert_post_data', $lock_probe);

$created = $apply($create); $id = $created['cms_page_id']; $first = Writer\snapshot($id);
remove_filter('wp_insert_post_data', $lock_probe);
writer_check('native_draft_exact_identity', $first['post']['post_status'] === 'draft' && $first['post']['post_type'] === 'page' &&
    (int) $first['post']['post_parent'] === $parent && $first['post']['post_name'] === 'bsre-c0001' &&
    get_page_uri($id) === 'synthetic-native-writer/bsre-c0001' && get_post_meta($id, '_bsre_campaign_key', true) === 'BSRE-C0001' &&
    get_post_meta($id, '_bsre_landing_page_id', true) === 'BSRE-LP0001');
writer_check('native_revision_and_hash_receipt', $created['before'] === Writer\expectation(null) &&
    $created['after'] === Writer\expectation($first) && $created['after']['latest_revision_id'] !== null);
$journal = Writer\journal('lab-create-0001');
writer_check('durable_before_after_journal', $journal['state'] === 'APPLIED' && $journal['before'] === null &&
    Writer\digest($journal['after']) === Writer\digest($first));
// Deliberately discard the first response: replay discovers the committed native result.
writer_check('lost_create_ack_replay_exact', $apply($create) === $created && Writer\snapshot($id) === $first);
$changed = $create; $changed['content'] = writer_content('Changed request');
writer_reject('operation_body_conflict_rejected', fn() => $apply($changed), 'changed request');
writer_reject('second_create_cannot_replace_draft', fn() => $apply(writer_request('lab-create-duplicate', 'BSRE-C0001', 'create', $first)), 'Create requires absence');
$update = writer_request('lab-update-0001', 'BSRE-C0001', 'update', $first, 'Second');
$wrong_revision = $update; $wrong_revision['expected']['latest_revision_id']++;
writer_reject('exact_revision_required', fn() => $apply($wrong_revision), 'precondition');
$updated = $apply($update); $second = Writer\snapshot($id);
writer_check('native_update_preserves_id_and_adds_revision', $updated['cms_page_id'] === $id &&
    $second['post']['post_content'] === writer_content('Second')['post_content'] && count($second['revisions']) > count($first['revisions']) &&
    $updated['before']['latest_revision_id'] === Writer\latest($first) && $updated['after']['latest_revision_id'] === Writer\latest($second));
writer_check('lost_update_ack_replay_exact', $apply($update) === $updated && Writer\snapshot($id) === $second);
$restore_update = ['operation_key' => 'lab-restore-update', 'campaign_key' => 'BSRE-C0001', 'action' => 'restore',
    'expected' => Writer\expectation($second), 'restore_operation_key' => 'lab-update-0001'];
$restored = $apply($restore_update); $third = Writer\snapshot($id);
writer_check('update_restore_uses_exact_journal_content', $restored['cms_page_id'] === $id &&
    Writer\content_hash($third) === Writer\content_hash($first) && count($third['revisions']) > count($second['revisions']) &&
    $restored['before'] === Writer\expectation($second) && $restored['after'] === Writer\expectation($third));
writer_check('restore_replay_exact_revision', $apply($restore_update) === $restored && Writer\snapshot($id) === $third);
writer_reject('old_create_replay_rejects_intervening_update', fn() => $apply($create), 'Intervening edit');

$noop_update = writer_request('lab-noop-update', 'BSRE-C0001', 'update', $third, 'First');
$noop_result = $apply($noop_update); $noop_state = Writer\snapshot($id);
writer_check('native_noop_update_keeps_exact_revision', Writer\latest($noop_state) === Writer\latest($third) &&
    $noop_state['revisions'] === $third['revisions'] && $noop_result['after'] === Writer\expectation($noop_state));
$noop_restore = ['operation_key' => 'lab-noop-restore', 'campaign_key' => 'BSRE-C0001', 'action' => 'restore',
    'expected' => Writer\expectation($noop_state), 'restore_operation_key' => 'lab-noop-update'];
$noop_restored = $apply($noop_restore); $third = Writer\snapshot($id);
writer_check('native_noop_restore_receipt_has_no_new_revision', $noop_restored['restore_outcome'] === 'PRIOR_CONTENT_ALREADY_PRESENT_NO_NEW_REVISION' &&
    Writer\latest($third) === Writer\latest($noop_state) && $third['revisions'] === $noop_state['revisions'] &&
    $noop_restored['before'] === Writer\expectation($noop_state) && $noop_restored['after'] === Writer\expectation($third));
writer_check('native_noop_restore_ack_replay_stable', $apply($noop_restore) === $noop_restored && Writer\snapshot($id) === $third);

$no_revisions = static fn() => 0;
add_filter('wp_revisions_to_keep', $no_revisions);
$revision_failure = writer_request('lab-revision-disabled', 'BSRE-C0001', 'update', $third, 'Revision disabled');
writer_reject('disabled_native_revision_blocks_apply', fn() => $apply($revision_failure), 'Native revisions required');
remove_filter('wp_revisions_to_keep', $no_revisions);
writer_check('disabled_revision_rolls_back_native_mutation', Writer\snapshot($id) === $third && Writer\journal('lab-revision-disabled')['state'] === 'PREPARED');

$create_two = writer_request('lab-create-0002', 'BSRE-C0002', 'create', null, 'Second disposable page — 🦢');
$created_two = $apply($create_two); $second_id = $created_two['cms_page_id']; $created_two_state = Writer\snapshot($second_id);
$restore_create = ['operation_key' => 'lab-restore-create', 'campaign_key' => 'BSRE-C0002', 'action' => 'restore',
    'expected' => Writer\expectation(Writer\snapshot($second_id)), 'restore_operation_key' => 'lab-create-0002'];
$held = $apply($restore_create); $held_state = Writer\snapshot($second_id);
writer_check('create_restore_retains_held_draft', $held_state !== null && $held_state['post']['post_status'] === 'draft' &&
    $held['cms_page_id'] === $second_id && $held['after'] === Writer\expectation($held_state) &&
    $held['restore_outcome'] === 'HELD_CREATED_DRAFT_REQUIRES_RECONCILIATION' &&
    get_post_meta($second_id, '_bsre_native_writer_hold', true) === 'RESTORED_CREATE_REQUIRES_RECONCILIATION');
writer_check('create_restore_preserves_content_and_revision_trail', Writer\content_hash($held_state) === Writer\content_hash($created_two_state) &&
    $held_state['revisions'] === $created_two_state['revisions'] && Writer\journal('lab-create-0002')['before'] === null);
writer_check('create_restore_ack_replay_stable', $apply($restore_create) === $held && Writer\snapshot($second_id) === $held_state);
writer_reject('held_created_draft_cannot_resume_implicitly', fn() => $apply(writer_request('lab-held-update', 'BSRE-C0002', 'update', $held_state, 'Held')), 'requires reconciliation');

$collision = wp_insert_post(['post_type' => 'page', 'post_status' => 'draft', 'post_parent' => $parent, 'post_name' => 'bsre-c0003', 'post_title' => 'Synthetic unmanaged collision'], true);
$collision_before = Writer\snapshot($collision);
writer_reject('unmanaged_route_preserved', fn() => $apply(writer_request('lab-collision-0003', 'BSRE-C0003', 'create', null)), 'route is preserved');
writer_check('unmanaged_draft_unchanged', Writer\snapshot($collision) === $collision_before);

$lost_connection = writer_request('lab-lost-connection', 'BSRE-C0005', 'create', null, 'Connection loss');
$disconnect = static function ($data) {
    global $wpdb;
    if (($data['post_name'] ?? '') !== 'bsre-c0005') return $data;
    $session = (int) $wpdb->get_var('SELECT CONNECTION_ID()');
    $other = writer_other_connection();
    writer_check('dedicated_session_reconnect_disabled', $wpdb instanceof Writer\TransactionDatabase && $wpdb->check_connection() === false);
    $other->query('KILL CONNECTION ' . $session); $other->close();
    return $data;
};
add_filter('wp_insert_post_data', $disconnect);
writer_reject('lost_database_session_does_not_retry_write', fn() => $apply($lost_connection), 'Native synthetic draft save failed');
remove_filter('wp_insert_post_data', $disconnect);
writer_check('killed_session_retains_prepared_intent', Writer\journal('lab-lost-connection')['state'] === 'PREPARED' && Writer\target($manifest['pages'][4]) === null);
$connection_recovered = $apply($lost_connection);
writer_check('killed_session_exact_retry_completes_once', $connection_recovered['after']['cms_page_id'] > 0 && $apply($lost_connection) === $connection_recovered);

$failure = writer_request('lab-rollback-update', 'BSRE-C0001', 'update', $third, 'FAIL_ONCE');
$throw_after_write = static function ($post_id, $post) use ($id): void {
    if ($post_id === $id && $post->post_title === 'SYNTHETIC LAB FAIL_ONCE') throw new RuntimeException('Injected native post-write exception.');
};
add_action('wp_after_insert_post', $throw_after_write, 10, 2);
writer_reject('native_post_write_exception_reported', fn() => $apply($failure), 'Injected native');
remove_action('wp_after_insert_post', $throw_after_write, 10);
writer_check('failure_rolls_back_page_and_revisions', Writer\snapshot($id) === $third && Writer\journal('lab-rollback-update')['state'] === 'PREPARED');
$recovered = $apply($failure); $fourth = Writer\snapshot($id);
writer_check('durable_prepared_retry_completes_once', $recovered['after'] === Writer\expectation($fourth) &&
    Writer\journal('lab-rollback-update')['state'] === 'APPLIED' && $apply($failure) === $recovered);

wp_update_post(['ID' => $id, 'post_title' => 'SYNTHETIC LAB outside edit']);
wp_cache_flush(); $outside = Writer\snapshot($id);
writer_reject('outside_edit_rejects_saved_replay', fn() => $apply($failure), 'Intervening edit');
writer_reject('outside_edit_rejects_stale_update', fn() => $apply(writer_request('lab-stale-update', 'BSRE-C0001', 'update', $fourth, 'Stale')), 'precondition');
$stale_restore = ['operation_key' => 'lab-stale-restore', 'campaign_key' => 'BSRE-C0001', 'action' => 'restore',
    'expected' => Writer\expectation($outside), 'restore_operation_key' => 'lab-rollback-update'];
writer_reject('outside_edit_rejects_restore', fn() => $apply($stale_restore), 'Exact applied journal');
writer_check('rejected_operations_preserve_outside_edit', Writer\snapshot($id) === $outside);
wp_update_post(['ID' => $id, 'post_status' => 'publish']); wp_cache_flush();
$published = Writer\snapshot($id);
writer_reject('published_owned_page_cannot_change', fn() => $apply(writer_request('lab-published-hold', 'BSRE-C0001', 'update', $published, 'Held')), 'writer-owned synthetic drafts');
writer_check('published_page_and_main_control_unchanged', Writer\snapshot($id) === $published && Writer\snapshot($protected_id) === $protected);
writer_check('parent_unchanged', Writer\digest(Writer\snapshot($parent)) === $manifest['pages'][0]['parent_state_sha256']);

echo json_encode(['phase' => 'native_draft_writer', 'status' => 'PASS', 'checks' => $checks,
    'scope' => 'DISPOSABLE_SYNTHETIC_LAB_ONLY', 'production_authorized' => false], JSON_UNESCAPED_SLASHES) . PHP_EOL;
