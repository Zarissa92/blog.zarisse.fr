#!/usr/bin/env python3
"""Met à jour la liste des pages dans tous les index.md de docs/ qui portent les marqueurs.

La liste est entre deux marqueurs HTML :
    <!-- billets:debut -->
    <!-- billets:fin -->
Chaque build remplace le contenu entre ces marqueurs (il n'y a pas d'ajout à la suite).

Tous les index.md de docs/ ont ces marqueurs : index_dossiers.py, lancé juste avant par
build.py, les ajoute à la fin de ceux qui ne les ont pas. Chaque index reçoit la liste des
pages de son dossier, puis celle de ses sous-dossiers (sections). Ignorés : docs/assets/
et les dossiers cachés. Le build s'arrête si docs/Billets2Blog/index.md n'a pas les marqueurs.

Ordre : d'après `date.created` du front matter de chaque billet, heure comprise
(`AAAA-MM-JJ HH:MM` ; une date sans heure compte pour 00:00), puis par nom de fichier.
Le billet le plus récent est en haut (modifier RECENT_D_ABORD pour inverser).
Titre : `title` du front matter, sinon le premier titre `#`, sinon le nom du fichier.

Usage : venv_blog/bin/python billets_index.py
"""
import re
import sys
from datetime import date, datetime
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
DOCS = ROOT / "docs"
INDEX = DOCS / "Billets2Blog" / "index.md"  # seul index où les marqueurs sont obligatoires
IGNORES = {"assets"}  # dossiers de premier niveau de docs/ jamais parcourus
RECENT_D_ABORD = True

DEBUT = "<!-- billets:debut -->"
FIN = "<!-- billets:fin -->"
RE_FM = re.compile(r"^---\n(.*?\n)?---\n", re.S)
RE_TITRE = re.compile(r"^#\s+(.+)$", re.M)


def lire_billet(chemin: Path):
    """Renvoie (date et heure de création, titre) d'un billet."""
    texte = chemin.read_text(encoding="utf-8")
    meta = {}
    m = RE_FM.match(texte)
    corps = texte
    if m:
        meta = yaml.safe_load(m.group(1) or "") or {}
        corps = texte[m.end():]
    cree = (meta.get("date") or {}).get("created") if isinstance(meta.get("date"), dict) else None
    if isinstance(cree, str):
        try:
            cree = datetime.fromisoformat(cree.strip())
        except ValueError:
            cree = None
    if isinstance(cree, datetime):
        cree = cree.replace(tzinfo=None)
    elif isinstance(cree, date):  # date sans heure : minuit
        cree = datetime(cree.year, cree.month, cree.day)
    else:
        cree = datetime.fromtimestamp(chemin.stat().st_mtime)
    titre = meta.get("title")
    if not titre:
        t = RE_TITRE.search(corps)
        titre = t.group(1).strip() if t else chemin.stem
    return cree, str(titre)


def construire_liste(dossier: Path) -> str:
    billets = []
    for p in dossier.glob("*.md"):
        if p.name == "index.md":
            continue
        cree, titre = lire_billet(p)
        billets.append((cree, p.name, titre))
    # tri chronologique (date et heure), puis nom de fichier pour départager les ex æquo
    billets.sort(key=lambda b: (b[0], b[1]), reverse=RECENT_D_ABORD)
    sections = []
    for sous in sorted(d for d in dossier.iterdir() if d.is_dir() and not d.name.startswith(".")):
        index = sous / "index.md"
        if index.exists():
            titre = lire_billet(index)[1]
            if titre == "index":  # ni title ni titre « # » : nom du dossier
                titre = sous.name.replace("_", " ")
            sections.append(f"- [{titre}]({sous.name}/index.md)")
    if not billets and not sections:
        return "*Aucun billet pour le moment.*"
    lignes = []
    for cree, nom, titre in billets:
        jour = cree.strftime("%d/%m/%Y")
        lignes.append(f"- {jour} — [{titre}]({nom})")
    if sections:
        if lignes:
            lignes.append("")
        lignes.append("**Sections :**")
        lignes.append("")
        lignes.extend(sections)
    return "\n".join(lignes)


def mettre_a_jour(index: Path) -> None:
    texte = index.read_text(encoding="utf-8")
    avant, reste = texte.split(DEBUT, 1)
    _, apres = reste.split(FIN, 1)
    nouveau = avant + DEBUT + "\n" + construire_liste(index.parent) + "\n" + FIN + apres
    if nouveau != texte:
        index.write_text(nouveau, encoding="utf-8")
        print(f"Liste des billets mise à jour ({index.relative_to(ROOT)})")


def main() -> int:
    texte = INDEX.read_text(encoding="utf-8")
    if DEBUT not in texte or FIN not in texte:
        print(f"Marqueurs absents dans {INDEX}", file=sys.stderr)
        return 1
    for index in sorted(DOCS.rglob("index.md")):
        parties = index.relative_to(DOCS).parts
        if parties[0] in IGNORES or any(part.startswith(".") for part in parties):
            continue
        sous_texte = index.read_text(encoding="utf-8")
        if DEBUT in sous_texte and FIN in sous_texte:
            mettre_a_jour(index)
    return 0


if __name__ == "__main__":
    sys.exit(main())
