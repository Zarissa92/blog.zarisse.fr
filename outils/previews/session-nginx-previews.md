# Session : nginx Debian pour les previews zarisse.fr

## Contexte
- Objectif : servir des previews du site (Zensical, build statique dans `site/`) sur le serveur Debian.
- Convention retenue (hypothèse, à confirmer) : `https://<nom>.preview.zarisse.fr` -> `/var/www/previews/<nom>/`.
- Le projet ne contient pas de config preview existante (recherche faite dans le dépôt).
- Le script est destiné au serveur Debian, pas à cette machine.

## Script d'installation : `setup-previews.sh` (à lancer en root sur le serveur)

```bash
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
    echo "Pas encore de certificat wildcard : seul le HTTP est configuré (voir la note HTTPS plus bas)."
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
```

## Déployer une preview (depuis la machine de dev)

```bash
cd ~/zarisse.fr && outils/previews/deploy-preview.sh ma-branche utilisateur@serveur --dry-run   # simulation
outils/previews/deploy-preview.sh ma-branche utilisateur@serveur
```

Le script lance `venv_blog/bin/python build.py` puis `rsync --checksum --delete --delete-excluded`, comme `blog_push`.
Ne jamais utiliser `zensical build` seul (voir README.md).

Supprimer une preview : `sudo rm -rf /var/www/previews/ma-branche`

## Étapes manuelles (une seule fois)

1. **DNS** : enregistrement `*.preview` de type A (et AAAA) vers l'IP du serveur.
2. **Certificat wildcard** (challenge DNS obligatoire) :
   ```bash
   sudo apt install certbot
   sudo certbot certonly --manual --preferred-challenges dns -d "*.preview.zarisse.fr" -d "preview.zarisse.fr"
   ```
   Pour le renouvellement auto, utiliser un plugin `certbot-dns-*` adapté à l'hébergeur DNS.
3. Relancer `setup-previews.sh` une fois le certificat présent (ajoute le bloc HTTPS).

## Points à vérifier
- Le nom de preview doit être `[a-z0-9-]+` : `feat/menu` -> `feat-menu`.
- Vérifier que `site_url` dans `zensical.toml` et les chemins absolus des assets ne pointent pas vers la prod.
- Pour des previews privées : `auth_basic` + `htpasswd` dans le bloc HTTPS.

## Questions ouvertes
- Convention définitive : sous-domaine (choix actuel) ou `zarisse.fr/preview/<nom>/` ?
