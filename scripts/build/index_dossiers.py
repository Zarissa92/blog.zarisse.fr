#!/usr/bin/env python3
"""Crée l'index.md manquant de chaque dossier de docs/, et ajoute les marqueurs de liste aux
index.md qui ne les ont pas (lancé à chaque build par build.py).

Un dossier reçoit un index.md s'il contient au moins une page .md (directement ou dans un
sous-dossier) et n'en a pas encore. Les dossiers sans page (images, polices…) et les dossiers
cachés sont ignorés, ainsi que docs/assets/.

L'index créé contient un front matter avec le titre, tiré du nom du dossier
(« _ » remplacé par une espace), et les marqueurs de liste (billets:debut / billets:fin),
que billets_index.py remplit ensuite avec les pages du dossier. Les dates sont ajoutées
par dater_pages.py.

Un index.md existant qui n'a pas les marqueurs les reçoit à la fin du fichier, ajoutés à la
suite (le fichier n'est pas recréé, son texte n'est pas modifié). Tous les index de docs/
ont ainsi leur liste, accueil compris. Un index qui n'a qu'un seul des deux marqueurs est
signalé et laissé tel quel.

Usage :
  venv_blog/bin/python scripts/build/index_dossiers.py               # simulation
  venv_blog/bin/python scripts/build/index_dossiers.py --appliquer   # écriture
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DOCS = ROOT / "docs"
IGNORES = {"assets"}  # dossiers de premier niveau de docs/ à ne jamais indexer
DEBUT = "<!-- billets:debut -->"
FIN = "<!-- billets:fin -->"
MARQUEURS = f"{DEBUT}\n{FIN}\n"  # liste remplie par billets_index.py


def titre(dossier: Path) -> str:
    return dossier.name.replace("_", " ")


def dossiers_sans_index() -> list[Path]:
    manquants = []
    for dossier in sorted(p for p in DOCS.rglob("*") if p.is_dir()):
        relatif = dossier.relative_to(DOCS)
        if relatif.parts[0] in IGNORES or any(part.startswith(".") for part in relatif.parts):
            continue
        if (dossier / "index.md").exists():
            continue
        if not any(dossier.rglob("*.md")):
            continue
        manquants.append(dossier)
    return manquants


def index_sans_marqueurs() -> list[Path]:
    """index.md existants sans les deux marqueurs (ceux qui n'en ont qu'un sont signalés)."""
    a_completer = []
    for index in sorted(DOCS.rglob("index.md")):
        parties = index.relative_to(DOCS).parts
        if parties[0] in IGNORES or any(part.startswith(".") for part in parties):
            continue
        texte = index.read_text(encoding="utf-8")
        debut, fin = DEBUT in texte, FIN in texte
        if debut and fin:
            continue
        if debut or fin:
            print(f"  ! un seul marqueur dans {index.relative_to(ROOT)} : à corriger à la main", file=sys.stderr)
            continue
        a_completer.append(index)
    return a_completer


def ajouter_marqueurs(index: Path) -> None:
    """Ajoute les marqueurs à la fin du fichier, sur place (le fichier garde sa date de naissance)."""
    texte = index.read_text(encoding="utf-8")
    saut = "\n" if texte.endswith("\n") else "\n\n"
    with index.open("a", encoding="utf-8") as f:
        f.write(saut + MARQUEURS)


def main(appliquer: bool = False) -> int:
    for index in index_sans_marqueurs():
        if appliquer:
            ajouter_marqueurs(index)
            print(f"  ✓ marqueurs ajoutés : {index.relative_to(ROOT)}")
        else:
            print(f"  (simulation) marqueurs à ajouter : {index.relative_to(ROOT)}")
    for dossier in dossiers_sans_index():
        nom = titre(dossier).replace('"', '\\"')
        chemin = dossier / "index.md"
        if appliquer:
            chemin.write_text(f'---\ntitle: "{nom}"\n---\n\n{MARQUEURS}', encoding="utf-8")
            print(f"  ✓ créé : {chemin.relative_to(ROOT)}")
        else:
            print(f"  (simulation) à créer : {chemin.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(appliquer="--appliquer" in sys.argv))
