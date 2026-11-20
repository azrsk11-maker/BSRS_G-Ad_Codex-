<?php
/** Inert, disposable synthetic WordPress laboratory only. No hooks or endpoints. */
namespace BSRE\NativeDraftLab;

if (!defined('ABSPATH')) return;

const SCHEMA = 'bsre-native-draft-lab-v1';

/** Never retry a transaction's statement on a new, unlocked database session. */
class TransactionDatabase extends \wpdb {
    public function check_connection($allow_bail = true) { return false; }
}

function guard(string $nonce): void {
    global $wpdb;
    if (!defined('BSRE_NATIVE_DRAFT_WRITER_ENABLED') || BSRE_NATIVE_DRAFT_WRITER_ENABLED !== true) {
        throw new \RuntimeException('Synthetic draft writer is disabled.');
    }
    // These are independent of filterable home_url(), and deliberately exclude production.
    if (PHP_SAPI !== 'cli' || !defined('WP_HOME') || WP_HOME !== 'http://bsre.invalid' ||
        !defined('WP_SITEURL') || WP_SITEURL !== 'http://bsre.invalid' ||
        !defined('DB_NAME') || DB_NAME !== 'bsre_synthetic' || $wpdb->prefix !== 'synthetic_' ||
        !defined('WP_HTTP_BLOCK_EXTERNAL') || WP_HTTP_BLOCK_EXTERNAL !== true ||
        !defined('DISABLE_WP_CRON') || DISABLE_WP_CRON !== true || is_multisite() ||
        !function_exists('posix_geteuid') || posix_geteuid() === 0 ||
        !is_dir('/sys/class/net') || array_values(array_diff(scandir('/sys/class/net'), ['.', '..'])) !== ['lo'] ||
        !is_readable('/proc/net/route') || count(preg_split('/\r?\n/', trim(file_get_contents('/proc/net/route')))) !== 1 ||
        is_writable(ABSPATH)) {
        throw new \RuntimeException('Disposable network-none synthetic lab required.');
    }
    if (!current_user_can('manage_options') || !wp_verify_nonce($nonce, 'bsre_native_draft_lab')) {
        throw new \RuntimeException('Authorized synthetic administrator and nonce required.');
    }
}

function encode($value): string {
    if (is_array($value)) {
        if (!array_is_list($value)) ksort($value, SORT_STRING);
        foreach ($value as &$item) if (is_array($item)) $item = json_decode(encode($item), true, 512, JSON_THROW_ON_ERROR);
        unset($item);
    }
    return json_encode($value, JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE | JSON_THROW_ON_ERROR);
}

function digest($value): string { return hash('sha256', encode($value)); }
function table(): string { global $wpdb; return $wpdb->prefix . 'bsre_native_draft_journal'; }
function sql(string $query): void {
    global $wpdb;
    if ($wpdb->query($query) === false) throw new \RuntimeException('Synthetic journal transaction failed.');
}
function transactional_tables(): void {
    global $wpdb;
    foreach ([$wpdb->posts, $wpdb->postmeta, table()] as $name) {
        $engine = $wpdb->get_var($wpdb->prepare('SELECT ENGINE FROM information_schema.TABLES WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME=%s', $name));
        if (strtoupper((string) $engine) !== 'INNODB') throw new \RuntimeException('Transactional synthetic tables required.');
    }
}

/** Explicit lab setup; never runs merely by including this file. */
function initialize(string $nonce): void {
    global $wpdb;
    guard($nonce);
    $journal = table();
    $charset = $wpdb->get_charset_collate();
    sql("CREATE TABLE IF NOT EXISTS `$journal` (
        operation_key varchar(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL PRIMARY KEY,
        request_sha256 char(64) NOT NULL, request_json longtext NOT NULL,
        state varchar(16) NOT NULL, before_json longtext NOT NULL, before_sha256 char(64) NOT NULL,
        after_json longtext NULL, after_sha256 char(64) NULL, cms_page_id bigint unsigned NULL
    ) ENGINE=InnoDB $charset");
    transactional_tables();
}

/** Exact DB state, including metadata row identity and the complete native revision set. */
function snapshot(int $id): ?array {
    global $wpdb;
    $post = $wpdb->get_row($wpdb->prepare("SELECT * FROM {$wpdb->posts} WHERE ID=%d", $id), ARRAY_A);
    if (!$post) return null;
    return ['post' => $post,
        'meta' => $wpdb->get_results($wpdb->prepare("SELECT meta_id,meta_key,meta_value FROM {$wpdb->postmeta} WHERE post_id=%d ORDER BY meta_id", $id), ARRAY_A),
        'revisions' => $wpdb->get_results($wpdb->prepare("SELECT * FROM {$wpdb->posts} WHERE post_parent=%d AND post_type='revision' ORDER BY ID", $id), ARRAY_A)];
}

function latest(?array $state): ?int {
    if ($state === null || !$state['revisions']) return null;
    return (int) $state['revisions'][count($state['revisions']) - 1]['ID'];
}

function expectation(?array $state): array {
    return ['cms_page_id' => $state === null ? null : (int) $state['post']['ID'],
        'state_sha256' => digest($state), 'latest_revision_id' => latest($state)];
}

function content_hash(?array $state): string {
    return digest($state === null ? null : array_intersect_key($state['post'], array_flip(['post_title', 'post_content', 'post_excerpt'])));
}

function decode_journal(array $row): array {
    foreach (['request', 'before', 'after'] as $part) {
        if ($part === 'after' && $row['after_json'] === null) continue;
        $bytes = $row[$part . '_json'];
        if (!is_string($bytes) || !hash_equals($row[$part . '_sha256'], hash('sha256', $bytes))) {
            throw new \RuntimeException('Journal integrity requires reconciliation.');
        }
        $row[$part] = json_decode($bytes, true, 512, JSON_THROW_ON_ERROR);
    }
    return $row;
}

function journal(string $key): ?array {
    global $wpdb;
    $row = $wpdb->get_row($wpdb->prepare('SELECT * FROM `' . table() . '` WHERE operation_key=%s', $key), ARRAY_A);
    return $row ? decode_journal($row) : null;
}

function receipt(array $row): array {
    $hold = false;
    foreach ($row['after']['meta'] ?? [] as $meta) {
        if ($meta['meta_key'] === '_bsre_native_writer_hold' && $meta['meta_value'] === 'RESTORED_CREATE_REQUIRES_RECONCILIATION') $hold = true;
    }
    return ['status' => 'APPLIED_SYNTHETIC_ONLY', 'operation_key' => $row['operation_key'],
        'action' => $row['request']['request']['action'], 'cms_page_id' => $row['cms_page_id'] === null ? null : (int) $row['cms_page_id'],
        'restore_outcome' => $hold ? 'HELD_CREATED_DRAFT_REQUIRES_RECONCILIATION' : ($row['request']['request']['action'] === 'restore'
            ? (latest($row['after']) !== latest($row['before']) ? 'PRIOR_CONTENT_RESTORED_WITH_NEW_REVISION' : 'PRIOR_CONTENT_ALREADY_PRESENT_NO_NEW_REVISION') : null),
        'before' => expectation($row['before']), 'after' => expectation($row['after']),
        'before_content_sha256' => content_hash($row['before']), 'after_content_sha256' => content_hash($row['after'])];
}

function binding(array $manifest, string $key): array {
    if (($manifest['schema'] ?? '') !== SCHEMA || ($manifest['mode'] ?? '') !== 'SYNTHETIC_LAB_ONLY' ||
        ($manifest['site_origin'] ?? '') !== 'http://bsre.invalid' || !is_array($manifest['pages'] ?? null) || !$manifest['pages']) {
        throw new \RuntimeException('Explicit synthetic allowlist required.');
    }
    // Retain the reviewed immutable campaign/landing pairing; lab routes need their own explicit binding.
    $registry = json_decode(file_get_contents(__DIR__ . '/native-page-manifest.json'), true, 512, JSON_THROW_ON_ERROR);
    $pairs = []; $known = [];
    foreach ($registry['pages'] as $page) {
        $pairs[] = $page['campaign_key'] . '|' . $page['landing_page_id'] . "\n";
        $known[$page['campaign_key']] = $page['landing_page_id'];
    }
    sort($pairs, SORT_STRING);
    if (hash('sha256', implode('', $pairs)) !== '495bb081af104d85f9016dc0b250b03a040bd0555922611589ffeeddd3fd6b61') {
        throw new \RuntimeException('Reviewed identity registry required.');
    }
    $seen = []; $paths = []; $selected = null;
    foreach ($manifest['pages'] as $page) {
        $campaign = $page['campaign_key'] ?? ''; $landing = $page['landing_page_id'] ?? '';
        $parent = $page['parent_cms_id'] ?? 0; $slug = $page['post_name'] ?? ''; $path = $page['path'] ?? '';
        if (!is_string($campaign) || !isset($known[$campaign]) || $known[$campaign] !== $landing || isset($seen[$campaign]) ||
            !is_int($parent) || $parent < 1 || $slug !== strtolower($campaign) ||
            !is_string($path) || !preg_match('~^/[a-z0-9-]+/[a-z0-9-]+/$~D', $path) || isset($paths[$path]) ||
            !is_string($page['parent_state_sha256'] ?? null) || !preg_match('/^[a-f0-9]{64}$/D', $page['parent_state_sha256'])) {
            throw new \RuntimeException('Invalid synthetic page binding.');
        }
        $state = snapshot($parent);
        if (!$state || $state['post']['post_type'] !== 'page' || $state['post']['post_status'] !== 'draft' ||
            get_post_meta($parent, '_bsre_native_lab_parent', true) !== SCHEMA ||
            !hash_equals($page['parent_state_sha256'], digest($state)) ||
            $path !== '/' . trim(get_page_uri($parent), '/') . '/' . $slug . '/') {
            throw new \RuntimeException('Exact existing synthetic parent and route required.');
        }
        $seen[$campaign] = true; $paths[$path] = true;
        if ($campaign === $key) $selected = $page;
    }
    if ($selected === null) throw new \RuntimeException('Page is outside the explicit allowlist.');
    return $selected;
}

function target(array $page): ?array {
    $lookup = ['post_type' => 'page', 'post_status' => ['publish','future','draft','pending','private','trash','auto-draft','inherit'],
        'fields' => 'ids', 'numberposts' => -1, 'suppress_filters' => true];
    $campaign = get_posts($lookup + ['meta_key' => '_bsre_campaign_key', 'meta_value' => $page['campaign_key']]);
    $landing = get_posts($lookup + ['meta_key' => '_bsre_landing_page_id', 'meta_value' => $page['landing_page_id']]);
    if (count($campaign) > 1 || count($landing) > 1 || $campaign !== $landing) throw new \RuntimeException('Duplicate or conflicting CMS identity.');
    $id = (int) ($campaign[0] ?? 0);
    $collision = get_page_by_path(trim($page['path'], '/'), OBJECT, 'page');
    if ($collision && (int) $collision->ID !== $id) throw new \RuntimeException('Existing CMS route is preserved.');
    if (!$id) return null;
    $state = snapshot($id);
    if (!$state || $state['post']['post_type'] !== 'page' || $state['post']['post_status'] !== 'draft' ||
        (int) $state['post']['post_parent'] !== $page['parent_cms_id'] || $state['post']['post_name'] !== $page['post_name'] ||
        get_post_meta($id, '_bsre_native_writer_owned', true) !== SCHEMA ||
        trim(get_page_uri($id), '/') !== trim($page['path'], '/')) {
        throw new \RuntimeException('Only exact writer-owned synthetic drafts may change.');
    }
    return $state;
}

function request_content(array $request): array {
    $content = $request['content'] ?? null;
    $keys = is_array($content) ? array_keys($content) : []; sort($keys);
    if (!is_array($content) || $keys !== ['post_content','post_excerpt','post_title'] ||
        !is_string($content['post_title']) || !str_starts_with($content['post_title'], 'SYNTHETIC LAB ') ||
        !is_string($content['post_content']) || !str_starts_with($content['post_content'], '<!-- BSRE SYNTHETIC LAB ONLY -->') ||
        !is_string($content['post_excerpt']) || strlen(encode($content)) > 20000 ||
        strip_tags($content['post_title']) !== $content['post_title'] || strip_tags($content['post_excerpt']) !== $content['post_excerpt'] ||
        str_contains(implode('', $content), '[') || str_contains(implode('', $content), ']')) {
        throw new \RuntimeException('Inert synthetic content fields required.');
    }
    $body = substr($content['post_content'], strlen('<!-- BSRE SYNTHETIC LAB ONLY -->'));
    if (wp_kses($body, ['p' => [], 'strong' => [], 'em' => []]) !== $body || str_contains($body, '<!--')) {
        throw new \RuntimeException('Inert synthetic content fields required.');
    }
    return $content;
}

/** Create, update, or restore one explicitly bound disposable draft. No production mode exists. */
function apply(array $manifest, array $request, string $nonce): array {
    global $wpdb;
    guard($nonce);
    $key = $request['operation_key'] ?? ''; $action = $request['action'] ?? ''; $campaign = $request['campaign_key'] ?? '';
    if (!is_string($key) || !preg_match('/^[a-z0-9][a-z0-9-]{7,63}$/D', $key) ||
        !in_array($action, ['create','update','restore'], true) || !is_string($campaign)) throw new \RuntimeException('Invalid operation.');
    $allowed = $action === 'restore' ? ['operation_key','action','campaign_key','expected','restore_operation_key'] : ['operation_key','action','campaign_key','expected','content'];
    $keys = array_keys($request); sort($keys); sort($allowed);
    if ($keys !== $allowed) throw new \RuntimeException('Unexpected operation fields.');
    $content = $action === 'restore' ? null : request_content($request);
    $encoded = encode(['manifest' => $manifest, 'request' => $request]);
    $hash = hash('sha256', $encoded); $locked = false; $transaction = false; $mutated_id = 0;
    $previous_db = $wpdb;
    $wpdb = new TransactionDatabase(DB_USER, DB_PASSWORD, DB_NAME, DB_HOST);
    $wpdb->set_prefix($previous_db->prefix);
    $wpdb->suppress_errors(true);
    try {
        transactional_tables();
        if ((string) $wpdb->get_var("SELECT GET_LOCK('bsre_native_draft_lab',0)") !== '1') throw new \RuntimeException('Another synthetic writer is active.');
        $locked = true;
        $page = binding($manifest, $campaign); $before = target($page); $old = journal($key);
        if ($old) {
            if (!hash_equals($old['request_sha256'], $hash)) throw new \RuntimeException('Operation key reused with changed request.');
            if ($old['state'] === 'APPLIED') {
                if (digest($before) !== $old['after_sha256']) throw new \RuntimeException('Intervening edit after applied operation.');
                return receipt($old);
            }
            if ($old['state'] !== 'PREPARED' || digest($before) !== $old['before_sha256']) throw new \RuntimeException('Ambiguous operation requires reconciliation.');
        }
        if (!is_array($request['expected']) || encode($request['expected']) !== encode(expectation($before))) throw new \RuntimeException('CMS identity, revision or state precondition changed.');
        if (($action === 'create') !== ($before === null)) throw new \RuntimeException('Create requires absence; update and restore require an owned draft.');
        if ($before !== null && get_post_meta((int) $before['post']['ID'], '_bsre_native_writer_hold', true) !== '') {
            throw new \RuntimeException('Held created draft requires reconciliation.');
        }
        $restore = null;
        if ($action === 'restore') {
            $restore_key = $request['restore_operation_key'];
            if (!is_string($restore_key) || !preg_match('/^[a-z0-9][a-z0-9-]{7,63}$/D', $restore_key)) throw new \RuntimeException('Invalid restore reference.');
            $restore = journal($restore_key);
            if (!$restore || $restore['state'] !== 'APPLIED' || !in_array($restore['request']['request']['action'], ['create','update'], true) ||
                $restore['request']['request']['campaign_key'] !== $campaign || digest($before) !== $restore['after_sha256'] ||
                $restore['request']['manifest'] !== json_decode(encode($manifest), true, 512, JSON_THROW_ON_ERROR)) {
                throw new \RuntimeException('Exact applied journal version required for restore.');
            }
        }
        if (!$old) {
            if ($wpdb->insert(table(), ['operation_key' => $key, 'request_sha256' => $hash, 'request_json' => $encoded,
                'state' => 'PREPARED', 'before_json' => encode($before), 'before_sha256' => digest($before)]) !== 1) {
                throw new \RuntimeException('Durable intent could not be recorded.');
            }
        }
        sql('SET TRANSACTION ISOLATION LEVEL SERIALIZABLE');
        sql('START TRANSACTION'); $transaction = true;
        // Full synthetic-table range locks also cover parent metadata and new ownership rows.
        sql("SELECT ID FROM {$wpdb->posts} FOR UPDATE");
        sql("SELECT meta_id FROM {$wpdb->postmeta} FOR UPDATE");
        $wpdb->get_row($wpdb->prepare('SELECT operation_key FROM `' . table() . '` WHERE operation_key=%s FOR UPDATE', $key));
        wp_cache_flush();
        binding($manifest, $campaign);
        if (digest(target($page)) !== digest($before)) throw new \RuntimeException('Intervening edit before mutation.');
        $id = $before === null ? 0 : (int) $before['post']['ID'];
        if ($action === 'restore' && $restore['before'] === null) {
            $mutated_id = $id;
            if (!add_post_meta($id, '_bsre_native_writer_hold', 'RESTORED_CREATE_REQUIRES_RECONCILIATION', true)) {
                throw new \RuntimeException('Created draft hold could not be recorded.');
            }
        } else {
            if ($action === 'restore') {
                $content = array_intersect_key($restore['before']['post'], array_flip(['post_title','post_content','post_excerpt']));
            }
            $data = $content + ['post_type' => 'page', 'post_status' => 'draft', 'post_parent' => $page['parent_cms_id'],
                'post_name' => $page['post_name'], 'comment_status' => 'closed', 'ping_status' => 'closed'];
            if ($id) $data['ID'] = $id;
            else $data['meta_input'] = ['_bsre_campaign_key' => $campaign, '_bsre_landing_page_id' => $page['landing_page_id'], '_bsre_native_writer_owned' => SCHEMA];
            $written = $id ? wp_update_post(wp_slash($data), true) : wp_insert_post(wp_slash($data), true);
            if (is_wp_error($written) || !$written) throw new \RuntimeException('Native synthetic draft save failed.');
            $mutated_id = (int) $written;
            if (!wp_revisions_enabled(get_post($mutated_id)) || is_wp_error(wp_save_post_revision($mutated_id))) {
                throw new \RuntimeException('Native revisions required.');
            }
        }
        wp_cache_flush();
        $after = target($page);
        $held_create = $action === 'restore' && $restore['before'] === null;
        $expected_content = $held_create ? array_intersect_key($before['post'], array_flip(['post_title','post_content','post_excerpt'])) : $content;
        if ($after === null || encode(array_intersect_key($after['post'], array_flip(array_keys($expected_content)))) !== encode($expected_content) ||
            ($held_create && (latest($after) !== latest($before) || get_post_meta($id, '_bsre_native_writer_hold', true) !== 'RESTORED_CREATE_REQUIRES_RECONCILIATION'))) {
            throw new \RuntimeException('Native save readback differs from requested content.');
        }
        if (!$held_create) {
            $revision = $after['revisions'] ? $after['revisions'][count($after['revisions']) - 1] : null;
            $changed = $before === null || content_hash($before) !== content_hash($after);
            if (!$revision || (int) $revision['post_parent'] !== $mutated_id ||
                content_hash(['post' => $revision]) !== content_hash($after) ||
                ($changed && (latest($after) === latest($before) || count($after['revisions']) <= count($before['revisions'] ?? [])))) {
                throw new \RuntimeException('Exact native revision readback required.');
            }
        }
        if ($wpdb->update(table(), ['state' => 'APPLIED', 'after_json' => encode($after), 'after_sha256' => digest($after),
            'cms_page_id' => $after === null ? null : (int) $after['post']['ID']], ['operation_key' => $key, 'state' => 'PREPARED']) !== 1) {
            throw new \RuntimeException('Durable result could not be recorded.');
        }
        sql('COMMIT'); $transaction = false;
        return receipt(journal($key));
    } catch (\Throwable $error) {
        if ($transaction) $wpdb->query('ROLLBACK');
        if ($mutated_id) clean_post_cache($mutated_id);
        wp_cache_flush();
        throw $error;
    } finally {
        if ($locked) $wpdb->get_var("SELECT RELEASE_LOCK('bsre_native_draft_lab')");
        $wpdb->close();
        $wpdb = $previous_db;
    }
}
