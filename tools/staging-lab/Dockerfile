FROM php:8.2-cli-bookworm@sha256:ce09ca1d4b532edf9b0347b44a1968a80d9175addb581c450ba0c9a43fa0c5ea
ARG BSRE_DB_PROFILE=debian-bookworm
COPY tools/staging-lab/install-db-profile.mjs tools/staging-lab/database-11.8.9.lock.json /opt/lab-build/
# Official dependencies only; no WordPress or custom PHP executes at build time.
RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates nodejs openssl \
    && node /opt/lab-build/install-db-profile.mjs "$BSRE_DB_PROFILE" \
    && docker-php-ext-install mysqli sockets \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /opt
RUN curl --fail --location --proto '=https' --tlsv1.2 https://wordpress.org/wordpress-7.1.4.tar.gz -o wordpress.tar.gz \
    && echo '881e53a4681ff2cd911651b11cccdede5ae477ddf0765af5d6a1a8b219a1d835  wordpress.tar.gz' | sha256sum -c - \
    && tar -xzf wordpress.tar.gz && rm wordpress.tar.gz
COPY tools/staging-lab/wp-config.php /opt/wordpress/wp-config.php
COPY tools/staging-lab/database-profile.mjs /opt/lab/
COPY tools/native-wordpress/native-draft-preview.php tools/native-wordpress/native-page-manifest.json tools/native-wordpress/paid-entry-search.php /opt/reviewed/
COPY tools/native-wordpress/entry-drafts /opt/reviewed/entry-drafts
COPY tools/native-wordpress/native-draft-writer.php /opt/reviewed/native-draft-writer.php
COPY tools/native-wordpress/tests/native-draft-writer-test.php /opt/reviewed/native-draft-writer-test.php
COPY tools/property-decision-tools /opt/lab/property-decision-tools
COPY tools/property-decision-tools /opt/wordpress/wp-content/plugins/bsre-property-decision-tools
COPY tools/staging-lab/fixtures/bsre-enquiries /opt/wordpress/wp-content/plugins/bsre-enquiries
COPY tools/staging-lab/build-rental-copy-candidate.mjs /opt/lab/
RUN node /opt/lab/build-rental-copy-candidate.mjs /opt/wordpress/wp-content/plugins/bsre-enquiries/templates/source/rent.html
COPY tools/staging-lab/isolation.php tools/staging-lab/native.php tools/staging-lab/plugin.php tools/staging-lab/transport.php tools/staging-lab/receive.php tools/staging-lab/interop.php tools/staging-lab/retention.php tools/staging-lab/restore.php tools/staging-lab/backup-bridge.mjs tools/staging-lab/receiver-lab.mjs tools/staging-lab/receiver-bridge.mjs tools/staging-lab/entrypoint.sh /opt/lab/
COPY tools/staging-lab/fixtures/receiver-v2 /opt/lab/fixtures/receiver-v2
# Preserve repository-relative imports for the actual-source no-mail receiver tests.
COPY tools/staging-lab/receiver-lab.mjs /opt/lab/staging-lab/receiver-lab.mjs
COPY tools/staging-lab/fixtures/receiver-v2 /opt/lab/staging-lab/fixtures/receiver-v2
COPY tools/staging-lab/fixtures/bsre-enquiries /opt/lab/staging-lab/fixtures/bsre-enquiries
COPY tools/staging-lab/composed-delivery-interop.php tools/staging-lab/composed-delivery-interop.mjs /opt/lab/
COPY tools/website-tracking/tracking-system/composed-delivery-fixture.mjs tools/website-tracking/tracking-system/build-contact-compatible-client-candidate.mjs tools/website-tracking/tracking-system/build-frame-delivery-candidate.mjs /opt/lab/website-tracking/tracking-system/
COPY tools/website-tracking/tracking-system/build-retention-admission-candidate.mjs \
    tools/website-tracking/tracking-system/build-purpose-attribution-candidate.mjs \
    tools/website-tracking/tracking-system/build-attribution-client-candidate.mjs \
    tools/website-tracking/tracking-system/build-receipt-client-candidate.mjs \
    tools/website-tracking/tracking-system/build-reload-guard-candidate.mjs \
    tools/website-tracking/tracking-system/build-receipt-status-candidate.mjs \
    tools/website-tracking/tracking-system/contract.mjs /opt/lab/website-tracking/tracking-system/
COPY tools/consent-retention /opt/lab/consent-retention
COPY tools/recovery-package /opt/lab/recovery-package
COPY tools/website-tracking/tracking-system/receipt-recovery.php tools/website-tracking/tracking-system/receipt-recovery-wordpress.php tools/website-tracking/tracking-system/receipt-status.php tools/website-tracking/tracking-system/receipt-status.test.php /opt/lab/receipt-recovery/
COPY tools/website-tracking/tracking-system/build-receipt-status-candidate.mjs /opt/lab/tracking-system/
COPY tools/website-tracking/tracking-system/build-reload-guard-candidate.mjs tools/website-tracking/tracking-system/build-receipt-client-candidate.mjs /opt/lab/tracking-system/
COPY tools/website-tracking/tracking-system/build-attribution-client-candidate.mjs /opt/lab/tracking-system/
COPY tools/staging-lab/client-interop.php tools/staging-lab/client-interop.mjs /opt/lab/
COPY tools/staging-lab/client-page.mjs tools/staging-lab/consented-client-interop.php tools/staging-lab/consented-client-interop.mjs /opt/lab/
COPY tools/staging-lab/browser-prerequisites.php /opt/lab/
COPY tools/staging-lab/consent-http-router.php tools/staging-lab/consent-http.mjs /opt/lab/
COPY tools/website-tracking/tracking-system/build-purpose-attribution-candidate.mjs tools/website-tracking/tracking-system/contract.mjs /opt/lab/tracking-system/
COPY tools/website-tracking/tracking-system/purpose-attribution.php tools/website-tracking/tracking-system/purpose-attribution.test.php tools/website-tracking/tracking-system/purpose-retention.php /opt/lab/purpose/
COPY tools/website-tracking/tracking-system/build-purpose-retention-candidate.mjs /opt/lab/tracking-system/
COPY tools/website-tracking/tracking-system/purpose-retention.php /opt/lab/purpose-retention/
COPY tools/staging-lab/purpose-client-interop.php tools/staging-lab/purpose-client-interop.mjs /opt/lab/
COPY tools/staging-lab/purpose-concurrency.php /opt/lab/
COPY tools/website-tracking/tracking-system/build-retention-admission-candidate.mjs tools/website-tracking/tracking-system/retention-admission-bridge.mjs tools/website-tracking/tracking-system/retention-admission-client.mjs /opt/lab/tracking-system/
COPY tools/website-tracking/tracking-system/retention-admission.php tools/website-tracking/tracking-system/retention-admission.test.php tools/website-tracking/tracking-system/retention-admission-native.php /opt/lab/retention-admission/
COPY tools/closed-enquiry-retention /opt/lab/closed-enquiry-retention
COPY tools/owner-mail-review /opt/lab/owner-mail-review
COPY tools/website-tracking/tracking-system/build-g1-retention-store-candidate.mjs /opt/lab/website-tracking/tracking-system/
COPY tools/staging-lab/build-g1-retention-lab-store.mjs /opt/lab/staging-lab/
COPY tools/staging-lab/g1-retention-native.php /opt/lab/g1-retention/native.php
COPY tools/staging-lab/g1-retention-concurrency.php /opt/lab/g1-retention/concurrency.php
# Fixed G2 candidate-only plugin tree; ordinary/default/G1 paths retained.
COPY tools/website-tracking/tracking-system/build-g2-shared-repository-candidate.mjs tools/website-tracking/tracking-system/build-g2-profile-candidate.mjs /opt/lab/website-tracking/tracking-system/
COPY tools/website-tracking/tracking-system/g2-shared-repository.php tools/website-tracking/tracking-system/g2-shared-bootstrap.php /opt/lab/website-tracking/tracking-system/
COPY tools/website-tracking/tracking-system/purpose-attribution.php tools/website-tracking/tracking-system/retention-admission.php tools/website-tracking/tracking-system/receipt-recovery.php tools/website-tracking/tracking-system/receipt-status.php tools/website-tracking/tracking-system/receipt-recovery-wordpress.php /opt/lab/website-tracking/tracking-system/
COPY tools/staging-lab/build-g2-profile-lab.mjs /opt/lab/staging-lab/
COPY tools/staging-lab/g2-shared-repository-native.php /opt/lab/g2/g2-shared-repository-native.php
COPY tools/staging-lab/g2-namespace-collision-fixture.php /opt/lab/g2/g2-namespace-collision-fixture.php
COPY docs/audit/INSTALLED_SOURCE_COMPARISON_2026-11-07.json /opt/lab/g2/original-member-audit.json
# Separate fixed G3 route/context candidate; no production activation.
COPY tools/website-tracking/tracking-system/build-g3-profile-candidate.mjs tools/website-tracking/tracking-system/g3-bootstrap.php tools/website-tracking/tracking-system/g3-route-context.php /opt/lab/website-tracking/tracking-system/
COPY tools/staging-lab/build-g3-profile-lab.mjs /opt/lab/staging-lab/
COPY tools/staging-lab/g3-route-context-native.php /opt/lab/g3/native.php
# Explicit G4 V2 joined tree and independent durable G5 ports, all held.
COPY tools/website-tracking/tracking-system/build-g34-profile-candidate.mjs tools/website-tracking/tracking-system/build-native-page-context-candidate.mjs tools/website-tracking/tracking-system/build-native-frame-candidate.mjs /opt/lab/website-tracking/tracking-system/
COPY tools/website-tracking/tracking-system/native-page-context /opt/lab/website-tracking/tracking-system/native-page-context
COPY tools/staging-lab/build-g34-profile-lab.mjs tools/staging-lab/build-g5-runtime-lab.mjs /opt/lab/staging-lab/
COPY tools/staging-lab/native-page-context-native.php /opt/lab/g34/native.php
COPY tools/website-tracking/g5-runtime-ports /opt/lab/website-tracking/g5-runtime-ports
# Explicit first-canonical-connection candidate, separate from all accepted trees.
COPY tools/website-tracking/canonical-lease /opt/lab/website-tracking/canonical-lease
COPY tools/staging-lab/g3-route-context-native.php /opt/lab/staging-lab/g3-route-context-native.php
COPY tools/staging-lab/build-canonical-lease-lab.mjs /opt/lab/staging-lab/
COPY tools/staging-lab/canonical-lease-bootstrap-native.php /opt/lab/g35/bootstrap-native.php
COPY tools/staging-lab/canonical-purpose-native.php /opt/lab/g35/purpose-native.php
# Byte-only candidate derivation; no WordPress/custom PHP execution during build.
RUN node /opt/lab/consent-retention/build-candidate.mjs /opt/wordpress/wp-content/plugins/bsre-enquiries/includes/consent-store.php /opt/lab/consent-retention/candidate-store.php
RUN node /opt/lab/tracking-system/build-purpose-attribution-candidate.mjs store /opt/wordpress/wp-content/plugins/bsre-enquiries/includes/consent-store.php /opt/lab/purpose/store.php \
    && node /opt/lab/tracking-system/build-purpose-attribution-candidate.mjs intake /opt/wordpress/wp-content/plugins/bsre-enquiries/bsre-enquiries.php /opt/wordpress/wp-content/plugins/bsre-enquiries/includes/consent.php /opt/lab/purpose/intake.php
RUN node /opt/lab/tracking-system/build-purpose-retention-candidate.mjs /opt/lab/consent-retention /opt/lab/restore.php /opt/lab/purpose-retention
RUN node /opt/lab/tracking-system/build-retention-admission-candidate.mjs store /opt/wordpress/wp-content/plugins/bsre-enquiries/includes/consent-store.php /opt/lab/retention-admission/store.php \
    && node /opt/lab/tracking-system/build-retention-admission-candidate.mjs intake /opt/wordpress/wp-content/plugins/bsre-enquiries/bsre-enquiries.php /opt/wordpress/wp-content/plugins/bsre-enquiries/includes/consent.php /opt/lab/retention-admission/intake.php
RUN node /opt/lab/staging-lab/build-g1-retention-lab-store.mjs
RUN node /opt/lab/staging-lab/build-g2-profile-lab.mjs
RUN node /opt/lab/staging-lab/build-g3-profile-lab.mjs
RUN node /opt/lab/staging-lab/build-g34-profile-lab.mjs
RUN node /opt/lab/staging-lab/build-g5-runtime-lab.mjs
RUN node /opt/lab/staging-lab/build-canonical-lease-lab.mjs
# Public source-shaped input cache only; fixed separate target. Never copy a private held packet.
COPY docs/audit/INSTALLED_SOURCE_COMPARISON_2026-11-07.json /opt/lab/g36-source/docs/audit/
COPY tools/closed-enquiry-retention/ClosureCollection.php tools/closed-enquiry-retention/ClosureCollectionJournal.php tools/closed-enquiry-retention/LeaseBoundWpdb.php tools/closed-enquiry-retention/NoMailCopy.php tools/closed-enquiry-retention/RetirementIntent.php tools/closed-enquiry-retention/RetirementJournal.php tools/closed-enquiry-retention/Workflow.php tools/closed-enquiry-retention/WpCaptureResource.php /opt/lab/g36-source/tools/closed-enquiry-retention/
COPY tools/closed-enquiry-retention/receiver-fence/build-candidate.mjs tools/closed-enquiry-retention/receiver-fence/runtime.gs /opt/lab/g36-source/tools/closed-enquiry-retention/receiver-fence/
COPY tools/consent-retention/PreferenceRetirement.php tools/consent-retention/RetentionInventory.php tools/consent-retention/RetirementLedger.php /opt/lab/g36-source/tools/consent-retention/
COPY tools/owner-mail-review/Cleanup.php tools/owner-mail-review/OwnerClosure.php tools/owner-mail-review/OwnerCollection.php tools/owner-mail-review/OwnerMailReview.php tools/owner-mail-review/OwnerRetirement.php tools/owner-mail-review/WordPress.php /opt/lab/g36-source/tools/owner-mail-review/
COPY tools/staging-lab/build-rental-copy-candidate.mjs tools/staging-lab/canonical-lease-bootstrap-native.php tools/staging-lab/canonical-purpose-native.php tools/staging-lab/g3-route-context-native.php /opt/lab/g36-source/tools/staging-lab/
COPY tools/staging-lab/fixtures/bsre-enquiries/assets/assets.css tools/staging-lab/fixtures/bsre-enquiries/assets/consent-bridge.js tools/staging-lab/fixtures/bsre-enquiries/assets/consent.css tools/staging-lab/fixtures/bsre-enquiries/assets/google-measurement.js tools/staging-lab/fixtures/bsre-enquiries/assets/google-runtime.js tools/staging-lab/fixtures/bsre-enquiries/assets/hub.css tools/staging-lab/fixtures/bsre-enquiries/assets/lead.js tools/staging-lab/fixtures/bsre-enquiries/assets/wordpress.js /opt/lab/g36-source/tools/staging-lab/fixtures/bsre-enquiries/assets/
COPY tools/staging-lab/fixtures/bsre-enquiries/bsre-enquiries.php /opt/lab/g36-source/tools/staging-lab/fixtures/bsre-enquiries/
COPY tools/staging-lab/fixtures/bsre-enquiries/includes/admin.php tools/staging-lab/fixtures/bsre-enquiries/includes/cli.php tools/staging-lab/fixtures/bsre-enquiries/includes/consent-export.php tools/staging-lab/fixtures/bsre-enquiries/includes/consent-store.php tools/staging-lab/fixtures/bsre-enquiries/includes/consent.php tools/staging-lab/fixtures/bsre-enquiries/includes/drafts.php tools/staging-lab/fixtures/bsre-enquiries/includes/enquiry-seo.php tools/staging-lab/fixtures/bsre-enquiries/includes/measurement-runtime.php tools/staging-lab/fixtures/bsre-enquiries/includes/measurement-settings.php tools/staging-lab/fixtures/bsre-enquiries/includes/measurement.php tools/staging-lab/fixtures/bsre-enquiries/includes/parent-isolation.php tools/staging-lab/fixtures/bsre-enquiries/includes/presentation.php tools/staging-lab/fixtures/bsre-enquiries/includes/protocol.php /opt/lab/g36-source/tools/staging-lab/fixtures/bsre-enquiries/includes/
COPY tools/staging-lab/fixtures/bsre-enquiries/templates/hub.php tools/staging-lab/fixtures/bsre-enquiries/templates/page.php /opt/lab/g36-source/tools/staging-lab/fixtures/bsre-enquiries/templates/
COPY tools/staging-lab/fixtures/bsre-enquiries/templates/source/hub.html tools/staging-lab/fixtures/bsre-enquiries/templates/source/let.html tools/staging-lab/fixtures/bsre-enquiries/templates/source/off-plan.html tools/staging-lab/fixtures/bsre-enquiries/templates/source/rent.html tools/staging-lab/fixtures/bsre-enquiries/templates/source/resale.html tools/staging-lab/fixtures/bsre-enquiries/templates/source/sell.html /opt/lab/g36-source/tools/staging-lab/fixtures/bsre-enquiries/templates/source/
COPY tools/staging-lab/fixtures/receiver-v2/Code.gs /opt/lab/g36-source/tools/staging-lab/fixtures/receiver-v2/
COPY tools/website-tracking/canonical-lease/build-candidate.mjs tools/website-tracking/canonical-lease/build-canonical-capture-producer.mjs tools/website-tracking/canonical-lease/build-route-native.mjs tools/website-tracking/canonical-lease/CanonicalCaptureProducer.template.php tools/website-tracking/canonical-lease/db.php tools/website-tracking/canonical-lease/route-custody-postlude.php /opt/lab/g36-source/tools/website-tracking/canonical-lease/
COPY tools/website-tracking/coupled-package-v3/compose-v3.mjs tools/website-tracking/coupled-package-v3/profile-contract-v3.json tools/website-tracking/coupled-package-v3/source-pins-v3.json tools/website-tracking/coupled-package-v3/synthetic-input.mjs /opt/lab/g36-source/tools/website-tracking/coupled-package-v3/
COPY tools/website-tracking/coupled-package/baseline-pins.json tools/website-tracking/coupled-package/capture-guard-policy-v2.mjs tools/website-tracking/coupled-package/compose-v2.mjs tools/website-tracking/coupled-package/compose.mjs tools/website-tracking/coupled-package/g3-source-pins-v2.json tools/website-tracking/coupled-package/g4-source-pins-v2.json tools/website-tracking/coupled-package/profile-contract-v2.json tools/website-tracking/coupled-package/profile-contract.json /opt/lab/g36-source/tools/website-tracking/coupled-package/
COPY tools/website-tracking/g5-runtime-ports/build-candidate.mjs /opt/lab/g36-source/tools/website-tracking/g5-runtime-ports/
COPY tools/website-tracking/g5-runtime-ports/candidate/plugin/includes/candidate/closed-enquiry-retention/ActualCaptureResource.php tools/website-tracking/g5-runtime-ports/candidate/plugin/includes/candidate/closed-enquiry-retention/ActualJournal.php tools/website-tracking/g5-runtime-ports/candidate/plugin/includes/candidate/closed-enquiry-retention/CaptureRules.php /opt/lab/g36-source/tools/website-tracking/g5-runtime-ports/candidate/plugin/includes/candidate/closed-enquiry-retention/
COPY tools/website-tracking/g5-runtime-ports/candidate/plugin/includes/candidate/recovery/ActualRecoveryCustody.php /opt/lab/g36-source/tools/website-tracking/g5-runtime-ports/candidate/plugin/includes/candidate/recovery/
COPY tools/website-tracking/g5-runtime-ports/candidate/plugin/includes/candidate/runtime/G5Contracts.php /opt/lab/g36-source/tools/website-tracking/g5-runtime-ports/candidate/plugin/includes/candidate/runtime/
COPY tools/website-tracking/g5-runtime-ports/tests/native.php /opt/lab/g36-source/tools/website-tracking/g5-runtime-ports/tests/
COPY tools/website-tracking/tracking-system/build-attribution-client-candidate.mjs tools/website-tracking/tracking-system/build-contact-compatible-client-candidate.mjs tools/website-tracking/tracking-system/build-frame-delivery-candidate.mjs tools/website-tracking/tracking-system/build-g1-retention-store-candidate.mjs tools/website-tracking/tracking-system/build-g2-profile-candidate.mjs tools/website-tracking/tracking-system/build-g2-shared-repository-candidate.mjs tools/website-tracking/tracking-system/build-g3-profile-candidate.mjs tools/website-tracking/tracking-system/build-g34-profile-candidate.mjs tools/website-tracking/tracking-system/build-native-frame-candidate.mjs tools/website-tracking/tracking-system/build-native-page-context-candidate.mjs tools/website-tracking/tracking-system/build-purpose-attribution-candidate.mjs tools/website-tracking/tracking-system/build-purpose-retention-candidate.mjs tools/website-tracking/tracking-system/build-receipt-client-candidate.mjs tools/website-tracking/tracking-system/build-receipt-status-candidate.mjs tools/website-tracking/tracking-system/build-reload-guard-candidate.mjs tools/website-tracking/tracking-system/build-retention-admission-candidate.mjs tools/website-tracking/tracking-system/g2-shared-bootstrap.php tools/website-tracking/tracking-system/g2-shared-repository.php tools/website-tracking/tracking-system/g3-bootstrap.php tools/website-tracking/tracking-system/g3-route-context.php tools/website-tracking/tracking-system/purpose-attribution.php tools/website-tracking/tracking-system/purpose-retention.php tools/website-tracking/tracking-system/receipt-recovery-wordpress.php tools/website-tracking/tracking-system/receipt-recovery.php tools/website-tracking/tracking-system/receipt-status.php tools/website-tracking/tracking-system/retention-admission.php /opt/lab/g36-source/tools/website-tracking/tracking-system/
COPY tools/website-tracking/tracking-system/native-page-context/client.js tools/website-tracking/tracking-system/native-page-context/NativePageContext.php /opt/lab/g36-source/tools/website-tracking/tracking-system/native-page-context/
COPY tools/website-tracking/coupled-package-v3/build-native.mjs tools/website-tracking/coupled-package-v3/native-contact-abi.php /opt/lab/website-tracking/coupled-package-v3/
COPY tools/staging-lab/build-coupled-canonical-v3-lab.mjs tools/staging-lab/canonical-coupled-contact-native.php /opt/lab/staging-lab/
# Place this RUN after existing byte builds and before USER mysql.
RUN node /opt/lab/staging-lab/build-coupled-canonical-v3-lab.mjs
# Insert after the retained G36 byte build and before USER mysql. Public code only.
COPY tools/website-tracking/g5-receiver-runtime/build-native-lab.mjs tools/website-tracking/g5-receiver-runtime/build-candidate.mjs /opt/lab/website-tracking/g5-receiver-runtime/
COPY tools/website-tracking/g5-receiver-runtime/runtime/control.gs tools/website-tracking/g5-receiver-runtime/runtime/no-copy.gs /opt/lab/website-tracking/g5-receiver-runtime/runtime/
COPY tools/website-tracking/g5-receiver-runtime/candidate/plugin/includes/candidate/receiver/ReceiverContracts.php tools/website-tracking/g5-receiver-runtime/candidate/plugin/includes/candidate/receiver/NoMailCopyAlgebra.php tools/website-tracking/g5-receiver-runtime/candidate/plugin/includes/candidate/receiver/ActualRetirementPort.php tools/website-tracking/g5-receiver-runtime/candidate/plugin/includes/candidate/receiver/ReceiverOperationalEvidence.php tools/website-tracking/g5-receiver-runtime/candidate/plugin/includes/candidate/receiver/ActualReceiverWorkflow.php /opt/lab/website-tracking/g5-receiver-runtime/candidate/plugin/includes/candidate/receiver/
COPY tools/website-tracking/g5-receiver-runtime/candidate/plugin/includes/candidate/closed-enquiry-retention/ActualReceiverJournal.php /opt/lab/website-tracking/g5-receiver-runtime/candidate/plugin/includes/candidate/closed-enquiry-retention/
COPY tools/website-tracking/g5-receiver-runtime/tests/control-fixture.mjs tools/website-tracking/g5-receiver-runtime/tests/native-bridge.mjs tools/website-tracking/g5-receiver-runtime/tests/receiver-runtime-native.php /opt/lab/website-tracking/g5-receiver-runtime/tests/
COPY tools/staging-lab/build-receiver-runtime-lab.mjs /opt/lab/staging-lab/
# These two curated additions supply the recorded /opt/lab/g36-source bridge root.
# Keep each exactly once if already added by the integration correction.
COPY tools/closed-enquiry-retention/receiver-fence/lab.mjs /opt/lab/g36-source/tools/closed-enquiry-retention/receiver-fence/
COPY tools/staging-lab/receiver-lab.mjs /opt/lab/g36-source/tools/staging-lab/
RUN node /opt/lab/staging-lab/build-receiver-runtime-lab.mjs

# Explicit fixed G37 preference input cache; retain the accepted G36 site/helper.
COPY tools/website-tracking/g5-preference-runtime/build-native-addon.mjs tools/website-tracking/g5-preference-runtime/build-runtime.mjs /opt/lab/website-tracking/g5-preference-runtime/
COPY tools/website-tracking/g5-preference-runtime/candidate/plugin/includes/candidate/retention/ActualPreferenceRetention.php tools/website-tracking/g5-preference-runtime/candidate/plugin/includes/candidate/retention/PreferenceAlgebra.php tools/website-tracking/g5-preference-runtime/candidate/plugin/includes/candidate/retention/PreferenceAtomicStore.php tools/website-tracking/g5-preference-runtime/candidate/plugin/includes/candidate/retention/PreferenceContracts.php tools/website-tracking/g5-preference-runtime/candidate/plugin/includes/candidate/retention/PreferenceCustody.php /opt/lab/website-tracking/g5-preference-runtime/candidate/plugin/includes/candidate/retention/
COPY tools/website-tracking/g5-preference-runtime/native/FixturePorts.php tools/website-tracking/g5-preference-runtime/native/native.php /opt/lab/website-tracking/g5-preference-runtime/native/
COPY tools/staging-lab/build-preference-runtime-lab.mjs /opt/lab/staging-lab/
# Run after build-coupled-canonical-v3-lab.mjs and before USER mysql.
RUN node /opt/lab/staging-lab/build-preference-runtime-lab.mjs

# Fixed synthetic G38 races; preserve all G36/G37 closed manifests.
COPY tools/staging-lab/g38/native/g2-retirement-races.php /opt/lab/g38/g2-retirement-races.php

USER mysql
ENTRYPOINT ["sh", "/opt/lab/entrypoint.sh"]
