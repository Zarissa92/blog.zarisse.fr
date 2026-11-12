#!/usr/bin/env bash
# Active les commentaires sur blog.zarisse.fr : ajoute « ssi on; » et l'include des
# commentaires dans le bloc HTTPS « server { }  » de blog.zarisse.fr.
#
# À lancer SUR LE LENOVO, depuis le dossier synchronisé (outils/contact/) :
#   sudo bash activer_ssi_blog.sh
#
# Ce que fait le script :
#   1. repère les blocs « server { }  » qui contiennent le domaine ET une écoute TLS
#      (listen 443 / ssl_certificate). Il en faut exactement un : les blocs port 80
#      (redirection ou 404 de Certbot) sont ignorés. Sinon, rien n'est modifié ;
#   2. sauvegarde le fichier dans ~/sauvegardes_deploiement/ ;
#   3. ajoute les deux lignes juste après la ligne « server_name » de ce bloc (sauf si elles y sont déjà) ;
#   4. copie le snippet commentaires.conf s'il manque ;
#   5. teste nginx -t : si le test échoue, le fichier d'origine est restauré et rien n'est rechargé ;
#   6. recharge nginx.
# Relancer le script ne fait rien de plus si tout est déjà en place.

set -euo pipefail

# --- Réglages système : seuls endroits à modifier ---
SITE_BLOG="/etc/nginx/sites-available/default"
DOSSIER_SNIPPETS="/etc/nginx/snippets"
DOMAINE="blog.zarisse.fr"
# -----------------------------------------------------

DOSSIER_SCRIPT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HORODATAGE="$(date +%Y-%m-%d_%H%M%S)"

fin() { echo "ERREUR : $*" >&2; exit 1; }
info() { echo "--> $*"; }

[[ ${EUID} -eq 0 ]] || fin "lancer avec sudo : sudo bash activer_ssi_blog.sh"
UTILISATEUR="${SUDO_USER:-}"
[[ -n "${UTILISATEUR}" && "${UTILISATEUR}" != "root" ]] || fin "SUDO_USER absent : lancer avec sudo depuis le compte utilisateur"
HOME_UTIL="$(getent passwd "${UTILISATEUR}" | cut -d: -f6)"
DOSSIER_SAUVEGARDE="${HOME_UTIL}/sauvegardes_deploiement/${HORODATAGE}"

[[ -f "${SITE_BLOG}" ]] || fin "fichier introuvable : ${SITE_BLOG}"
[[ -f "${DOSSIER_SCRIPT}/nginx-commentaires.conf" ]] || fin "nginx-commentaires.conf introuvable dans ${DOSSIER_SCRIPT}"

LIGNE_SSI="ssi on;"
LIGNE_INCLUDE="include snippets/commentaires.conf;"

# nginx lit sites-enabled/, pas sites-available/ : le lien doit pointer vers SITE_BLOG.
SITE_ACTIF="/etc/nginx/sites-enabled/$(basename "${SITE_BLOG}")"
if [[ "$(readlink -f "${SITE_ACTIF}" 2>/dev/null || true)" == "$(readlink -f "${SITE_BLOG}")" ]]; then
    info "${SITE_ACTIF} pointe déjà vers ${SITE_BLOG}"
else
    if [[ -f "${SITE_ACTIF}" && ! -L "${SITE_ACTIF}" ]] && ! cmp -s "${SITE_ACTIF}" "${SITE_BLOG}"; then
        fin "${SITE_ACTIF} est une copie différente de ${SITE_BLOG}. Rien n'a été modifié : comparer les deux fichiers (diff) avant de continuer."
    fi
    install -d -m 700 -o "${UTILISATEUR}" -g "${UTILISATEUR}" "${DOSSIER_SAUVEGARDE}"
    if [[ -e "${SITE_ACTIF}" || -L "${SITE_ACTIF}" ]]; then
        cp -a "${SITE_ACTIF}" "${DOSSIER_SAUVEGARDE}/"
        info "sauvegarde du lien actif : ${DOSSIER_SAUVEGARDE}/$(basename "${SITE_ACTIF}")"
    fi
    rm -f "${SITE_ACTIF}"
    ln -s "${SITE_BLOG}" "${SITE_ACTIF}"
    info "lien créé : ${SITE_ACTIF} -> ${SITE_BLOG}"
fi

# Déjà en place ?
ssi_present=0; include_present=0
grep -qF "${LIGNE_SSI}" "${SITE_BLOG}" && ssi_present=1
grep -qF "${LIGNE_INCLUDE}" "${SITE_BLOG}" && include_present=1

# 4. Snippet
install -d -m 755 "${DOSSIER_SNIPPETS}"
if [[ -f "${DOSSIER_SNIPPETS}/commentaires.conf" ]] && cmp -s "${DOSSIER_SCRIPT}/nginx-commentaires.conf" "${DOSSIER_SNIPPETS}/commentaires.conf"; then
    info "snippet commentaires.conf déjà à jour"
else
    install -m 644 "${DOSSIER_SCRIPT}/nginx-commentaires.conf" "${DOSSIER_SNIPPETS}/commentaires.conf"
    info "snippet copié : ${DOSSIER_SNIPPETS}/commentaires.conf"
fi

if [[ ${ssi_present} -eq 1 && ${include_present} -eq 1 ]]; then
    info "ssi on et l'include sont déjà dans ${SITE_BLOG}, rien à modifier"
    nginx -t
    systemctl reload nginx
    echo "    nginx rechargé"
    exit 0
fi

# 1 et 3. Choix du bloc HTTPS du domaine, insertion après sa ligne server_name.
# Le résultat part dans un fichier temporaire ; en cas d'erreur, awk s'arrête sans rien écrire.
install -d -m 700 -o "${UTILISATEUR}" -g "${UTILISATEUR}" "${DOSSIER_SAUVEGARDE}"
tmp="${DOSSIER_SAUVEGARDE}/$(basename "${SITE_BLOG}").modifie"
if ! awk -v dom="${DOMAINE}" -v ssi="${ssi_present}" -v inc="${include_present}" \
        -v ligne_ssi="${LIGNE_SSI}" -v ligne_inc="${LIGNE_INCLUDE}" '
{ lignes[NR] = $0 }
END {
    prof = 0; debut = 0; nb = 0
    for (i = 1; i <= NR; i++) {
        if (prof == 0 && lignes[i] ~ /^[ \t]*server[ \t]*\{/) debut = i
        t = lignes[i]; o = gsub(/\{/, "{", t)
        t = lignes[i]; c = gsub(/\}/, "}", t)
        prof += o - c
        if (prof == 0 && debut > 0) { nb++; bd[nb] = debut; bf[nb] = i; debut = 0 }
    }
    nbc = 0; cible = 0
    for (b = 1; b <= nb; b++) {
        domaine_ok = 0; tls = 0; sn = 0
        for (i = bd[b]; i <= bf[b]; i++) {
            if (lignes[i] ~ /server_name/ && index(lignes[i], dom) > 0) { domaine_ok = 1; if (sn == 0) sn = i }
            if (lignes[i] ~ /listen[^;]*443/ || lignes[i] ~ /ssl_certificate/) tls = 1
        }
        if (domaine_ok && tls) { nbc++; cible = sn }
    }
    if (nbc != 1) {
        print "ERREUR : " nbc " bloc(s) HTTPS pour " dom " (il en faut exactement 1)" > "/dev/stderr"
        exit 3
    }
    for (i = 1; i <= NR; i++) {
        print lignes[i]
        if (i == cible) {
            if (ssi == 0) print "    " ligne_ssi
            if (inc == 0) print "    " ligne_inc
        }
    }
}' "${SITE_BLOG}" > "${tmp}"; then
    fin "aucune modification : le bloc HTTPS de ${DOMAINE} n'a pas pu être identifié de façon unique. Rien n'a été modifié."
fi

# Sauvegarde de l'original, puis remplacement et test. En cas d'échec, restauration.
cp -a "${SITE_BLOG}" "${DOSSIER_SAUVEGARDE}/"
info "sauvegarde : ${DOSSIER_SAUVEGARDE}/$(basename "${SITE_BLOG}")"

cat "${tmp}" > "${SITE_BLOG}"
if ! nginx -t; then
    cat "${DOSSIER_SAUVEGARDE}/$(basename "${SITE_BLOG}")" > "${SITE_BLOG}"
    fin "la configuration modifiée est invalide : fichier d'origine restauré, rien n'a été rechargé. Voir le message nginx ci-dessus."
fi

systemctl reload nginx
info "ssi on et include ajoutés dans le bloc HTTPS de ${DOMAINE}, nginx rechargé"
echo "Différence avec la sauvegarde :"
diff -u "${DOSSIER_SAUVEGARDE}/$(basename "${SITE_BLOG}")" "${SITE_BLOG}" || true
echo
echo "Vérifier : curl -s 'https://${DOMAINE}/commentaire?article=divers%2Fcv%2F' doit renvoyer la section « Commentaires »."
