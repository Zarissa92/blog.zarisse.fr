#!/usr/bin/env bash
# Build le site puis publie la preview sur le serveur.
# Usage : ./deploy-preview.sh <nom-preview> [utilisateur@serveur] [options rsync]
# Exemple : ./deploy-preview.sh ma-branche melissandre@zarisse.fr --dry-run
# Même principe que blog_push (outils/publication/blog_push.fish) : build.py, puis rsync --checksum
# avec suppression des fichiers absents en local. Ce script est dans outils/previews/, d'où ../..
set -euo pipefail

NAME="${1:?Usage: $0 <nom-preview> [utilisateur@serveur] [options rsync]}"
SERVER="${2:-utilisateur@serveur}"
PROJECT_DIR="$(cd "$(dirname "$0")/../.." && pwd)"

# Le nom doit correspondre à [a-z0-9-]+ (ex : feat/menu -> feat-menu)
if [[ ! "$NAME" =~ ^[a-z0-9-]+$ ]]; then
    echo "Nom invalide : utilise uniquement a-z, 0-9 et '-'." >&2
    exit 1
fi

cd "$PROJECT_DIR"
# Jamais « zensical build » seul : il saute les étapes post-build (voir README.md).
"$PROJECT_DIR/venv_blog/bin/python" build.py

# --checksum : compare le contenu, pas la date (build.py réécrit tout site/).
# --exclude / --delete-excluded : pas de fichiers cachés, et on retire ceux qui ne sont plus en local.
rsync -avz --checksum --delete --delete-excluded --exclude='.*' --human-readable "${@:3}" \
    site/ "${SERVER}:/var/www/previews/${NAME}/"

echo "Preview publiée : https://${NAME}.preview.zarisse.fr"
