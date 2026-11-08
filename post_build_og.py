#!/usr/bin/env python3
"""Ajoute les balises Open Graph / Twitter aux pages générées par Zensical.

Travaille uniquement sur site/ (sortie du build) : le thème et docs/ ne sont pas modifiés.
Les valeurs se règlent dans le front matter de chaque page source (docs/…md) :
  - description   : meta description, reprise pour og:description
  - og_description: (optionnel) texte de partage, s'il diffère de la description
  - og_image      : (optionnel) chemin de l'image de partage, relatif à la racine du site
                    (ex. assets/img/x.jpg) ; sinon l'image générée par post_build_og_images.py
                    (assets/og/<page>.png), et à défaut assets/partage.jpg
À lancer après `venv_blog/bin/zensical build`. Idempotent : les pages déjà traitées sont ignorées.
"""
import html
import re
import tomllib
from pathlib import Path

import yaml

from post_build_og_images import nom_image

ROOT = Path(__file__).resolve().parent
SITE = ROOT / "site"
DOCS = ROOT / "docs"
# Même source que le canonical de Zensical : zensical.toml -> [project] site_url
SITE_URL = tomllib.loads((ROOT / "zensical.toml").read_text(encoding="utf-8"))["project"]["site_url"]
SITE_NAME = "Blog de Zaza"
IMAGE_DEFAUT = "assets/partage.jpg"  # 1200x630 : aperçu « grand format » sur Discord, Mastodon…
IMAGE_DEFAUT_TAILLE = (1200, 630)

RE_TITLE = re.compile(r"<title>(.*?)</title>", re.S)
RE_DESC = re.compile(r'<meta name="description" content="(.*?)">', re.S)
RE_CANON = re.compile(r'<link rel="canonical" href="(.*?)">', re.S)
RE_HEAD_END = re.compile(r"</head>", re.I)
RE_FM = re.compile(r"^---\n(.*?)\n---\n", re.S)


def source_de(page: Path) -> Path | None:
    """site/a/b/index.html -> docs/a/b.md ou docs/a/b/index.md."""
    rel = page.relative_to(SITE).parent
    for cand in (DOCS / rel.with_suffix(".md") if rel.parts else DOCS / "index.md",
                 DOCS / rel / "index.md"):
        if cand.exists():
            return cand
    return None


def front_matter(page: Path) -> dict:
    src = source_de(page)
    if not src:
        return {}
    m = RE_FM.match(src.read_text(encoding="utf-8"))
    return (yaml.safe_load(m.group(1)) or {}) if m else {}


def traiter(page: Path) -> bool:
    texte = page.read_text(encoding="utf-8")
    if 'property="og:title"' in texte or "Redirecting..." in texte[:600]:
        return False
    m_title = RE_TITLE.search(texte)
    if not m_title or not RE_HEAD_END.search(texte):
        return False
    fm = front_matter(page)
    titre = html.unescape(m_title.group(1)).strip()
    m_desc = RE_DESC.search(texte)
    desc = html.unescape(m_desc.group(1)).strip() if m_desc else ""
    desc = str(fm.get("og_description") or desc)
    m_can = RE_CANON.search(texte)
    url = html.unescape(m_can.group(1)) if m_can else SITE_URL
    slug = nom_image(page.relative_to(SITE).parent)
    if fm.get("og_image"):
        image_rel = str(fm["og_image"]).lstrip("/")
    elif (SITE / "assets" / "og" / f"{slug}.png").exists():
        image_rel = f"assets/og/{slug}.png"  # image générée par post_build_og_images.py
    else:
        image_rel = IMAGE_DEFAUT
    image = SITE_URL + image_rel
    # dimensions connues seulement pour les images 1200x630 (par défaut ou générées)
    grand = image_rel == IMAGE_DEFAUT or image_rel.startswith("assets/og/")
    taille = [
        f'<meta property="og:image:width" content="{IMAGE_DEFAUT_TAILLE[0]}">',
        f'<meta property="og:image:height" content="{IMAGE_DEFAUT_TAILLE[1]}">',
    ] if grand else []

    balises = [
        '<meta property="og:type" content="website">',
        '<meta property="og:locale" content="fr_FR">',
        f'<meta property="og:site_name" content="{html.escape(SITE_NAME)}">',
        f'<meta property="og:title" content="{html.escape(titre)}">',
    ]
    if desc:
        balises.append(f'<meta property="og:description" content="{html.escape(desc)}">')
    balises += [
        f'<meta property="og:url" content="{html.escape(url)}">',
        f'<meta property="og:image" content="{html.escape(image)}">',
    ]
    balises += taille
    balises.append(f'<meta name="twitter:card" content="{"summary_large_image" if grand else "summary"}">')
    bloc = "\n".join("      " + b for b in balises) + "\n    "
    texte = RE_HEAD_END.sub(lambda _: bloc + "</head>", texte, count=1)
    page.write_text(texte, encoding="utf-8")
    return True


def main() -> None:
    n = 0
    for page in sorted(SITE.rglob("index.html")):
        if traiter(page):
            n += 1
    print(f"Balises Open Graph ajoutées à {n} page(s).")


if __name__ == "__main__":
    main()
