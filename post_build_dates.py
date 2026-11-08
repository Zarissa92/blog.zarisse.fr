#!/usr/bin/env python3
"""Dates des flux RSS/JSON : date de création des fichiers sources (au lieu de la date du build).

Appelé par build.py après `zensical build`. Travaille uniquement sur site/ ; docs/ n'est pas modifié.

Pour chaque article, le fichier source est retrouvé à partir de son lien (docs/<chemin>.md ou
docs/<chemin>/index.md), puis :
  - flux « créés »  (feed_rss_created.xml, feed_json_created.json) : date = date de CRÉATION du fichier ;
  - flux « mis à jour » (feed_rss_updated.xml, feed_json_updated.json) : date = date de MODIFICATION.
Le JSON garde date_published (création) et date_modified (modification) dans les deux flux.
La date de création vient de `stat -c %W` (Linux, btrfs/ext4…). Si elle est indisponible
(0), la date de modification est utilisée pour ce fichier. Les articles sont triés du plus récent au plus ancien.

Idempotent : relancer le build réécrit les mêmes dates.
"""
import email.utils
import html
import json
import re
import subprocess
import sys
import tomllib
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parent
SITE = ROOT / "site"
DOCS = ROOT / "docs"
# Même source que le canonical de Zensical : zensical.toml -> [project] site_url
SITE_URL = tomllib.loads((ROOT / "zensical.toml").read_text(encoding="utf-8"))["project"]["site_url"]

RE_ITEM = re.compile(r"<item>.*?</item>", re.S)
RE_LINK = re.compile(r"<link>(.*?)</link>", re.S)
RE_PUBDATE = re.compile(r"<pubDate>[^<]*</pubDate>")

# flux RSS : fichier -> source de la date
FLUX_RSS = {"feed_rss_created.xml": "creation", "feed_rss_updated.xml": "modification"}
FLUX_JSON = {"feed_json_created.json": "creation", "feed_json_updated.json": "modification"}


def fichier_source(lien):
    """<site_url>Fiches_Wiki/meow/ -> docs/Fiches_Wiki/meow.md (ou …/meow/index.md).
    Les liens encodés (My%20Life, accents…) sont décodés avant la recherche du fichier."""
    if not lien.startswith(SITE_URL):
        return None
    rel = unquote(lien[len(SITE_URL):].split("?")[0].split("#")[0]).strip("/")
    candidats = [DOCS / "index.md"] if rel == "" else [DOCS / (rel + ".md"), DOCS / rel / "index.md"]
    for c in candidats:
        if c.exists():
            return c
    return None


def dates_fichier(chemin):
    """(création, modification) en timestamps. Création = None si indisponible."""
    st = chemin.stat()
    try:
        out = subprocess.run(["stat", "-c", "%W", str(chemin)], capture_output=True, text=True, check=True)
        naissance = int(out.stdout.strip())
    except (subprocess.CalledProcessError, ValueError, FileNotFoundError):
        naissance = 0
    return (naissance or None), st.st_mtime


def date_choisie(source, creation, modification):
    """Renvoie le timestamp à afficher selon la source demandée, avec repli sur la modification."""
    if source == "creation" and creation is not None:
        return creation
    return modification


def rfc822(ts):
    return email.utils.format_datetime(datetime.fromtimestamp(ts, timezone.utc))


def iso(ts):
    return datetime.fromtimestamp(ts, timezone.utc).isoformat(timespec="seconds")


def traiter_rss(chemin_flux, source, stats):
    texte = chemin_flux.read_text(encoding="utf-8")
    items = list(RE_ITEM.finditer(texte))
    if not items:
        return
    nouveaux = []
    for m in items:
        bloc = m.group(0)
        lien = html.unescape(RE_LINK.search(bloc).group(1)).strip()
        src = fichier_source(lien)
        if src is None:
            stats["sans_source"] += 1
            nouveaux.append((None, bloc))
            continue
        creation, modification = dates_fichier(src)
        ts = date_choisie(source, creation, modification)
        if source == "creation" and creation is None:
            stats["repli"] += 1
        bloc = RE_PUBDATE.sub(lambda _: f"<pubDate>{rfc822(ts)}</pubDate>", bloc, count=1)
        nouveaux.append((ts, bloc))
        stats["articles"] += 1
    # tri du plus récent au plus ancien (les articles sans source gardent leur ordre, en fin)
    nouveaux.sort(key=lambda x: -(x[0] or 0))
    debut, fin = items[0].start(), items[-1].end()
    texte = texte[:debut] + "".join(b for _, b in nouveaux) + texte[fin:]
    # date de la chaîne = article le plus récent
    recent = max((t for t, _ in nouveaux if t is not None), default=None)
    if recent is not None:
        avant = texte[:debut]
        apres = texte[debut:]
        avant = RE_PUBDATE.sub(lambda _: f"<pubDate>{rfc822(recent)}</pubDate>", avant, count=1)
        texte = avant + apres
    chemin_flux.write_text(texte, encoding="utf-8")


def traiter_json(chemin_flux, source, stats):
    donnees = json.loads(chemin_flux.read_text(encoding="utf-8"))
    articles = []
    for it in donnees.get("items", []):
        src = fichier_source(it.get("url") or it.get("id") or "")
        if src is None:
            stats["sans_source"] += 1
            articles.append((0, it))
            continue
        creation, modification = dates_fichier(src)
        ts = date_choisie(source, creation, modification)
        if source == "creation" and creation is None:
            stats["repli"] += 1
        # JSON : date_published = création (repli : modification), date_modified = modification
        it["date_published"] = iso(creation or modification)
        it["date_modified"] = iso(modification)
        articles.append((ts, it))
        stats["articles"] += 1
    articles.sort(key=lambda x: -x[0])
    donnees["items"] = [it for _, it in articles]
    chemin_flux.write_text(json.dumps(donnees, ensure_ascii=False, indent=2), encoding="utf-8")


def main():
    stats = {"articles": 0, "repli": 0, "sans_source": 0}
    for nom, source in FLUX_RSS.items():
        chemin = SITE / nom
        if chemin.exists():
            traiter_rss(chemin, source, stats)
    for nom, source in FLUX_JSON.items():
        chemin = SITE / nom
        if chemin.exists():
            traiter_json(chemin, source, stats)
    print(f"Dates des flux : {stats['articles']} article(s) daté(s) depuis les fichiers sources.")
    if stats["repli"]:
        print(f"  {stats['repli']} date(s) de création indisponible(s) : date de modification utilisée.")
    if stats["sans_source"]:
        print(f"  {stats['sans_source']} article(s) sans fichier source : date du build conservée.")


if __name__ == "__main__":
    sys.exit(main())
