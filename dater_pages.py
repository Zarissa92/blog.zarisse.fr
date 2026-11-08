#!/usr/bin/env python3
"""Date les pages de docs/ (lancé à chaque build par build.py).

Dans le front matter de chaque page .md :
    date:
      created: AAAA-MM-JJ   # date de création du fichier (repli : modification)
      updated: AAAA-MM-JJ   # date de modification
Une page sans clé `date` reçoit les deux dates (et un front matter si elle n'en a pas).
Une page déjà datée garde sa date `created` ; seule `updated` avance, quand le fichier a été
modifié après la date notée. Le reste du contenu n'est pas modifié.

Sans option : simulation, rien n'est écrit.
Avec --appliquer : écrit les pages.

Usage :
  python3 dater_pages.py               # simulation
  python3 dater_pages.py --appliquer   # écriture
"""
import datetime
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
import post_build_dates as pbd  # noqa: E402  (dates_fichier : création via stat, repli sur la modification)

DOCS = ROOT / "docs"
RE_FM = re.compile(r"^---\n(.*?\n)?---\n", re.S)


def jour(ts):
    return datetime.datetime.fromtimestamp(ts).strftime("%Y-%m-%d")


# bloc `date:` du front matter, puis sa ligne `updated:` (bloc indenté uniquement)
RE_BLOC_DATE = re.compile(r"^date\s*:[ \t]*\n((?:[ \t]+.*\n)*)", re.M)
RE_UPDATED = re.compile(r"^([ \t]+updated\s*:\s*)['\"]?(\d{4}-\d{2}-\d{2})['\"]?[ \t]*$", re.M)


def nouveau_texte(texte, cree, modifie):
    """Renvoie le texte avec la date ajoutée ou avancée, ou None s'il n'y a rien à changer.

    Sans clé `date` : ajoute created et updated.
    Avec un bloc `date:` dont `updated` est plus ancienne que `modifie` : avance seulement `updated`.
    Une clé `date` écrite autrement (sur une seule ligne, par exemple) n'est pas touchée.
    """
    bloc = f"date:\n  created: {cree}\n  updated: {modifie}\n"
    m = RE_FM.match(texte)
    if not m:
        return "---\n" + bloc + "---\n" + texte
    fm = m.group(1) or ""
    if not re.search(r"^date\s*:", fm, re.M):
        return "---\n" + fm + bloc + "---\n" + texte[m.end():]
    m_bloc = RE_BLOC_DATE.search(fm)
    if not m_bloc:
        return None
    m_upd = RE_UPDATED.search(m_bloc.group(1))
    if not m_upd or m_upd.group(2) >= modifie:  # dates AAAA-MM-JJ : l'ordre du texte suffit
        return None
    ligne = m_bloc.start(1) + m_upd.start()
    fin_ligne = m_bloc.start(1) + m_upd.end()
    fm = fm[:ligne] + m_upd.group(1) + modifie + fm[fin_ligne:]
    return "---\n" + fm + "---\n" + texte[m.end():]


def main(appliquer=None, silencieux=False):
    """Ajoute les dates manquantes. appliquer=None : lu sur la ligne de commande (--appliquer).
    silencieux=True : pas de détail, utilisé par build.py (qui écrit toujours)."""
    if appliquer is None:
        appliquer = "--appliquer" in sys.argv
    modifications = []
    for p in sorted(DOCS.rglob("*.md")):
        texte = p.read_text(encoding="utf-8")
        naissance, modification = pbd.dates_fichier(p)
        cree = jour(naissance or modification)
        maj = jour(modification)
        nouveau = nouveau_texte(texte, cree, maj)
        rel = p.relative_to(ROOT)
        if nouveau is None:
            if not silencieux:
                print(f"  = {rel} (date à jour)")
            continue
        modifications.append((p, nouveau))
        if not silencieux:
            print(f"  + {rel} : modifiée {maj}")

    if silencieux and not modifications:
        return 0
    print(f"\n{len(modifications)} page(s) à dater.")
    if not appliquer:
        print("Simulation : rien n'a été écrit. Relance avec --appliquer pour écrire.")
        return 0
    for p, texte in modifications:
        p.write_text(texte, encoding="utf-8")
    print(f"Écrit : {len(modifications)} page(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
