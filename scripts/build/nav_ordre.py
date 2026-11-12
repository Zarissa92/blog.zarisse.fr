#!/usr/bin/env python3
"""Ordre de la navigation (barre latérale) : le plus récent en haut (lancé à chaque build par build.py).

Zensical trie la navigation automatique par nom de fichier. Le plugin `mkdocs-nav-weight`
(zensical.toml) la trie d'après le champ `weight` du front matter, du plus petit au plus grand.
Ce script écrit donc, pour chaque page .md de docs/ :

    weight: -202611111800      # -(AAAAMMJJHHMM) de la date de tri, heure française

La date de tri est celle de billets_index.py (date.created, sinon la date notée, sinon la date
du fichier), pour que la barre latérale suive le même ordre que les listes de billets.
Plus la page est récente, plus son poids est petit, donc plus elle est haute dans la barre latérale.
Les index.md (pages de section) ne reçoivent pas de poids : leur poids vient du plugin.

Le champ est écrit sur place : seule la ligne `weight:` change (ou est ajoutée en fin de front
matter), le reste du fichier est intact. La date de modification du fichier est remise à sa
valeur d'avant, comme dans dater_pages.py : ajouter un poids ne compte pas comme une modification.

Sans option : simulation, rien n'est écrit.
Avec --appliquer : écrit les pages.

Usage :
  venv_blog/bin/python nav_ordre.py               # simulation
  venv_blog/bin/python nav_ordre.py --appliquer   # écriture
"""
import datetime
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))  # modules du même dossier
import billets_index  # noqa: E402  (lire_billet : date de tri, la même que pour les listes)
DOCS = ROOT / "docs"
IGNORES = {"assets"}  # dossiers de premier niveau de docs/ jamais parcourus
RE_FM = re.compile(r"^---\n(.*?\n)?---\n", re.S)
RE_WEIGHT = re.compile(r"^weight\s*:.*$", re.M)


def poids(cree) -> int:
    """Poids d'une date de création : plus elle est récente, plus il est petit (négatif)."""
    if isinstance(cree, datetime.datetime):
        return -int(cree.strftime("%Y%m%d%H%M"))
    return -int(datetime.datetime(cree.year, cree.month, cree.day).strftime("%Y%m%d%H%M"))


def nouveau_texte(p: Path, texte: str):
    """Texte avec le champ `weight` à jour, ou None s'il n'y a rien à changer.

    La date vient de billets_index.lire_billet : la même que celle qui trie les listes de billets
    (date.created, sinon la date notée, sinon la date du fichier). La barre latérale et les listes
    restent ainsi dans le même ordre.
    """
    cree, _titre = billets_index.lire_billet(p)
    m = RE_FM.match(texte)
    if not m:
        return None
    ligne = f"weight: {poids(cree)}"
    fm = m.group(1) or ""
    if RE_WEIGHT.search(fm):
        nouveau_fm = RE_WEIGHT.sub(ligne, fm, count=1)
    else:
        nouveau_fm = fm + ligne + "\n"
    if nouveau_fm == fm:
        return None
    return "---\n" + nouveau_fm + "---\n" + texte[m.end():]


def pages():
    for p in sorted(DOCS.rglob("*.md")):
        parties = p.relative_to(DOCS).parts
        if parties[0] in IGNORES or any(part.startswith(".") for part in parties):
            continue
        if p.name == "index.md":
            continue
        yield p


def main(appliquer=None, silencieux=False) -> int:
    """appliquer=None : lu sur la ligne de commande (--appliquer). silencieux=True : utilisé par build.py."""
    if appliquer is None:
        appliquer = "--appliquer" in sys.argv
    modifications = []
    for p in pages():
        texte = p.read_text(encoding="utf-8")
        nouveau = nouveau_texte(p, texte)
        if nouveau is None:
            continue
        modifications.append((p, nouveau))
        if not silencieux:
            print(f"  + {p.relative_to(ROOT)}")

    if silencieux and not modifications:
        return 0
    print(f"\n{len(modifications)} page(s) à ordonner dans la navigation.")
    if not appliquer:
        print("Simulation : rien n'a été écrit. Relance avec --appliquer pour écrire.")
        return 0
    for p, texte in modifications:
        stat = p.stat()
        p.write_text(texte, encoding="utf-8")
        os.utime(p, ns=(stat.st_atime_ns, stat.st_mtime_ns))  # date de modification d'avant
    return 0


if __name__ == "__main__":
    sys.exit(main())
