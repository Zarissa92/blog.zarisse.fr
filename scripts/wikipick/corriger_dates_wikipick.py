#!/usr/bin/env python3
"""Correctif wikipick : initialise les dates à aujourd'hui.

Pour chaque page de collection wikipick (docs/**/*.md, hors index.md) :
  - la ligne « mise à jour le … » est réglée sur la date du jour ;
  - chaque carte est notée comme ajoutée aujourd'hui dans wiki_historique.json.
Le journal « Dernières modifications » (index.md) n'est pas touché.

Sans option : simulation, rien n'est écrit.
Avec --appliquer : écrit les pages et wiki_historique.json.

Usage :
  venv_blog/bin/python corriger_dates_wikipick.py               # simulation
  venv_blog/bin/python corriger_dates_wikipick.py --appliquer   # écriture
"""
import hashlib
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))  # modules du même dossier
import wikipick_site as wp  # noqa: E402

SUIVI = ROOT / "donnees" / "wikipick" / "wiki_historique.json"
RE_DATE_LIGNE = re.compile(r"( · mise à jour le )\d{2}/\d{2}/\d{4}")
RE_LIGNE_SANS_DATE = re.compile(r"(retour à la collection\]\(index\.md\))")


def pages_wikipick():
    for p in sorted((ROOT / "docs").rglob("*.md")):
        if p.name == "index.md":
            continue
        texte = p.read_text(encoding="utf-8")
        if wp.DEBUT_REPERE in texte and wp.FIN_BLOC in texte:
            yield p


def main():
    appliquer = "--appliquer" in sys.argv
    aujourdhui = time.strftime("%Y-%m-%d")
    fr = wp.date_fr(aujourdhui)
    suivi = wp.charger_suivi(SUIVI)
    nouveau = {"collections": {}, "journal": suivi["journal"]}
    reecritures = []
    total = 0

    for p in pages_wikipick():
        cle_page = p.resolve().relative_to((ROOT / "docs").resolve()).as_posix()
        cartes = {}
        for _, entrees in wp.lire_cartes_existantes(p):
            for e in entrees:
                cartes[e["cle"]] = {"ajoutee": aujourdhui,
                                    "h": hashlib.md5(e["carte"].encode("utf-8")).hexdigest()}
        nouveau["collections"][cle_page] = {"maj": aujourdhui, "cartes": cartes}
        total += len(cartes)

        texte = p.read_text(encoding="utf-8")
        if RE_DATE_LIGNE.search(texte):
            maj = RE_DATE_LIGNE.sub(lambda m: m.group(1) + fr, texte)
        else:
            maj = RE_LIGNE_SANS_DATE.sub(lambda m: m.group(1) + " · mise à jour le " + fr, texte, count=1)
        if maj != texte:
            reecritures.append((p, maj))
        print(f"{p.relative_to(ROOT)} : {len(cartes)} carte(s), mise à jour le {fr}")

    print(f"\n{len(nouveau['collections'])} collection(s), {total} carte(s) datées du {fr}.")
    print(f"{len(reecritures)} page(s) à modifier, journal conservé : {len(suivi['journal'])} événement(s).")

    if not appliquer:
        print("\nSimulation : rien n'a été écrit. Relance avec --appliquer pour écrire.")
        return 0

    for p, texte in reecritures:
        p.write_text(texte, encoding="utf-8")
    wp.sauver_suivi(SUIVI, nouveau)
    print(f"\nÉcrit : {len(reecritures)} page(s) et {SUIVI.name}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
