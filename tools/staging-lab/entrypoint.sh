#!/bin/sh
set -eu
# Must pass BEFORE DB initialization and the first WordPress bootstrap.
php -d sendmail_path=/bin/false /opt/lab/isolation.php
php -d sendmail_path=/bin/false /opt/lab/browser-prerequisites.php
node --test /opt/lab/closed-enquiry-retention/receiver-fence/candidate.test.mjs
mkdir /tmp/database
mariadb-install-db --no-defaults --datadir=/tmp/database --auth-root-authentication-method=normal > /tmp/db-init.log 2>&1
mariadbd --no-defaults --datadir=/tmp/database --socket=/tmp/bsre.sock --pid-file=/tmp/bsre.pid --skip-networking --log-error=/tmp/db.log &
db_pid=$!
trap 'kill "$db_pid" 2>/dev/null || true' EXIT INT TERM
i=0
until mariadb-admin --no-defaults --user=root --socket=/tmp/bsre.sock ping --silent >/dev/null 2>&1; do
    i=$((i + 1)); [ "$i" -lt 40 ] || { echo 'Synthetic database startup failed' >&2; exit 1; }; sleep 1
done
mariadb --no-defaults --user=root --socket=/tmp/bsre.sock -e 'CREATE DATABASE bsre_synthetic;'
php -d sendmail_path=/bin/false /opt/lab/native.php
php -d sendmail_path=/bin/false /opt/reviewed/native-draft-writer-test.php
php -d sendmail_path=/bin/false /opt/lab/property-decision-tools/native-wordpress-test.php
php -d sendmail_path=/bin/false /opt/lab/plugin.php
node /opt/lab/consent-http.mjs
php -d sendmail_path=/bin/false /opt/lab/transport.php
php -d sendmail_path=/bin/false /opt/lab/receive.php
php -d sendmail_path=/bin/false /opt/lab/interop.php
php -d sendmail_path=/bin/false /opt/lab/client-interop.php
php -d sendmail_path=/bin/false /opt/lab/receipt-recovery/receipt-status.test.php
php -d sendmail_path=/bin/false /opt/lab/client-interop.php --upstream
php -d sendmail_path=/bin/false /opt/lab/retention.php
php -d sendmail_path=/bin/false /opt/lab/restore.php
php -d sendmail_path=/bin/false /opt/lab/consent-retention/compaction-native.php
php -d sendmail_path=/bin/false /opt/lab/consent-retention/per-choice/selective-native.php
php -d sendmail_path=/bin/false /opt/lab/consent-retention/per-choice/purpose-selective-native.php
php -d sendmail_path=/bin/false /opt/lab/consented-client-interop.php
php -d sendmail_path=/bin/false /opt/lab/purpose-client-interop.php
BSRE_PURPOSE_FIXTURE=/opt/wordpress/wp-content/plugins/bsre-enquiries BSRE_RETENTION_SOURCE=/opt/lab/consent-retention php -d sendmail_path=/bin/false /opt/lab/purpose/purpose-attribution.test.php
php -d sendmail_path=/bin/false /opt/lab/purpose-retention/restore.php
php -d sendmail_path=/bin/false /opt/lab/retention-admission/retention-admission.test.php
php -d sendmail_path=/bin/false /opt/lab/retention-admission/retention-admission-native.php
php -d sendmail_path=/bin/false /opt/lab/closed-enquiry-retention/test_workflow.php
php -d sendmail_path=/bin/false /opt/lab/closed-enquiry-retention/test_no_mail_copy.php
php -d sendmail_path=/bin/false /opt/lab/closed-enquiry-retention/native-test.php
php -d sendmail_path=/bin/false /opt/lab/closed-enquiry-retention/intake-custody-native.php
php -d sendmail_path=/bin/false /opt/lab/owner-mail-review/native-test.php
php -d sendmail_path=/bin/false /opt/lab/owner-mail-review/retirement-native.php
php -d sendmail_path=/bin/false /opt/lab/owner-mail-review/collection-native.php
php -d sendmail_path=/bin/false /opt/lab/closed-enquiry-retention/capture-native.php
php -d sendmail_path=/bin/false /opt/lab/closed-enquiry-retention/admission-capture-native.php
