#!/usr/bin/env python3
"""Construit le site : dates des pages (dater_pages.py), Zensical, dates des flux
(post_build_dates.py), contrôle des flux RSS, puis balises Open Graph (post_build_og.py).

Les flux RSS sont produits par le plugin `rss` de Zensical (zensical.toml) ;
l'étape « Flux RSS » vérifie qu'ils existent, sont du XML valide et contiennent des articles.

Usage : python3 build.py [--forcer] [--serve]
Les images de partage ne sont refaites que si leur contenu a changé ;
--forcer les régénère toutes (voir empreintes.py).
--serve : après le build, sert site/ sur http://localhost:8000 (Ctrl+C pour arrêter).
C'est exactement ce qui sera déployé ; `zensical serve` seul, lui, refait site/ sans les étapes
post-build (dates des flux, images et balises de partage).
Le script s'arrête dès qu'une étape échoue.
"""
import functools
import http.server
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ZENSICAL = ROOT / "venv_blog" / "bin" / "zensical"
SITE = ROOT / "site"
# Flux attendus : ceux référencés par overrides/main.html et overrides/partials/header.html
FLUX_RSS = ["feed_rss_created.xml", "feed_rss_updated.xml"]
FEUILLE_STYLE = "rss.xsl"
ADRESSE_SERVE = ("127.0.0.1", 8000)

sys.path.insert(0, str(ROOT))
import billets_index  # noqa: E402
import dater_pages  # noqa: E402
import post_build_dates  # noqa: E402
import post_build_og  # noqa: E402
import post_build_og_images  # noqa: E402


def verifier_flux_rss() -> bool:
    """Contrôle les flux RSS générés dans site/. Renvoie False en cas de problème."""
    ok = True
    if not (SITE / FEUILLE_STYLE).exists():
        print(f"  ✗ feuille de style absente : {FEUILLE_STYLE}", file=sys.stderr)
        ok = False
    for nom in FLUX_RSS:
        chemin = SITE / nom
        if not chemin.exists():
            print(f"  ✗ flux absent : {nom}", file=sys.stderr)
            ok = False
            continue
        try:
            canal = ET.parse(chemin).getroot().find("channel")
        except ET.ParseError as e:
            print(f"  ✗ XML invalide dans {nom} : {e}", file=sys.stderr)
            ok = False
            continue
        if canal is None:
            print(f"  ✗ élément <channel> absent dans {nom}", file=sys.stderr)
            ok = False
            continue
        nb = len(canal.findall("item"))
        if nb == 0:
            print(f"  ✗ aucun article dans {nom}", file=sys.stderr)
            ok = False
        else:
            print(f"  ✓ {nom} : {nb} article(s)")
    return ok


class _Gestionnaire(http.server.SimpleHTTPRequestHandler):
    """Serveur statique de site/ ; une page absente renvoie le 404.html du site, comme en ligne."""

    def send_error(self, code, message=None, explain=None):
        page_404 = SITE / "404.html"
        if code != 404 or not page_404.exists():
            return super().send_error(code, message, explain)
        contenu = page_404.read_bytes()
        self.send_response(404)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(contenu)))
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(contenu)


def servir() -> int:
    """Sert site/ en local jusqu'à Ctrl+C."""
    gestionnaire = functools.partial(_Gestionnaire, directory=str(SITE))
    with http.server.ThreadingHTTPServer(ADRESSE_SERVE, gestionnaire) as serveur:
        print(f"==> Aperçu sur http://localhost:{ADRESSE_SERVE[1]}/ (Ctrl+C pour arrêter)", flush=True)
        try:
            serveur.serve_forever()
        except KeyboardInterrupt:
            print("\nServeur arrêté.")
    return 0


def main() -> int:
    print("==> Dates des pages")
    # ajoute date (création / modification) au front matter des pages qui n'en ont pas encore
    dater_pages.main(appliquer=True, silencieux=True)

    print("==> Liste des billets")
    # remplace la liste entre les marqueurs de docs/Billets2Blog/index.md (voir billets_index.py)
    if billets_index.main() != 0:
        return 1

    print("==> Build Zensical")
    try:
        subprocess.run([str(ZENSICAL), "build"], cwd=ROOT, check=True)
    except subprocess.CalledProcessError as e:
        print(f"Échec du build Zensical (code {e.returncode}).", file=sys.stderr)
        return e.returncode

    print("==> Dates des flux")
    post_build_dates.main()

    print("==> Flux RSS")
    if not verifier_flux_rss():
        print("Échec : flux RSS incomplets ou invalides.", file=sys.stderr)
        return 1

    print("==> Images de partage")
    post_build_og_images.main()

    print("==> Balises Open Graph")
    post_build_og.main()

    print("Site prêt dans", SITE)
    if "--serve" in sys.argv:
        return servir()
    return 0


if __name__ == "__main__":
    sys.exit(main())
