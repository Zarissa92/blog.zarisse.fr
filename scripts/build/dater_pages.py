#!/usr/bin/env python3
"""Date les pages de docs/ (lancé à chaque build par build.py).

Dans le front matter de chaque page .md :
    date:
      created: AAAA-MM-JJ HH:MM   # création du fichier (repli : modification)
      updated: AAAA-MM-JJ HH:MM   # modification
Les heures sont en heure française (Europe/Paris, heure d'été comprise), à la minute.
Une page sans clé `date` reçoit les deux dates (et un front matter si elle n'en a pas).
Une page déjà datée garde sa date `created` ; seule `updated` avance, quand le fichier a été
modifié après la date notée. Une date notée sans heure (AAAA-MM-JJ) reçoit l'heure du fichier
si c'est le même jour ; sinon elle reste telle quelle. Le reste du contenu n'est pas modifié.
Après l'écriture, la date de modification du fichier est remise à sa valeur d'avant : noter
la date ne compte pas comme une modification de la page.

Sans option : simulation, rien n'est écrit.
Avec --appliquer : écrit les pages.

Usage :
  venv_blog/bin/python dater_pages.py               # simulation
  venv_blog/bin/python dater_pages.py --appliquer   # écriture
"""
import datetime
import os
import re
import sys
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))  # modules du même dossier
import post_build_dates as pbd  # noqa: E402  (dates_fichier : création via stat, repli sur la modification)

DOCS = ROOT / "docs"
RE_FM = re.compile(r"^---\n(.*?\n)?---\n", re.S)
FUSEAU = ZoneInfo("Europe/Paris")  # heure française, quel que soit le réglage de la machine


def horodatage(ts):
    """Timestamp -> « AAAA-MM-JJ HH:MM » en heure française."""
    return datetime.datetime.fromtimestamp(ts, FUSEAU).strftime("%Y-%m-%d %H:%M")


# bloc `date:` du front matter, puis ses lignes `created:` / `updated:` (bloc indenté uniquement)
RE_BLOC_DATE = re.compile(r"^date\s*:[ \t]*\n((?:[ \t]+.*\n)*)", re.M)


def re_cle(cle):
    return re.compile(
        rf"^([ \t]+{cle}\s*:\s*)['\"]?(\d{{4}}-\d{{2}}-\d{{2}}(?:[ T]\d{{2}}:\d{{2}}(?::\d{{2}})?)?)['\"]?[ \t]*$",
        re.M,
    )


RE_CREATED = re_cle("created")
RE_UPDATED = re_cle("updated")


def valeur_cree(notee, cree):
    """Nouvelle valeur de `created`, ou None si elle ne change pas.
    Seul ajout possible : l'heure, quand la date notée n'en a pas et tombe le même jour."""
    if len(notee) == 10 and notee == cree[:10]:
        return cree
    return None


def valeur_maj(notee, modifie):
    """Nouvelle valeur de `updated`, ou None si elle ne change pas."""
    if len(notee) == 10:  # date sans heure : on compare au jour près
        if modifie[:10] > notee or modifie[:10] == notee:
            return modifie
        return None
    if modifie > notee[:16]:  # « AAAA-MM-JJ HH:MM » : l'ordre du texte suffit
        return modifie
    return None


def nouveau_texte(texte, cree, modifie):
    """Renvoie le texte avec la date ajoutée, avancée ou complétée, ou None s'il n'y a rien à changer.

    Sans clé `date` : ajoute created et updated.
    Avec un bloc `date:` : avance `updated` si le fichier a été modifié depuis, et ajoute l'heure
    aux dates notées sans heure quand elles tombent le jour du fichier.
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
    contenu = m_bloc.group(1)
    change = False
    for motif, calcul, ref in ((RE_CREATED, valeur_cree, cree), (RE_UPDATED, valeur_maj, modifie)):
        m_cle = motif.search(contenu)
        if not m_cle:
            continue
        valeur = calcul(m_cle.group(2), ref)
        if valeur is None or valeur == m_cle.group(2):
            continue
        contenu = contenu[:m_cle.start()] + m_cle.group(1) + valeur + contenu[m_cle.end():]
        change = True
    if not change:
        return None
    fm = fm[:m_bloc.start(1)] + contenu + fm[m_bloc.end(1):]
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
        cree = horodatage(naissance or modification)
        maj = horodatage(modification)
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
        st = p.stat()
        p.write_text(texte, encoding="utf-8")
        os.utime(p, ns=(st.st_atime_ns, st.st_mtime_ns))  # noter la date n'est pas une modification
    print(f"Écrit : {len(modifications)} page(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
