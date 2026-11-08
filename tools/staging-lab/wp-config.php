<?php
// Disposable synthetic fixture only. No production credentials or services.
define('DB_NAME', 'bsre_synthetic');
define('DB_USER', 'root');
define('DB_PASSWORD', '');
define('DB_HOST', 'localhost:/tmp/bsre.sock');
define('DB_CHARSET', 'utf8mb4');
define('DB_COLLATE', '');
$table_prefix = 'synthetic_';
define('WP_HOME', 'http://bsre.invalid');
define('WP_SITEURL', 'http://bsre.invalid');
define('WP_DEBUG', false);
define('DISABLE_WP_CRON', true);
define('AUTOMATIC_UPDATER_DISABLED', true);
define('WP_AUTO_UPDATE_CORE', false);
define('WP_HTTP_BLOCK_EXTERNAL', true);
define('DISALLOW_FILE_MODS', true);
define('WP_TEMP_DIR', '/tmp');
define('BSRE_NATIVE_PLANNER_PREVIEW_ENABLED', true);
define('AUTH_KEY', 'synthetic-not-for-production');
define('SECURE_AUTH_KEY', 'synthetic-not-for-production-2');
define('LOGGED_IN_KEY', 'synthetic-not-for-production-3');
define('NONCE_KEY', 'synthetic-not-for-production-4');
define('ABSPATH', __DIR__ . '/');
require_once ABSPATH . 'wp-settings.php';
