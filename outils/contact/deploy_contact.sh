#!/usr/bin/env bash
# Déploie ou met à jour le formulaire de kioske.fr et les commentaires de zarisse.fr.
#
# À lancer SUR LE LENOVO, depuis le dossier synchronisé (outils/contact/) :
#   sudo bash deploy_contact.sh install   première mise en service
#   sudo bash deploy_contact.sh maj       après une mise à jour de contact.py
#
# install : crée les dossiers de données, installe le service systemd, copie les snippets
#           nginx, vérifie les configurations des sites et dit ce qu'il reste à ajouter.
# maj     : redémarre le service avec le contact.py synchronisé. Ne touche ni à nginx,
#           ni aux données (messages, commentaires, clé).
#
# Le script ne modifie jamais un fichier de configuration nginx existant : il sauvegarde
# les fichiers concernés et affiche les lignes à ajouter à la main.

set -euo pipefail

# --- Réglages système : seuls endroits à modifier ---
UNITE="contact.service"
DEST_UNITE="/etc/systemd/system/${UNITE}"
DOSSIER_SNIPPETS="/etc/nginx/snippets"
SITE_KIOSKE="/etc/nginx/sites-available/kioske.fr"
SITE_BLOG="/etc/nginx/sites-available/default"   # blog.zarisse.fr est déclaré dans ce fichier
PORT_LOCAL=8765
# -----------------------------------------------------

MODE="${1:-}"
case "${MODE}" in
    install|maj) ;;
    *) echo "usage : sudo bash deploy_contact.sh install|maj" >&2; exit 1 ;;
esac

DOSSIER_SCRIPT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJET="$(cd "${DOSSIER_SCRIPT}/../.." && pwd)"
HORODATAGE="$(date +%Y-%m-%d_%H%M%S)"

fin() { echo "ERREUR : $*" >&2; exit 1; }
info() { echo "--> $*"; }

[[ ${EUID} -eq 0 ]] || fin "lancer avec sudo : sudo bash deploy_contact.sh ${MODE}"

UTILISATEUR="${SUDO_USER:-}"
[[ -n "${UTILISATEUR}" && "${UTILISATEUR}" != "root" ]] || fin "SUDO_USER absent : lancer avec sudo depuis le compte utilisateur, pas en root direct"
HOME_UTIL="$(getent passwd "${UTILISATEUR}" | cut -d: -f6)"
[[ -n "${HOME_UTIL}" && -d "${HOME_UTIL}" ]] || fin "dossier personnel introuvable pour ${UTILISATEUR}"

PYTHON="${PROJET}/venv_blog/bin/python"
DOSSIER_DONNEES="${HOME_UTIL}/contact"
DOSSIER_SAUVEGARDE="${HOME_UTIL}/sauvegardes_deploiement/${HORODATAGE}"

[[ -x "${PYTHON}" ]] || fin "venv absent : ${PYTHON} (recréer venv_blog à partir de requirements.txt)"
[[ -f "${DOSSIER_SCRIPT}/contact.py" ]] || fin "contact.py introuvable dans ${DOSSIER_SCRIPT}"
[[ -f "${DOSSIER_SCRIPT}/contact.service" ]] || fin "contact.service introuvable dans ${DOSSIER_SCRIPT}"

sauvegarder() {
    # Copie un fichier existant dans le dossier de sauvegarde, avant de le remplacer.
    local fichier="$1"
    if [[ -e "${fichier}" ]]; then
        install -d -m 700 -o "${UTILISATEUR}" -g "${UTILISATEUR}" "${DOSSIER_SAUVEGARDE}"
        cp -a "${fichier}" "${DOSSIER_SAUVEGARDE}/"
        info "sauvegarde : ${DOSSIER_SAUVEGARDE}/$(basename "${fichier}")"
    fi
}

verifier_include() {
    # Affiche si un site contient la ligne attendue. Retourne 0 si oui, 1 sinon.
    local site="$1" motif="$2"
    if [[ ! -f "${site}" ]]; then
        echo "    fichier introuvable : ${site} (corriger SITE_* en tête du script)"
        return 1
    fi
    if grep -qF "${motif}" "${site}"; then
        echo "    OK : « ${motif} » présent dans ${site}"
        return 0
    fi
    echo "    MANQUANT dans ${site} : « ${motif} »"
    return 1
}

# ---------- Données ----------

info "dossier de données : ${DOSSIER_DONNEES}"
install -d -m 700 -o "${UTILISATEUR}" -g "${UTILISATEUR}" "${DOSSIER_DONNEES}"
install -d -m 700 -o "${UTILISATEUR}" -g "${UTILISATEUR}" "${DOSSIER_DONNEES}/commentaires"

# ---------- Service systemd ----------

# Unités : le service, et l'import des commentaires toutes les 5 minutes (install comme maj,
# pour que les modifications des modèles suivent).
info "unités systemd : service et import toutes les 5 minutes"
install -d -m 700 -o "${UTILISATEUR}" -g "${UTILISATEUR}" "${DOSSIER_SAUVEGARDE}"
for modele in contact.service contact-import.service contact-import.timer; do
    cible="/etc/systemd/system/${modele}"
    sauvegarder "${cible}"
    genere="${DOSSIER_SAUVEGARDE}/${modele}.genere"
    sed -e "s|__UTILISATEUR__|${UTILISATEUR}|g" \
        -e "s|__PROJET__|${PROJET}|g" \
        -e "s|__HOME__|${HOME_UTIL}|g" \
        "${DOSSIER_SCRIPT}/${modele}" > "${genere}"
    install -m 644 -o root -g root "${genere}" "${cible}"
    echo "    installé : ${cible}"
done
systemctl daemon-reload
systemctl enable "${UNITE}"
systemctl enable --now contact-import.timer

info "redémarrage du service (à relancer après chaque mise à jour de contact.py)"
systemctl restart "${UNITE}"
sleep 1
systemctl is-active --quiet "${UNITE}" || fin "le service ne démarre pas : journalctl -u ${UNITE} -n 50"
echo "    service actif"

if curl -fs --max-time 5 "http://127.0.0.1:${PORT_LOCAL}/contact" >/dev/null; then
    echo "    OK : /contact répond sur 127.0.0.1:${PORT_LOCAL}"
else
    fin "le script ne répond pas sur 127.0.0.1:${PORT_LOCAL} : journalctl -u ${UNITE} -n 50"
fi

if [[ "${MODE}" == "maj" ]]; then
    info "mise à jour terminée (nginx et données inchangés)"
    exit 0
fi

# ---------- Installation : snippets nginx et vérifications ----------

info "snippets nginx"
install -d -m 755 "${DOSSIER_SNIPPETS}"
sauvegarder "${DOSSIER_SNIPPETS}/contact.conf"
sauvegarder "${DOSSIER_SNIPPETS}/commentaires.conf"
install -m 644 "${DOSSIER_SCRIPT}/nginx-contact.conf" "${DOSSIER_SNIPPETS}/contact.conf"
install -m 644 "${DOSSIER_SCRIPT}/nginx-commentaires.conf" "${DOSSIER_SNIPPETS}/commentaires.conf"
echo "    copiés : contact.conf, commentaires.conf"

info "vérification des sites (le script ne modifie pas ces fichiers)"
sauvegarder "${SITE_KIOSKE}"
sauvegarder "${SITE_BLOG}"
manque=0
echo "  kioske.fr :"
verifier_include "${SITE_KIOSKE}" "include snippets/contact.conf;" || manque=1
echo "  blog.zarisse.fr :"
verifier_include "${SITE_BLOG}" "ssi on;" || manque=1
verifier_include "${SITE_BLOG}" "include snippets/commentaires.conf;" || manque=1

if [[ ${manque} -eq 1 ]]; then
    cat <<EOF

Ajouter à la main, dans le bloc « server { }  » concerné, puis relancer le script :
  kioske.fr       : include snippets/contact.conf;
  blog.zarisse.fr : ssi on;
                    include snippets/commentaires.conf;
Sauvegardes déjà faites dans ${DOSSIER_SAUVEGARDE}.
Ensuite : sudo bash deploy_contact.sh install
EOF
    exit 2
fi

info "test de la configuration nginx"
nginx -t
systemctl reload nginx
echo "    nginx rechargé"

info "installation terminée. Vérifier : curl -I https://kioske.fr/contact et la page d'un article du blog."
info "Premier import des commentaires : ${PYTHON} ${DOSSIER_SCRIPT}/contact.py importer"
