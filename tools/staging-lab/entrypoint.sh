#!/bin/sh
set -eu
# Must pass BEFORE DB initialization and the first WordPress bootstrap.
php -d sendmail_path=/bin/false /opt/lab/isolation.php
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
php -d sendmail_path=/bin/false /opt/lab/plugin.php
php -d sendmail_path=/bin/false /opt/lab/transport.php
