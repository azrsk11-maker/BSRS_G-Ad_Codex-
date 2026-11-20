#!/bin/sh
set -eu
# Must pass BEFORE DB initialization and the first WordPress bootstrap.
php -d sendmail_path=/bin/false /opt/lab/isolation.php
php -d sendmail_path=/bin/false /opt/lab/browser-prerequisites.php
node /opt/lab/staging-lab/physical-identity.mjs
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
node /opt/lab/database-profile.mjs
mariadb --no-defaults --user=root --socket=/tmp/bsre.sock -e 'CREATE DATABASE bsre_synthetic;'
php -d sendmail_path=/bin/false /opt/lab/native.php
php -d sendmail_path=/bin/false /opt/lab/g2/g2-shared-repository-native.php --disabled
php -d sendmail_path=/bin/false /opt/lab/g2/g2-shared-repository-native.php --namespace-collision
php -d sendmail_path=/bin/false /opt/lab/g2/g2-shared-repository-native.php
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
php -d sendmail_path=/bin/false /opt/lab/retention-admission/retention-admission-native.php --composed-delivery
php -d sendmail_path=/bin/false /opt/lab/retention-admission/retention-admission-native.php --g1-retention
php -d sendmail_path=/bin/false /opt/lab/g1-retention/concurrency.php
php -d sendmail_path=/bin/false /opt/lab/closed-enquiry-retention/test_workflow.php
php -d sendmail_path=/bin/false /opt/lab/closed-enquiry-retention/test_no_mail_copy.php
php -d sendmail_path=/bin/false /opt/lab/closed-enquiry-retention/native-test.php
php -d sendmail_path=/bin/false /opt/lab/closed-enquiry-retention/intake-custody-native.php
php -d sendmail_path=/bin/false /opt/lab/owner-mail-review/native-test.php
php -d sendmail_path=/bin/false /opt/lab/owner-mail-review/retirement-native.php
php -d sendmail_path=/bin/false /opt/lab/owner-mail-review/collection-native.php
php -d sendmail_path=/bin/false /opt/lab/closed-enquiry-retention/capture-native.php
php -d sendmail_path=/bin/false /opt/lab/closed-enquiry-retention/admission-capture-native.php
php -d sendmail_path=/bin/false /opt/lab/closed-enquiry-retention/combined-native.php

# Additive G3-G5 fixtures run after all original lanes; never mutate their setup.
php -d sendmail_path=/bin/false /opt/lab/g3/native.php inactive
php -d sendmail_path=/bin/false /opt/lab/g3/native.php missing-store
php -d sendmail_path=/bin/false /opt/lab/g3/native.php disabled
php -d sendmail_path=/bin/false /opt/lab/g3/native.php malformed
php -d sendmail_path=/bin/false /opt/lab/g3/native.php enforced
php -d sendmail_path=/bin/false /opt/lab/g34/native.php
php -d sendmail_path=/bin/false /opt/lab/g5/tests/native.php

# G35 first-global bootstrap and common G2/G3/G5 custody; synthetic fixture only.
php -d sendmail_path=/bin/false /opt/lab/g35/bootstrap-native.php disabled
php -d sendmail_path=/bin/false /opt/lab/g35/bootstrap-native.php enabled
php -d sendmail_path=/bin/false /opt/lab/g35/bootstrap-native.php malformed-flag
php -d sendmail_path=/bin/false /opt/lab/g35/bootstrap-native.php existing-global
php -d sendmail_path=/bin/false /opt/lab/g35/bootstrap-native.php namespace-collision
php -d sendmail_path=/bin/false /opt/lab/g35/bootstrap-native.php manifest-tampered
php -d sendmail_path=/bin/false /opt/lab/g35/bootstrap-native.php source-tampered
php -d sendmail_path=/bin/false /opt/lab/g35/bootstrap-native.php producer-tampered
php -d sendmail_path=/bin/false /opt/lab/g35/route-native.php routes
php -d sendmail_path=/bin/false /opt/lab/g35/route-native.php loss

# Explicit G36 coupled synthetic candidate, after every accepted original/G3/G4/G5/G35 lane.
php -d sendmail_path=/bin/false /opt/lab/g36/bootstrap-native.php disabled
php -d sendmail_path=/bin/false /opt/lab/g36/bootstrap-native.php enabled
php -d sendmail_path=/bin/false /opt/lab/g36/bootstrap-native.php malformed-flag
php -d sendmail_path=/bin/false /opt/lab/g36/bootstrap-native.php existing-global
php -d sendmail_path=/bin/false /opt/lab/g36/bootstrap-native.php namespace-collision
php -d sendmail_path=/bin/false /opt/lab/g36/bootstrap-native.php manifest-tampered
php -d sendmail_path=/bin/false /opt/lab/g36/bootstrap-native.php source-tampered
php -d sendmail_path=/bin/false /opt/lab/g36/bootstrap-native.php producer-tampered
php -d sendmail_path=/bin/false /opt/lab/g36/route-native.php routes
php -d sendmail_path=/bin/false /opt/lab/g36/route-native.php loss
php -d sendmail_path=/bin/false /opt/lab/g36/contact-native.php hub
php -d sendmail_path=/bin/false /opt/lab/g36/contact-native.php off-plan
php -d sendmail_path=/bin/false /opt/lab/g36/contact-native.php resale
php -d sendmail_path=/bin/false /opt/lab/g36/contact-native.php rent
php -d sendmail_path=/bin/false /opt/lab/g36/contact-native.php sell
php -d sendmail_path=/bin/false /opt/lab/g36/contact-native.php let


# Append after every retained G36 contact command in the existing entrypoint.
# Both isolated database profiles use that same unchanged prefix of commands.
php -d sendmail_path=/bin/false /opt/lab/g5-receiver-runtime/tests/receiver-runtime-native.php


# Explicit fixed G37 preference runtime, after all accepted G36 lanes.
php -d sendmail_path=/bin/false /opt/lab/g37-pref/native.php disabled
php -d sendmail_path=/bin/false /opt/lab/g37-pref/native.php missing_provider
php -d sendmail_path=/bin/false /opt/lab/g37-pref/native.php nonce
php -d sendmail_path=/bin/false /opt/lab/g37-pref/native.php signature
php -d sendmail_path=/bin/false /opt/lab/g37-pref/native.php coverage
php -d sendmail_path=/bin/false /opt/lab/g37-pref/native.php reference_coverage
php -d sendmail_path=/bin/false /opt/lab/g37-pref/native.php closed_due
php -d sendmail_path=/bin/false /opt/lab/g37-pref/native.php closed_early
php -d sendmail_path=/bin/false /opt/lab/g37-pref/native.php retire
php -d sendmail_path=/bin/false /opt/lab/g37-pref/native.php known_after
php -d sendmail_path=/bin/false /opt/lab/g37-pref/native.php unknown_after
php -d sendmail_path=/bin/false /opt/lab/g37-pref/native.php new_choice
php -d sendmail_path=/bin/false /opt/lab/g37-pref/native.php restore_later
php -d sendmail_path=/bin/false /opt/lab/g37-pref/native.php cas_ack
php -d sendmail_path=/bin/false /opt/lab/g37-pref/native.php rollback
php -d sendmail_path=/bin/false /opt/lab/g37-pref/native.php trigger
php -d sendmail_path=/bin/false /opt/lab/g37-pref/native.php foreign_key
php -d sendmail_path=/bin/false /opt/lab/g37-pref/native.php snapshot_expiry
php -d sendmail_path=/bin/false /opt/lab/g37-pref/native.php compact
php -d sendmail_path=/bin/false /opt/lab/g37-pref/native.php floor_restore
php -d sendmail_path=/bin/false /opt/lab/g37-pref/native.php upgrade_scope
php -d sendmail_path=/bin/false /opt/lab/g37-pref/native.php large_unrelated
php -d sendmail_path=/bin/false /opt/lab/g37-pref/native.php partition_conflict
php -d sendmail_path=/bin/false /opt/lab/g37-pref/native.php orphan_history
php -d sendmail_path=/bin/false /opt/lab/g37-pref/native.php expired_approval
php -d sendmail_path=/bin/false /opt/lab/g37-pref/native.php revoked_cleanup
php -d sendmail_path=/bin/false /opt/lab/g37-pref/native.php expired_backup_reference
php -d sendmail_path=/bin/false /opt/lab/g37-pref/native.php external_deadlines

# Additional bounded G2 versus actual preference retirement races.
php -d sendmail_path=/bin/false /opt/lab/g38/g2-retirement-races.php choose_commit
php -d sendmail_path=/bin/false /opt/lab/g38/g2-retirement-races.php choose_rollback
php -d sendmail_path=/bin/false /opt/lab/g38/g2-retirement-races.php stage_commit
php -d sendmail_path=/bin/false /opt/lab/g38/g2-retirement-races.php stage_rollback

# Append after every retained receiver/G36/G37/G38 command in BOTH existing profiles.
# The two commands use distinct fixed namespaces/progress paths in the SAME isolated DB.
# Retained G37 large_unrelated (1100 foreign captures) is a required predecessor.
php -d sendmail_path=/bin/false /opt/lab/g5-actual-purge-runtime/tests/purge-held-native.php
php -d sendmail_path=/bin/false /opt/lab/g5-actual-purge-runtime/tests/purge-positive-native.php

# Local-only observation after every retained predecessor; no provider/export authority.
php -d sendmail_path=/bin/false /opt/lab/g39-history-local/tests/local-history-native.php
