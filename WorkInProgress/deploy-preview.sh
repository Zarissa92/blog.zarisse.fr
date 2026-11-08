#!/usr/bin/env bash
# Build le site puis publie la preview sur le serveur.
# Usage : ./deploy-preview.sh <nom-preview> [utilisateur@serveur]
# Exemple : ./deploy-preview.sh ma-branche melissandre@zarisse.fr
set -euo pipefail

NAME="${1:?Usage: $0 <nom-preview> [utilisateur@serveur]}"
SERVER="${2:-utilisateur@serveur}"
PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"

# Le nom doit correspondre à [a-z0-9-]+ (ex : feat/menu -> feat-menu)
if [[ ! "$NAME" =~ ^[a-z0-9-]+$ ]]; then
    echo "Nom invalide : utilise uniquement a-z, 0-9 et '-'." >&2
    exit 1
fi

cd "$PROJECT_DIR"
zensical build

rsync -av --delete site/ "${SERVER}:/var/www/previews/${NAME}/"

echo "Preview publiée : https://${NAME}.preview.zarisse.fr"
