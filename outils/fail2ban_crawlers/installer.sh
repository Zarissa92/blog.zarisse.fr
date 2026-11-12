#!/bin/bash
# SPDX-License-Identifier: GPL-3.0-or-later
#
# installer.sh — installe les jails anti-robots zarisse-scans et zarisse-cadence.
#
# À lancer EN ROOT, SUR LE SERVEUR Debian 13, depuis ce dossier :
#   sudo ./installer.sh --tester     # n'installe rien : mesure sur les journaux réels
#   sudo ./installer.sh              # installe, recharge fail2ban, vérifie
#   sudo ./installer.sh --desinstaller
#
# Prérequis : fail2ban, nginx, et l'action nginx-geo-ban déjà installée par f2b.sh
# (c'est elle qui sert la page 403 « Tu es banni »).
#
# Idempotent : relançable sans risque. Sauvegarde avant écriture, restauration
# automatique si fail2ban refuse la nouvelle configuration.

# Ce script a besoin de bash (tableaux, BASH_SOURCE). Lancé par erreur avec
# « sh installer.sh », dash s'arrête sur la première syntaxe bash : on se relance
# donc sous bash. Ce test-ci est volontairement en syntaxe POSIX.
if [ -z "${BASH_VERSION:-}" ]; then
    exec bash "$0" "$@"
fi

set -Eeuo pipefail

SOURCE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FILTRES=(zarisse-scans zarisse-cadence)
JAIL_SRC="$SOURCE/jail.d/zarisse-crawlers.local"
JAIL_DST="/etc/fail2ban/jail.d/zarisse-crawlers.local"
ACTION="/etc/fail2ban/action.d/nginx-geo-ban.conf"
JOURNAL="/var/log/nginx/access.log"
MODE="${1:-installer}"

msg()    { printf '==> %s\n' "$1"; }
erreur() { printf 'Erreur : %s\n' "$1" >&2; exit 1; }

[[ $EUID -eq 0 ]] || erreur "lance ce script en root (sudo ./installer.sh)."
command -v fail2ban-client >/dev/null || erreur "fail2ban n'est pas installé."
command -v fail2ban-regex  >/dev/null || erreur "fail2ban-regex est absent (paquet fail2ban incomplet)."

# ---------------------------------------------------------------- désinstallation
if [[ $MODE == --desinstaller ]]; then
    rm -f "$JAIL_DST"
    for f in "${FILTRES[@]}"; do rm -f "/etc/fail2ban/filter.d/$f.conf"; done
    msg "Jails retirées. Les IP déjà bannies restent dans /etc/nginx/banned_ips.conf :"
    msg "  pour tout débannir : sudo truncate -s 0 /etc/nginx/banned_ips.conf && sudo systemctl reload nginx"
    fail2ban-client reload
    msg "fail2ban rechargé."
    exit 0
fi

# ---------------------------------------------------------------------- mesure
mesurer() {
    local filtre nom
    [[ -r $JOURNAL ]] || erreur "journal introuvable : $JOURNAL"
    for nom in "${FILTRES[@]}"; do
        filtre="$SOURCE/filter.d/$nom.conf"
        echo
        msg "Mesure de $nom sur $JOURNAL (et ses archives) :"
        # zcat -f lit aussi les .gz ; on passe par un fichier temporaire car
        # fail2ban-regex veut un chemin, pas un flux.
        local tmp
        tmp=$(mktemp)
        # shellcheck disable=SC2086
        zcat -f ${JOURNAL}* > "$tmp" 2>/dev/null || true
        fail2ban-regex "$tmp" "$filtre" --print-no-missed 2>/dev/null \
            | grep -E "Lines:|matched|Ignored|^\s+\[[0-9]+\]" | head -20 || true
        echo "    IP distinctes qui correspondent :"
        fail2ban-regex "$tmp" "$filtre" --out=ip 2>/dev/null | sort -u | head -15 | sed 's/^/      /' || true
        fail2ban-regex "$tmp" "$filtre" --out=ip 2>/dev/null | sort -u | wc -l | sed 's/^/      total : /'
        rm -f "$tmp"
        # Une correspondance ne veut pas dire un ban : tout depend de maxretry.
        case "$nom" in
            zarisse-scans)
                echo "    Lecture : maxretry = 1, donc chacune de ces IP serait bannie."
                echo "              Un total eleve est normal (ce sont les scanners)."
                ;;
            zarisse-cadence)
                echo "    Lecture : ce filtre compte TOUTE requete de page. Chaque visiteuse"
                echo "              apparait donc ici. Le ban n'arrive qu'a 30 pages en 60 s :"
                echo "              ce total est le nombre de visiteuses distinctes, pas de bans."
                ;;
        esac
    done
}

if [[ $MODE == --tester ]]; then
    mesurer
    echo
    msg "Rien n'a été installé. Relis la liste ci-dessus : si une IP qui t'appartient"
    msg "y figure, ajuste maxretry dans jail.d/zarisse-crawlers.local avant d'installer."
    exit 0
fi

[[ $MODE == installer ]] || erreur "option inconnue : $MODE (attendu : --tester, --desinstaller, ou rien)."
[[ -f $ACTION ]] || erreur "l'action nginx-geo-ban est absente ($ACTION). Lance d'abord f2b.sh."

# -------------------------------------------------------------------- sauvegarde
STAMP=$(date +%Y%m%d-%H%M%S)
SAUVEGARDE="/root/crawlers-backup-$STAMP"
mkdir -p "$SAUVEGARDE"
GERES=("$JAIL_DST")
for f in "${FILTRES[@]}"; do GERES+=("/etc/fail2ban/filter.d/$f.conf"); done
for f in "${GERES[@]}"; do
    [[ -f $f ]] && cp -a "$f" "$SAUVEGARDE/$(basename "$f")"
done
msg "Sauvegarde : $SAUVEGARDE"

restaurer() {
    trap - ERR
    echo "Restauration de la configuration précédente..." >&2
    local f b
    for f in "${GERES[@]}"; do
        b="$SAUVEGARDE/$(basename "$f")"
        if [[ -f $b ]]; then cp -a "$b" "$f"; else rm -f "$f"; fi
    done
    fail2ban-client reload || systemctl restart fail2ban || true
}
trap 'echo "Erreur ligne $LINENO." >&2; restaurer; exit 1' ERR

# ------------------------------------------------------------------ installation
for f in "${FILTRES[@]}"; do
    install -m 644 -o root -g root "$SOURCE/filter.d/$f.conf" "/etc/fail2ban/filter.d/$f.conf"
    msg "Filtre installé : /etc/fail2ban/filter.d/$f.conf"
done
install -m 644 -o root -g root "$JAIL_SRC" "$JAIL_DST"
msg "Jail installée : $JAIL_DST"

# Vérification de syntaxe de chaque filtre avant de recharger fail2ban.
for f in "${FILTRES[@]}"; do
    fail2ban-regex "$JOURNAL" "/etc/fail2ban/filter.d/$f.conf" >/dev/null \
        || erreur "le filtre $f est invalide."
done
msg "Filtres valides."

fail2ban-client reload
sleep 2
for j in zarisse-scans zarisse-cadence; do
    fail2ban-client status "$j" >/dev/null 2>&1 || erreur "la jail $j n'est pas active après rechargement."
    msg "Jail active : $j"
done

echo
msg "Terminé. Surveillance :"
echo "    sudo fail2ban-client status zarisse-scans"
echo "    sudo fail2ban-client status zarisse-cadence"
echo "    sudo tail -f /var/log/fail2ban.log"
echo "    grep -c . /etc/nginx/banned_ips.conf      # nombre d'IP bannies"
echo
msg "Débannir une IP :"
echo "    sudo fail2ban-client set zarisse-cadence unbanip <ip>"
