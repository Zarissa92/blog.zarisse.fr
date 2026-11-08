#!/usr/bin/env python3
"""Génère une image de partage (1200×630) pour chaque page, à partir de son titre et de sa description.

Les images sont écrites dans site/assets/og/<page>.png (une par page, nommée d'après son chemin :
divers/ressources -> divers-ressources.png ; l'accueil -> index.png).
post_build_og.py les utilise comme og:image quand la page n'a pas de `og_image` dans son front matter.

Les pages qui ont déjà un `og_image` ne sont pas touchées. Les pages sans source (redirections,
404) sont ignorées. Une image n'est redessinée que si son titre, sa description ou ce script ont
changé (voir empreintes.py) ; sinon la copie gardée dans .cache/og/ est reprise.

Dépendance : Pillow (venv_blog/bin/python -m pip install pillow).
"""
import html
import re
import shutil
import unicodedata
from pathlib import Path

import yaml
from PIL import Image, ImageDraw, ImageFont

from empreintes import Empreintes, hache

ROOT = Path(__file__).resolve().parent
SITE = ROOT / "site"
DOCS = ROOT / "docs"
DOSSIER_IMAGES = SITE / "assets" / "og"
DOSSIER_CACHE = ROOT / ".cache" / "og"
LARGEUR, HAUTEUR = 1200, 630
SUFFIXE_TITRE = " - Blog de Zaza"
NOM_SITE = "zarisse.fr"
AVATAR = DOCS / "assets" / "avatar.jpg"
_AVATAR_OCTETS = AVATAR.read_bytes() if AVATAR.exists() else b""
_CODE_OCTETS = Path(__file__).read_bytes()

# Couleurs de pluie.css (thème « matrix »)
FOND = (18, 19, 23)
BLEU = (91, 206, 250)
ROSE = (245, 169, 184)
VIOLET_DOUX = (195, 155, 211)
TEXTE = (236, 226, 242)

POLICES_GRAS = [
    "/usr/share/fonts/TTF/FiraSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
]
POLICES_TEXTE = [
    "/usr/share/fonts/TTF/FiraSans-Regular.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
]

RE_TITLE = re.compile(r"<title>(.*?)</title>", re.S)
RE_DESC = re.compile(r'<meta name="description" content="(.*?)">', re.S)
RE_FM = re.compile(r"^---\n(.*?)\n---\n", re.S)


def police(candidates: list[str], taille: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for chemin in candidates:
        if Path(chemin).exists():
            return ImageFont.truetype(chemin, taille)
    return ImageFont.load_default(size=taille)


def nom_image(rel: Path) -> str:
    """divers/ressources -> divers-ressources ; racine -> index."""
    morceaux = [unicodedata.normalize("NFKD", p).encode("ascii", "ignore").decode() for p in rel.parts]
    slug = re.sub(r"[^a-z0-9]+", "-", "-".join(morceaux).lower()).strip("-")
    return slug or "index"


def source_de(rel: Path) -> Path | None:
    """rel = chemin de la page dans site/ (sans index.html) -> fichier source Markdown."""
    for cand in (DOCS / rel.with_suffix(".md") if rel.parts else DOCS / "index.md",
                 DOCS / rel / "index.md"):
        if cand.exists():
            return cand
    return None


def front_matter(src: Path) -> dict:
    m = RE_FM.match(src.read_text(encoding="utf-8"))
    return (yaml.safe_load(m.group(1)) or {}) if m else {}


def decoupe(texte: str, draw: ImageDraw.ImageDraw, font, largeur_max: int, lignes_max: int) -> list[str] | None:
    """Coupe le texte en lignes ; renvoie None si cela ne tient pas dans lignes_max."""
    mots, lignes, courante = texte.split(), [], ""
    for mot in mots:
        essai = f"{courante} {mot}".strip()
        if draw.textlength(essai, font=font) <= largeur_max:
            courante = essai
        else:
            if courante:
                lignes.append(courante)
            courante = mot
            if draw.textlength(mot, font=font) > largeur_max:
                return None
    if courante:
        lignes.append(courante)
    return lignes if len(lignes) <= lignes_max else None


def dessiner(titre: str, description: str, sortie: Path) -> None:
    img = Image.new("RGB", (LARGEUR, HAUTEUR), FOND)
    draw = ImageDraw.Draw(img)
    marge = 56
    largeur_texte = LARGEUR - 2 * marge - 40

    # cadre bleu et liseré rose, comme le cadre principal du thème
    draw.rectangle([24, 24, LARGEUR - 25, HAUTEUR - 25], outline=BLEU, width=4)
    draw.rectangle([40, 40, LARGEUR - 41, HAUTEUR - 41], outline=ROSE, width=1)

    # avatar en haut à gauche
    if AVATAR.exists():
        av = Image.open(AVATAR).convert("RGB").resize((104, 104))
        masque = Image.new("L", (104, 104), 0)
        ImageDraw.Draw(masque).ellipse([0, 0, 103, 103], fill=255)
        img.paste(av, (marge, marge), masque)
        draw.ellipse([marge - 3, marge - 3, marge + 107, marge + 107], outline=BLEU, width=3)
    draw.text((marge + 128, marge + 52), NOM_SITE, font=police(POLICES_TEXTE, 34), fill=BLEU, anchor="lm")

    # titre et description : on réduit la taille jusqu'à ce que tout tienne
    y_debut = 230
    taille_titre = 84
    while taille_titre >= 40:
        f_titre = police(POLICES_GRAS, taille_titre)
        lignes_titre = decoupe(titre, draw, f_titre, largeur_texte, 2)
        if lignes_titre:
            break
        taille_titre -= 4
    else:
        lignes_titre = [titre[:60] + "…"]
        f_titre = police(POLICES_GRAS, 40)

    f_desc = police(POLICES_TEXTE, 34)
    lignes_desc = decoupe(description, draw, f_desc, largeur_texte, 3) or [
        " ".join(description.split()[:12]) + "…"
    ]

    y = y_debut
    for ligne in lignes_titre:
        draw.text((marge, y), ligne, font=f_titre, fill=VIOLET_DOUX)
        y += int(taille_titre * 1.15)
    y += 28
    for ligne in lignes_desc:
        draw.text((marge, y), ligne, font=f_desc, fill=TEXTE)
        y += 46

    sortie.parent.mkdir(parents=True, exist_ok=True)
    img.save(sortie, "PNG", optimize=True)


def generer(site: Path = SITE) -> tuple[int, int]:
    """Crée les images de partage modifiées ; renvoie (créées, inchangées)."""
    n = 0
    emp = Empreintes("og")
    n_ignorees = 0
    for page in sorted(site.rglob("index.html")):
        rel = page.relative_to(site).parent
        if rel.parts and rel.parts[0] == "assets":
            continue
        texte = page.read_text(encoding="utf-8")
        if "Redirecting..." in texte[:600]:
            continue
        src = source_de(rel)
        if src is None:
            continue
        fm = front_matter(src)
        if fm.get("og_image"):
            continue  # image choisie à la main : on la garde

        m_title = RE_TITLE.search(texte)
        if not m_title:
            continue
        titre = html.unescape(m_title.group(1)).strip()
        if titre.endswith(SUFFIXE_TITRE):
            titre = titre[: -len(SUFFIXE_TITRE)].strip()
        m_desc = RE_DESC.search(texte)
        description = str(fm.get("og_description") or fm.get("description")
                          or (html.unescape(m_desc.group(1)) if m_desc else "")).strip()

        # l'image ne dépend que du titre, de la description, de l'avatar et de ce script
        # zensical vide site/ à chaque build : les images sont gardées dans .cache/og/ et recopiées
        cle = str(rel)
        empreinte = hache(titre, description, _AVATAR_OCTETS, _CODE_OCTETS)
        cache = DOSSIER_CACHE / f"{nom_image(rel)}.png"
        if emp.a_jour(cle, empreinte, cache):
            n_ignorees += 1
        else:
            dessiner(titre, description, cache)
            n += 1
        emp.noter(cle, empreinte)
        DOSSIER_IMAGES.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(cache, DOSSIER_IMAGES / cache.name)
    emp.enregistrer()
    return n, n_ignorees


def main() -> None:
    n, n_ignorees = generer()
    print(f"Images de partage générées pour {n} page(s), {n_ignorees} inchangée(s), dans {DOSSIER_IMAGES}.")


if __name__ == "__main__":
    main()
