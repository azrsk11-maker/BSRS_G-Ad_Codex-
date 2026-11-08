FROM php:8.2-cli-bookworm@sha256:ce09ca1d4b532edf9b0347b44a1968a80d9175addb581c450ba0c9a43fa0c5ea
# Official dependencies only; no WordPress or custom PHP executes at build time.
RUN apt-get update && apt-get install -y --no-install-recommends mariadb-server curl ca-certificates nodejs \
    && docker-php-ext-install mysqli sockets \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /opt
RUN curl --fail --location --proto '=https' --tlsv1.2 https://wordpress.org/wordpress-7.1.4.tar.gz -o wordpress.tar.gz \
    && echo '881e53a4681ff2cd911651b11cccdede5ae477ddf0765af5d6a1a8b219a1d835  wordpress.tar.gz' | sha256sum -c - \
    && tar -xzf wordpress.tar.gz && rm wordpress.tar.gz
COPY tools/staging-lab/wp-config.php /opt/wordpress/wp-config.php
COPY tools/native-wordpress/native-draft-preview.php tools/native-wordpress/native-page-manifest.json /opt/reviewed/
COPY tools/staging-lab/fixtures/bsre-enquiries /opt/wordpress/wp-content/plugins/bsre-enquiries
COPY tools/staging-lab/isolation.php tools/staging-lab/native.php tools/staging-lab/plugin.php tools/staging-lab/transport.php tools/staging-lab/receive.php tools/staging-lab/interop.php tools/staging-lab/retention.php tools/staging-lab/restore.php tools/staging-lab/backup-bridge.mjs tools/staging-lab/receiver-lab.mjs tools/staging-lab/receiver-bridge.mjs tools/staging-lab/entrypoint.sh /opt/lab/
COPY tools/staging-lab/fixtures/receiver-v2 /opt/lab/fixtures/receiver-v2
COPY tools/consent-retention /opt/lab/consent-retention
COPY tools/recovery-package /opt/lab/recovery-package
COPY tools/website-tracking/tracking-system/receipt-recovery.php tools/website-tracking/tracking-system/receipt-recovery-wordpress.php tools/website-tracking/tracking-system/receipt-status.php tools/website-tracking/tracking-system/receipt-status.test.php /opt/lab/receipt-recovery/
COPY tools/website-tracking/tracking-system/build-receipt-status-candidate.mjs /opt/lab/tracking-system/
COPY tools/website-tracking/tracking-system/build-reload-guard-candidate.mjs tools/website-tracking/tracking-system/build-receipt-client-candidate.mjs /opt/lab/tracking-system/
COPY tools/website-tracking/tracking-system/build-attribution-client-candidate.mjs /opt/lab/tracking-system/
COPY tools/staging-lab/client-interop.php tools/staging-lab/client-interop.mjs /opt/lab/
COPY tools/staging-lab/client-page.mjs tools/staging-lab/consented-client-interop.php tools/staging-lab/consented-client-interop.mjs /opt/lab/
COPY tools/staging-lab/browser-prerequisites.php /opt/lab/
COPY tools/website-tracking/tracking-system/build-purpose-attribution-candidate.mjs /opt/lab/tracking-system/
COPY tools/website-tracking/tracking-system/purpose-attribution.php tools/website-tracking/tracking-system/purpose-attribution.test.php tools/website-tracking/tracking-system/purpose-retention.php /opt/lab/purpose/
COPY tools/website-tracking/tracking-system/build-purpose-retention-candidate.mjs /opt/lab/tracking-system/
COPY tools/website-tracking/tracking-system/purpose-retention.php /opt/lab/purpose-retention/
COPY tools/staging-lab/purpose-client-interop.php tools/staging-lab/purpose-client-interop.mjs /opt/lab/
COPY tools/staging-lab/purpose-concurrency.php /opt/lab/
COPY tools/website-tracking/tracking-system/build-retention-admission-candidate.mjs tools/website-tracking/tracking-system/retention-admission-bridge.mjs tools/website-tracking/tracking-system/retention-admission-client.mjs /opt/lab/tracking-system/
COPY tools/website-tracking/tracking-system/retention-admission.php tools/website-tracking/tracking-system/retention-admission.test.php tools/website-tracking/tracking-system/retention-admission-native.php /opt/lab/retention-admission/
COPY tools/closed-enquiry-retention /opt/lab/closed-enquiry-retention
# Byte-only candidate derivation; no WordPress/custom PHP execution during build.
RUN node /opt/lab/consent-retention/build-candidate.mjs /opt/wordpress/wp-content/plugins/bsre-enquiries/includes/consent-store.php /opt/lab/consent-retention/candidate-store.php
RUN node /opt/lab/tracking-system/build-purpose-attribution-candidate.mjs store /opt/wordpress/wp-content/plugins/bsre-enquiries/includes/consent-store.php /opt/lab/purpose/store.php \
    && node /opt/lab/tracking-system/build-purpose-attribution-candidate.mjs intake /opt/wordpress/wp-content/plugins/bsre-enquiries/bsre-enquiries.php /opt/wordpress/wp-content/plugins/bsre-enquiries/includes/consent.php /opt/lab/purpose/intake.php
RUN node /opt/lab/tracking-system/build-purpose-retention-candidate.mjs /opt/lab/consent-retention /opt/lab/restore.php /opt/lab/purpose-retention
RUN node /opt/lab/tracking-system/build-retention-admission-candidate.mjs store /opt/wordpress/wp-content/plugins/bsre-enquiries/includes/consent-store.php /opt/lab/retention-admission/store.php \
    && node /opt/lab/tracking-system/build-retention-admission-candidate.mjs intake /opt/wordpress/wp-content/plugins/bsre-enquiries/bsre-enquiries.php /opt/wordpress/wp-content/plugins/bsre-enquiries/includes/consent.php /opt/lab/retention-admission/intake.php
USER mysql
ENTRYPOINT ["sh", "/opt/lab/entrypoint.sh"]
