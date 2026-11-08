FROM php:8.2-cli-bookworm@sha256:ce09ca1d4b532edf9b0347b44a1968a80d9175addb581c450ba0c9a43fa0c5ea
# Official dependencies only; no WordPress or custom PHP executes at build time.
RUN apt-get update && apt-get install -y --no-install-recommends mariadb-server curl ca-certificates \
    && docker-php-ext-install mysqli sockets \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /opt
RUN curl --fail --location --proto '=https' --tlsv1.2 https://wordpress.org/wordpress-7.1.4.tar.gz -o wordpress.tar.gz \
    && echo '881e53a4681ff2cd911651b11cccdede5ae477ddf0765af5d6a1a8b219a1d835  wordpress.tar.gz' | sha256sum -c - \
    && tar -xzf wordpress.tar.gz && rm wordpress.tar.gz
COPY tools/staging-lab/wp-config.php /opt/wordpress/wp-config.php
COPY tools/native-wordpress/native-draft-preview.php tools/native-wordpress/native-page-manifest.json /opt/reviewed/
COPY tools/staging-lab/fixtures/bsre-enquiries /opt/wordpress/wp-content/plugins/bsre-enquiries
COPY tools/staging-lab/isolation.php tools/staging-lab/native.php tools/staging-lab/plugin.php tools/staging-lab/entrypoint.sh /opt/lab/
USER mysql
ENTRYPOINT ["sh", "/opt/lab/entrypoint.sh"]
