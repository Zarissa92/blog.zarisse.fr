#!/usr/bin/env python3
"""Met à jour la liste des billets de docs/Billets2Blog/index.md.

La liste est entre deux marqueurs HTML :
    <!-- billets:debut -->
    <!-- billets:fin -->
Chaque build remplace le contenu entre ces marqueurs (il n'y a pas d'ajout à la suite).

Ordre : d'après `date.created` du front matter de chaque billet, puis par nom de fichier.
Le billet le plus récent est en haut (modifier RECENT_D_ABORD pour inverser).
Titre : `title` du front matter, sinon le premier titre `#`, sinon le nom du fichier.

Usage : python3 billets_index.py
"""
import re
import sys
from datetime import date
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent
DOSSIER = ROOT / "docs" / "Billets2Blog"
INDEX = DOSSIER / "index.md"
RECENT_D_ABORD = True

DEBUT = "<!-- billets:debut -->"
FIN = "<!-- billets:fin -->"
RE_FM = re.compile(r"^---\n(.*?\n)?---\n", re.S)
RE_TITRE = re.compile(r"^#\s+(.+)$", re.M)


def lire_billet(chemin: Path):
    """Renvoie (date, titre) d'un billet."""
    texte = chemin.read_text(encoding="utf-8")
    meta = {}
    m = RE_FM.match(texte)
    corps = texte
    if m:
        meta = yaml.safe_load(m.group(1) or "") or {}
        corps = texte[m.end():]
    cree = (meta.get("date") or {}).get("created") if isinstance(meta.get("date"), dict) else None
    if isinstance(cree, str):
        cree = date.fromisoformat(cree[:10])
    if not isinstance(cree, date):
        cree = date.fromtimestamp(chemin.stat().st_mtime)
    titre = meta.get("title")
    if not titre:
        t = RE_TITRE.search(corps)
        titre = t.group(1).strip() if t else chemin.stem
    return cree, str(titre)


def construire_liste() -> str:
    billets = []
    for p in DOSSIER.glob("*.md"):
        if p.name == "index.md":
            continue
        cree, titre = lire_billet(p)
        billets.append((cree, p.name, titre))
    # tri chronologique, puis nom de fichier pour départager les jours identiques
    billets.sort(key=lambda b: (b[0], b[1]), reverse=RECENT_D_ABORD)
    if not billets:
        return "*Aucun billet pour le moment.*"
    lignes = []
    for cree, nom, titre in billets:
        jour = cree.strftime("%d/%m/%Y")
        lignes.append(f"- {jour} — [{titre}]({nom})")
    return "\n".join(lignes)


def main() -> int:
    texte = INDEX.read_text(encoding="utf-8")
    if DEBUT not in texte or FIN not in texte:
        print(f"Marqueurs absents dans {INDEX}", file=sys.stderr)
        return 1
    avant, reste = texte.split(DEBUT, 1)
    _, apres = reste.split(FIN, 1)
    nouveau = avant + DEBUT + "\n" + construire_liste() + "\n" + FIN + apres
    if nouveau != texte:
        INDEX.write_text(nouveau, encoding="utf-8")
        print(f"Liste des billets mise à jour ({INDEX.relative_to(ROOT)})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
