#!/usr/bin/env bash
# Configure nginx pour les previews : https://<nom>.preview.zarisse.fr -> /var/www/previews/<nom>/
set -euo pipefail

DOMAIN="${DOMAIN:-preview.zarisse.fr}"
ROOT="${ROOT:-/var/www/previews}"
CONF="/etc/nginx/sites-available/previews.conf"
CERT_DIR="/etc/letsencrypt/live/${DOMAIN}"

if [[ $EUID -ne 0 ]]; then
    echo "Lance ce script avec sudo." >&2
    exit 1
fi

apt-get update
apt-get install -y nginx

mkdir -p "$ROOT"
chown -R www-data:www-data "$ROOT"

# Le domaine est échappé pour une regex nginx (les points deviennent \.)
DOMAIN_RE="${DOMAIN//./\\.}"

cat > "$CONF" <<'EOF'
# Previews — généré par setup-previews.sh
server {
    listen 80;
    listen [::]:80;
    server_name ~^(?<preview>[a-z0-9-]+)\.__DOMAIN_RE__$;

    # Redirection HTTP -> HTTPS
    location / {
        return 301 https://$host$request_uri;
    }
}
EOF

if [[ -f "${CERT_DIR}/fullchain.pem" ]]; then
    cat >> "$CONF" <<'EOF'

server {
    listen 443 ssl;
    listen [::]:443 ssl;
    http2 on;
    server_name ~^(?<preview>[a-z0-9-]+)\.__DOMAIN_RE__$;

    ssl_certificate     __CERT_DIR__/fullchain.pem;
    ssl_certificate_key __CERT_DIR__/privkey.pem;

    root /var/www/previews/$preview;
    index index.html;

    # Previews privées : pas d'indexation par les moteurs
    add_header X-Robots-Tag "noindex, nofollow" always;

    # Preview inexistante -> 404
    if (!-d /var/www/previews/$preview) {
        return 404;
    }

    location / {
        try_files $uri $uri/ $uri/index.html =404;
    }

    access_log /var/log/nginx/previews.access.log;
    error_log  /var/log/nginx/previews.error.log;
}
EOF
else
    echo "Pas encore de certificat wildcard : seul le HTTP est configuré (voir la note HTTPS dans session-nginx-previews.md)."
fi

# Remplacement des placeholders
sed -i \
    -e "s|__DOMAIN_RE__|${DOMAIN_RE}|g" \
    -e "s|__CERT_DIR__|${CERT_DIR}|g" \
    "$CONF"

ln -sf "$CONF" /etc/nginx/sites-enabled/previews.conf
rm -f /etc/nginx/sites-enabled/default

nginx -t
systemctl reload nginx

echo "OK. Previews servies depuis ${ROOT}/<nom>/"
