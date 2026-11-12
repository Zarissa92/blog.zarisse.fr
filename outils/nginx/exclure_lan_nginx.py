#!/usr/bin/env python3
"""Exclut le réseau local des journaux d'accès nginx, donc de GoAccess.

Ce que fait le script, sur tous les fichiers *.conf sous la racine nginx :
  1. crée conf.d/exclure-lan.conf : un bloc `geo` qui vaut 0 pour les réseaux
     locaux et 1 pour les autres (`geo` accepte les CIDR, `map` non) ;
  2. ajoute ` if=$loggable` à chaque directive `access_log` concernée
     (pas `access_log off`, pas les blocs `stream`, pas celles qui ont déjà un if=).

Sécurité :
  - simulation par défaut : rien n'est écrit sans --appliquer ;
  - sauvegarde complète de la racine avant toute écriture ;
  - `nginx -t`, puis vérification que le bloc geo est bien chargé ;
    en cas d'échec, tout est restauré et nginx n'est pas rechargé.

Usage, sur le serveur, en root :
  sudo ./exclure_lan_nginx.py                                  # simulation
  sudo ./exclure_lan_nginx.py --appliquer
  sudo ./exclure_lan_nginx.py --appliquer --lan 192.168.1.0/24 --lan 10.0.0.0/8
"""

import argparse
import datetime
import ipaddress
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

MARQUEUR = "# Généré par exclure_lan_nginx.py : ne pas modifier à la main"
NOM_GEO = "exclure-lan.conf"
VARIABLE = "$loggable"
DECLARATION_GEO = f"geo $remote_addr {VARIABLE}"
LIGNE_ACCESS_LOG = re.compile(r"^(\s*)access_log(\s[^;]*?)\s*;(.*)$")


def contenu_geo(reseaux):
    lignes = [
        MARQUEUR,
        "# Requêtes des réseaux locaux : 0 (non journalisées), les autres : 1",
        f"{DECLARATION_GEO} {{",
        "    default 1;",
    ]
    lignes += [f"    {r} 0;" for r in reseaux]
    lignes.append("}")
    return "\n".join(lignes) + "\n"


def analyser(texte):
    """Retourne (texte modifié, modifications, sauts).

    modifications : liste de (numéro, ancienne ligne, nouvelle ligne)
    sauts         : liste de (numéro, raison)
    """
    pile = []
    sortie = []
    modifs = []
    sauts = []
    for num, ligne in enumerate(texte.splitlines(keepends=True), 1):
        brut = ligne.rstrip("\r\n")
        fin = ligne[len(brut):]
        code = brut.split("#", 1)[0]

        m = LIGNE_ACCESS_LOG.match(brut)
        if not m and "access_log" in code:
            sauts.append((num, "forme non reconnue, à traiter à la main"))
        if m:
            indent, args, reste = m.group(1), m.group(2).rstrip(), m.group(3)
            if "stream" in pile:
                sauts.append((num, "bloc stream : $loggable n'y est pas défini"))
            elif args.split()[:1] == ["off"]:
                pass
            elif re.search(r"\bif=", args):
                sauts.append((num, "if= déjà présent"))
            else:
                jetons = args.split()
                # Sans format explicite, nginx lit le mot suivant le chemin comme
                # un format : on écrit donc le format par défaut (combined) avant if=.
                # Un second mot contenant "=" (buffer=, flush=) ou "gzip" n'est pas un format.
                if len(jetons) == 1 or "=" in jetons[1] or jetons[1] == "gzip":
                    args = args.replace(jetons[0], f"{jetons[0]} combined", 1)
                nouvelle = f"{indent}access_log{args} if={VARIABLE};{reste}"
                modifs.append((num, brut, nouvelle))
                brut = nouvelle

        # Suivi des blocs ouverts/fermés, pour repérer le contexte stream.
        for pos, car in enumerate(code):
            if car == "{":
                mots = re.split(r"[;{}]", code[:pos])[-1].split()
                pile.append(mots[0] if mots else "")
            elif car == "}" and pile:
                pile.pop()

        sortie.append(brut + fin)
    return "".join(sortie), modifs, sauts


def fichiers_conf(racine):
    return sorted(p for p in racine.rglob("*.conf") if p.is_file())


def lire(chemin):
    return chemin.read_bytes().decode("utf-8")


def ecrire(chemin, texte):
    chemin.write_bytes(texte.encode("utf-8"))


def commande(nginx, *args):
    return subprocess.run([nginx, *args], capture_output=True, text=True)


def main():
    parser = argparse.ArgumentParser(description="Exclut le LAN des access_log nginx.")
    parser.add_argument("--racine", default="/etc/nginx", help="dossier de configuration nginx")
    parser.add_argument("--lan", action="append",
                        help="réseau à exclure (CIDR), répétable ; défaut : 192.168.1.0/24")
    parser.add_argument("--appliquer", action="store_true",
                        help="écrire les modifications (sans ce drapeau : simulation)")
    parser.add_argument("--nginx", default="nginx", help="binaire nginx")
    parser.add_argument("--sauvegarde", default="/var/backups/exclure-lan-nginx",
                        help="dossier où placer la sauvegarde avant modification")
    args = parser.parse_args()

    reseaux = []
    for r in args.lan or ["192.168.1.0/24"]:
        try:
            reseaux.append(str(ipaddress.ip_network(r, strict=False)))
        except ValueError:
            print(f"Réseau invalide : {r}", file=sys.stderr)
            return 2

    racine = Path(args.racine)
    if not racine.is_dir():
        print(f"Dossier introuvable : {racine}", file=sys.stderr)
        return 2
    if args.appliquer and os.geteuid() != 0:
        print("--appliquer demande les droits root (sudo).", file=sys.stderr)
        return 2

    geo = racine / "conf.d" / NOM_GEO
    geo_actuel = lire(geo) if geo.exists() else None
    if geo_actuel is not None and MARQUEUR not in geo_actuel:
        print(f"{geo} existe et n'a pas été généré par ce script. Arrêt.", file=sys.stderr)
        return 2

    a_modifier = {}
    for f in fichiers_conf(racine):
        try:
            texte = lire(f)
        except UnicodeDecodeError:
            print(f"[ignoré] {f} : encodage non UTF-8")
            continue
        nouveau, modifs, sauts = analyser(texte)
        for num, avant, apres in modifs:
            print(f"{f}:{num}\n    avant : {avant.strip()}\n    après : {apres.strip()}")
        for num, raison in sauts:
            print(f"[saut] {f}:{num} : {raison}")
        if modifs:
            a_modifier[f] = (texte, nouveau)

    nouveau_geo = contenu_geo(reseaux)
    geo_change = geo_actuel != nouveau_geo
    if geo_change:
        action = "Création" if geo_actuel is None else "Mise à jour"
        print(f"\n{action} de {geo} :\n{nouveau_geo}")

    if not a_modifier and not geo_change:
        print("Rien à modifier.")
        return 0
    print(f"\n{len(a_modifier)} fichier(s) à modifier.")
    if not args.appliquer:
        print("Simulation : rien n'a été écrit. Relancez avec --appliquer.")
        return 0

    sauvegarde = Path(args.sauvegarde) / datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    shutil.copytree(racine, sauvegarde)
    print(f"Sauvegarde : {sauvegarde}")

    originaux = {}
    try:
        geo.parent.mkdir(exist_ok=True)
        for f, (texte, nouveau) in a_modifier.items():
            originaux[f] = texte
            ecrire(f, nouveau)
        if geo_change:
            if geo_actuel is not None:
                originaux[geo] = geo_actuel
            ecrire(geo, nouveau_geo)

        test = commande(args.nginx, "-t")
        if test.returncode:
            raise RuntimeError("nginx -t a échoué :\n" + test.stderr)
        dump = commande(args.nginx, "-T")
        if dump.returncode or DECLARATION_GEO not in dump.stdout:
            raise RuntimeError(
                f"le bloc '{DECLARATION_GEO}' n'est pas chargé : vérifiez que "
                "nginx.conf inclut conf.d/*.conf dans le bloc http"
            )
    except Exception as e:
        for f, texte in originaux.items():
            ecrire(f, texte)
        if geo_actuel is None and geo.exists():
            geo.unlink()
        print(f"ERREUR : {e}\nModifications annulées. Sauvegarde conservée : {sauvegarde}",
              file=sys.stderr)
        return 1

    rechargement = commande(args.nginx, "-s", "reload")
    if rechargement.returncode:
        print(f"Rechargement échoué : {rechargement.stderr}", file=sys.stderr)
        return 1

    print("Configuration appliquée et nginx rechargé.")
    print("Les nouvelles requêtes du LAN ne sont plus journalisées. Les données déjà "
          "présentes dans GoAccess restent : reconstruisez sa base si nécessaire.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
