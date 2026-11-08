#!/usr/bin/env python3
"""
wikipick_site.py — reconstitue une collection wiki-pick sur un site Zensical.

Entrée : soit le texte de l'extraction de cartes du script Album, collé tel quel
dans un fichier (collection.txt), soit un collection.json au format :
    {
      "albums": [
        {"nom": "Châteaux de France",
         "cartes": [{"titre": "Château de Chambord"}, {"titre": "Château de Blois", "rarete": "rare"}]}
      ]
    }
  Les cartes peuvent aussi être de simples chaînes : "cartes": ["Château de Chambord", ...]

Pour chaque titre, le script interroge fr.wikipedia (API REST "summary") :
  - image (thumbnail Wikimedia Commons)
  - description (issue de Wikidata)
  - résumé de l'article (synopsis)
puis les métadonnées de licence de l'image (auteur, licence) pour l'attribution.

Tout est mis en cache dans wiki_cache.json : seules les nouvelles cartes sont
demandées à Wikipédia lors des mises à jour suivantes.

Réglages utilisateur : bloc CONFIG juste en dessous (dossier d'enregistrement, nom de la
collection, fichier d'entrée). Rien d'autre à passer en ligne de commande.

Un fichier texte = une catégorie : elle porte le nom du fichier sans son extension, précédé des
emojis de ses lignes de catégorie (« Queens.txt » contenant « 2💅Queens (251) » -> « 💅Queens ») ;
le reste de ces lignes est ignoré. Pour renommer une catégorie, renomme le fichier.

Catégories repliables : avec une collection (CONFIG["collection"] non vide), les cartes sont
rangées par catégorie sur la page, un fichier après l'autre. Les catégories sont repliées à
l'ouverture de la page : un clic sur le titre d'une catégorie la déplie ou la replie
(<details>, sans JavaScript). Le style est dans
docs/assets/collection.css (bloc « CATÉGORIES REPLIABLES »).

Questions, avant toute requête et avant d'écrire quoi que ce soit (comme ajouter_categories.py) :
  1. le script lit la page et liste ses catégories et celles du fichier, avec leur nombre de
     cartes : tape les numéros à retirer (ex. 1,3), ou Entrée pour n'en retirer aucune.
     Une catégorie retirée perd son titre et ses cartes ; si elle est aussi dans le fichier,
     ses cartes ne sont pas ajoutées ;
  2. pour les catégories mises à jour par le fichier, les cartes de la page qui ne sont plus
     dans le fichier sont listées : « o » les supprime, Entrée les garde.
  Sans terminal (tâche planifiée…), aucune question n'est posée et rien n'est supprimé.

Rien n'est supprimé sans ton accord :
  - les cartes déjà sur le site restent, sauf si tu choisis de les supprimer ;
  - les catégories de la page absentes du fichier restent telles quelles, sauf si tu les retires ;
  - le texte écrit à la main sur une page de collection, avant ou après le bloc généré
    (entre les commentaires wikipick:debut et wikipick:fin), est gardé ;
  - les images déjà téléchargées restent dans docs/assets/img/ ;
  - le cache n'est jamais vidé, même avec --refresh (les autres cartes y restent).

Sortie, dans CONFIG["dossier"] (créé s'il n'existe pas ; doit être dans le docs/ de Zensical) :
  index.md                -> page d'accueil, les collections s'y ajoutent
  <collection>.md         -> la page de la collection
  docs/assets/img/        -> les images téléchargées
Le cache wiki_cache.json (dans le dossier courant) n'est pas une page : il évite de
redemander Wikipédia à chaque lancement.

Dates : chaque page de collection affiche « mise à jour le … », date du dernier lancement
qui a changé quelque chose (carte ajoutée, retirée ou modifiée). Chaque carte garde la date de
son ajout dans wiki_historique.json (dans le dossier courant, à côté du cache). Ce fichier
alimente aussi le petit journal « Dernières modifications » de la page d'accueil (index.md).
Au premier lancement, les cartes déjà présentes n'apparaissent pas dans le journal et leur date
d'ajout reste inconnue ; seules les modifications suivantes sont journalisées.

Usage :
  python3 wikipick_site.py                       # utilise les réglages de CONFIG
  python3 wikipick_site.py Queens.txt            # autre fichier d'entrée : catégorie « 💅Queens »
  python3 wikipick_site.py --refresh             # redemande les cartes du fichier
"""

import argparse
import hashlib
import html
import json
import re
import shutil
import socket
import sys
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

# ===================== CONFIG (modifiable) =====================
CONFIG = {
    # --- À RÉGLER ---------------------------------------------------------
    "dossier": "~/zarisse.fr/docs/Fiches_Wiki/",  # où enregistrer les pages (dans docs/ ; créé s'il n'existe pas)
    "collection": "CaBouge",                      # nom de la collection (page trans.md) ; "" = noms du fichier
    "entree": "listes/CaBouge.txt",                 # fichier d'entrée (extraction Album ou JSON)
    "categories": True,               # collection : cartes rangées par catégorie du fichier (False = une seule grille)
    "categories_ouvertes": False,     # False = catégories repliées à l'ouverture (le visiteur déplie) ; True = dépliées
    # --- réglages avancés -------------------------------------------------
    "wiki": "fr.wikipedia.org",
    "commons": "commons.wikimedia.org",
    # Wikimedia demande un User-Agent identifiable avec un contact
    "user_agent": "WikiPickCollection/1.0 (https://zarisse.fr; site perso)",
    "pause_entre_requetes": 0.2,      # secondes, pour rester poli avec l'API
    "pause_max": 5.0,                 # pause maximale après des refus HTTP 429 (la pause double à chaque refus)
    "essais_max": 6,                  # essais par requête en cas de HTTP 429 / 503
    "largeur_image": 500,             # px ; largeurs standard Wikimedia (330, 500, 960…), les autres donnent une erreur 400
    "longueur_resume": 600,           # caractères max du résumé affiché (0 = complet)
    "titre_page": "Fiches wikipedia",   # titre fixe de la page d'accueil, quelle que soit la collection
    "dossier_images": "assets/img",   # dans docs/ de Zensical ; chemin des images = /assets/img/…
}
# ===============================================================

API_REST = "https://{wiki}/api/rest_v1/page/summary/{titre}"
API_ACTION = "https://{wiki}/w/api.php"

# repères du bloc généré sur une page de collection : ce qui est écrit en dehors est gardé
DEBUT_BLOC = "<!-- wikipick:debut (bloc généré par wikipick_site.py, réécrit à chaque lancement) -->"
DEBUT_REPERE = "<!-- wikipick:debut"
FIN_BLOC = "<!-- wikipick:fin -->"
# journal des modifications, sur la page d'accueil (index.md) : seul ce bloc est réécrit
DEBUT_JOURNAL = "<!-- wikipick:journal:debut -->"
FIN_JOURNAL = "<!-- wikipick:journal:fin -->"
JOURNAL_GARDES = 100      # événements conservés dans wiki_historique.json
JOURNAL_AFFICHES = 10     # événements affichés sur la page d'accueil

ATTENTES_429 = (5, 10, 20, 40, 60)     # secondes d'attente après un refus, essai après essai
PAUSE_ACTUELLE = CONFIG["pause_entre_requetes"]
REQUETES = 0
IMAGES_TELECHARGEES = 0
RESEAU_COUPE = ""                      # raison de l'arrêt des requêtes (vide = réseau utilisable)
DEBUT = time.monotonic()


class Abandon(Exception):
    """Wikimedia refuse encore (HTTP 429/503) ou le réseau ne répond plus : on arrête les requêtes."""


def attente_demandee(e):
    """Délai demandé par le serveur (en-tête Retry-After, en secondes), ou None."""
    v = e.headers.get("Retry-After") if e.headers else None
    try:
        return max(1, min(int(v), 300))
    except (TypeError, ValueError):
        return None


def http_get(url, binaire=False):
    """Une requête à la fois, avec une pause après chacune.
    HTTP 429 / 503 : attente (Retry-After, sinon 5, 10, 20, 40, 60 s), pause doublée, nouvel essai.
    Refus persistant ou réseau coupé : Abandon (le cache garde ce qui a déjà été trouvé)."""
    global PAUSE_ACTUELLE, REQUETES
    coupures = 0
    for essai in range(1, CONFIG["essais_max"] + 1):
        req = urllib.request.Request(url, headers={"User-Agent": CONFIG["user_agent"]})
        REQUETES += 1
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                data = r.read()
        except urllib.error.HTTPError as e:
            time.sleep(PAUSE_ACTUELLE)
            if e.code not in (429, 502, 503, 504):
                raise
            attente = attente_demandee(e) or ATTENTES_429[min(essai, len(ATTENTES_429)) - 1]
            PAUSE_ACTUELLE = min(max(PAUSE_ACTUELLE * 2, 0.5), CONFIG["pause_max"])
            print(f"    HTTP {e.code} : Wikimedia demande de ralentir. Attente {attente} s "
                  f"(essai {essai}/{CONFIG['essais_max']}), pause portée à {PAUSE_ACTUELLE:.1f} s",
                  file=sys.stderr)
            time.sleep(attente)
            continue
        except (urllib.error.URLError, socket.timeout, TimeoutError, ConnectionError) as e:
            coupures += 1
            raison = getattr(e, "reason", None) or e
            if coupures >= 3:
                raise Abandon(f"réseau injoignable ({raison})")
            print(f"    réseau : {raison}, nouvel essai dans {2 * coupures} s", file=sys.stderr)
            time.sleep(2 * coupures)
            continue
        time.sleep(PAUSE_ACTUELLE)
        return data if binaire else json.loads(data.decode("utf-8"))
    raise Abandon(f"Wikimedia refuse encore après {CONFIG['essais_max']} essais (HTTP 429/503)")


def slugify(texte):
    t = unicodedata.normalize("NFKD", texte).encode("ascii", "ignore").decode()
    t = re.sub(r"[^a-zA-Z0-9]+", "-", t).strip("-").lower()
    return t or "album"


def nettoyer_html(s):
    s = re.sub(r"<[^>]+>", "", s or "")
    return html.unescape(s).strip()


def duree():
    s = int(time.monotonic() - DEBUT)
    return f"{s // 60} min {s % 60:02d} s" if s >= 60 else f"{s} s"


def infos_licence(nom_fichier):
    """Auteur + licence d'un fichier image : Commons d'abord (là où sont presque toutes les images),
    puis la wiki (images locales). None en cas d'erreur : redemandé au prochain lancement."""
    for site in (CONFIG["commons"], CONFIG["wiki"]):
        params = {
            "action": "query", "format": "json", "formatversion": "2",
            "prop": "imageinfo", "iiprop": "extmetadata|url",
            "titles": "File:" + nom_fichier,
        }
        url = API_ACTION.format(wiki=site) + "?" + urllib.parse.urlencode(params)
        try:
            data = http_get(url)
        except Abandon:
            raise
        except Exception as e:
            print(f"  ! licence introuvable pour {nom_fichier} : {e}", file=sys.stderr)
            return None
        pages = data.get("query", {}).get("pages") or [{}]
        ii = (pages[0].get("imageinfo") or [None])[0]
        if ii:
            meta = ii.get("extmetadata", {})
            return {
                "auteur": nettoyer_html(meta.get("Artist", {}).get("value", "")) or "auteur inconnu",
                "licence": nettoyer_html(meta.get("LicenseShortName", {}).get("value", "")) or "voir la page du fichier",
                "page_fichier": ii.get("descriptionurl", ""),
            }
    # fichier absent de Commons et de la wiki : lien vers sa page, pas redemandé
    return {"auteur": "auteur inconnu", "licence": "voir la page du fichier",
            "page_fichier": f"https://{CONFIG['wiki']}/wiki/Fichier:"
                            + urllib.parse.quote(nom_fichier.replace(" ", "_"))}


def recuperer_carte(titre):
    """Interroge Wikipédia pour un titre d'article. Renvoie un dict, {'introuvable': True, 'http': 404}
    si l'article n'existe pas, ou None en cas d'erreur (pas mis en cache, on retentera)."""
    url = API_REST.format(wiki=CONFIG["wiki"],
                          titre=urllib.parse.quote(titre.replace(" ", "_"), safe=""))
    try:
        d = http_get(url)
    except Abandon:
        raise
    except urllib.error.HTTPError as e:
        if e.code == 404:
            print(f"  ! {titre} : article introuvable (HTTP 404)", file=sys.stderr)
            return {"introuvable": True, "http": 404}
        print(f"  ! {titre} : HTTP {e.code} (redemandé au prochain lancement)", file=sys.stderr)
        return None
    except Exception as e:
        print(f"  ! {titre} : {e}", file=sys.stderr)
        return None  # erreur réseau : pas mis en cache, on retentera

    carte = {
        "titre_article": d.get("title", titre),
        "description": d.get("description", ""),
        "resume": d.get("extract", ""),
        "url": d.get("content_urls", {}).get("desktop", {}).get("page", ""),
        "wikidata": d.get("wikibase_item", ""),
        "image": None,
    }
    img = d.get("originalimage") or d.get("thumbnail")
    if img and img.get("source"):
        orig = img["source"]
        nom_fichier = nom_original(orig.rsplit("/", 1)[-1])
        thumb = d.get("thumbnail", {}).get("source", orig)
        thumb = re.sub(r"/(\d+)px-", f"/{CONFIG['largeur_image']}px-", thumb)
        carte["image"] = {"url": thumb, "fichier": nom_fichier,
                          "licence": infos_licence(nom_fichier)}
    elif carte["wikidata"]:
        # Pas d'image principale dans l'article : on prend P18 (image) de Wikidata
        nom = image_wikidata(carte["wikidata"])
        if nom:
            carte["image"] = {
                "url": f"https://{CONFIG['commons']}/wiki/Special:FilePath/"
                       f"{urllib.parse.quote(nom)}?width={CONFIG['largeur_image']}",
                "fichier": nom,
                "licence": infos_licence(nom),
            }
    return carte


def etat_carte(r):
    """Résumé d'une réponse, pour l'affichage de la progression."""
    if r is None:
        return "erreur, redemandée au prochain lancement"
    if r.get("introuvable"):
        return "article introuvable"
    if r.get("image"):
        return "image trouvée" + ("" if r["image"].get("licence") else " (licence à compléter)")
    return "sans image"


def nom_original(nom):
    """Nom réel du fichier Commons : sans ?utm_…, sans préfixe de miniature (420px-, langfr-420px-), sans .png des SVG."""
    nom = urllib.parse.unquote(nom.split("?")[0])
    nom = re.sub(r"^(langfr-|langen-)?\d+px-", "", nom)
    if nom.lower().endswith(".svg.png"):
        nom = nom[:-4]
    return nom


def url_image(nom, site=None):
    """URL d'affichage d'une image : Special:FilePath sur Commons (ou sur le site indiqué), une seule URL, sans suivi.
    La largeur est demandée au serveur Wikimedia, qui redimensionne l'image (pas de traitement local)."""
    return (f"https://{site or CONFIG['commons']}/wiki/Special:FilePath/"
            f"{urllib.parse.quote(nom_original(nom))}?width={CONFIG['largeur_image']}")


def octets_image(nom):
    """Octets de l'image à la largeur configurée. Commons d'abord, puis fr.wikipedia : certaines images
    (logo One Piece, Logo_One_piece.svg) n'existent que sur la wiki et renvoient 404 sur Commons.
    Renvoie (octets, site trouvé). Une erreur autre que 404 (429, réseau…) remonte comme avant."""
    erreur = None
    for site in (CONFIG["commons"], CONFIG["wiki"]):
        try:
            return http_get(url_image(nom, site), binaire=True), site
        except urllib.error.HTTPError as e:
            if e.code != 404:
                raise
            erreur = e
    raise erreur


def image_wikidata(qid):
    """Nom du fichier Commons de la propriété P18 (image) d'un élément Wikidata, ou None."""
    params = {"action": "wbgetclaims", "entity": qid, "property": "P18", "format": "json"}
    url = f"https://www.wikidata.org/w/api.php?{urllib.parse.urlencode(params)}"
    try:
        claims = http_get(url).get("claims", {}).get("P18", [])
        return claims[0]["mainsnak"]["datavalue"]["value"] if claims else None
    except Abandon:
        raise
    except Exception as e:
        print(f"  ! wikidata {qid} : {e}", file=sys.stderr)
        return None


RE_TITRE = re.compile(r"^\*\*(.+?)\*\*$")
RE_NUMERO_TETE = re.compile(r"^\s*\d+\s*")


def nom_album(nom):
    """Nom affiché de la catégorie : sans le numéro en début (0🇨🇳china -> 🇨🇳china, 3trans -> trans)."""
    return RE_NUMERO_TETE.sub("", nom).strip() or nom
RE_COMPTE = re.compile(r"\s*\(\d+\)\s*$")


def cle_titre(titre):
    """Clé d'un titre de carte, sans accents, ponctuation ni majuscules (pour repérer les cartes absentes)."""
    t = "".join(ch for ch in unicodedata.normalize("NFKD", titre or "") if ch.isalnum()).lower()
    return t or (titre or "").strip().lower()


def cle_categorie(nom):
    """Clé d'une catégorie : sans compteur, emoji, accents ni majuscules
    (« 💅Queens (251) », « 👑Queens » et « queens » sont la même catégorie)."""
    s = RE_COMPTE.sub("", nom or "").strip()
    t = "".join(ch for ch in unicodedata.normalize("NFKD", s) if ch.isalnum()).lower()
    return t or s.lower()


def emojis(ligne):
    """Emojis d'une ligne de catégorie, séquences gardées entières :
    « 2💅Queens (251) » -> « 💅 », « 0🇨🇳china (5) » -> « 🇨🇳 », « 1🏳️‍🌈Fiertés » -> « 🏳️‍🌈 »."""
    return "".join(ch for ch in unicodedata.normalize("NFC", ligne)
                   if ord(ch) >= 0x2000 and unicodedata.category(ch) in ("So", "Sk", "Mn", "Me", "Cf"))


def nom_depuis_fichier(chemin, symboles):
    """Nom de la catégorie : nom du fichier sans extension, précédé des emojis trouvés dans ses
    lignes de catégorie (sauf s'ils sont déjà dans le nom du fichier)."""
    nom = Path(chemin).stem.strip()
    return "".join(e for e in symboles if e not in nom) + nom


def charger_extraction_album(texte, chemin):
    """
    Lit le texte de l'extraction de cartes du script Album :
        0🇨🇳china (5)
        <ligne vide>
        **Radical 86**
        clé chinoise traditionnelle feu (U+2F55)
        <ligne vide>
        **Métro de Tianjin**
        ...
    - ligne **...**                     -> titre de carte
    - ligne collée juste sous un titre  -> description de la carte
    - autre ligne non vide              -> ligne de catégorie : seuls ses emojis sont gardés
    Toutes les cartes vont dans une seule catégorie, nommée d'après le fichier sans son extension,
    précédée des emojis des lignes de catégorie : « china.txt » contenant « 0🇨🇳china (5) » -> « 🇨🇳china ».
    """
    cartes, symboles = [], []
    lignes = [l.strip() for l in texte.splitlines()]
    i = 0
    while i < len(lignes):
        l = lignes[i]
        if not l:
            i += 1
            continue
        m = RE_TITRE.match(l)
        if m:
            carte = {"titre": m.group(1).strip()}
            suivante = lignes[i + 1] if i + 1 < len(lignes) else ""
            if suivante and not RE_TITRE.match(suivante):
                carte["description"] = suivante
                i += 1
            cartes.append(carte)
        else:
            e = emojis(l)
            if e and e not in symboles:
                symboles.append(e)
        i += 1
    return [{"nom": nom_depuis_fichier(chemin, symboles), "cartes": cartes}] if cartes else []


def charger_collection(chemin):
    texte = Path(chemin).read_text(encoding="utf-8")
    try:
        data = json.loads(texte)
    except json.JSONDecodeError:
        return charger_extraction_album(texte, chemin)
    albums = []
    for a in data.get("albums", []):
        cartes = []
        for c in a.get("cartes", []):
            cartes.append({"titre": c} if isinstance(c, str) else dict(c))
        albums.append({"nom": nom_album(a["nom"]), "cartes": cartes})
    return albums


def charger_cache(cache_path):
    """Cache Wikipédia. Un fichier illisible est mis de côté (jamais effacé) et on repart d'un cache vide."""
    if not cache_path.exists():
        return {}
    try:
        return json.loads(cache_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        cote = cache_path.with_name(cache_path.stem + time.strftime(".illisible-%Y%m%d-%H%M%S") + cache_path.suffix)
        shutil.copy2(cache_path, cote)
        print(f"! {cache_path.name} illisible ({e}) : copie gardée dans {cote.name}, cache repris à zéro",
              file=sys.stderr)
        return {}


def sauver_cache(cache_path, cache):
    """Écriture sûre : un fichier temporaire remplace le cache d'un coup (pas de cache à moitié écrit)."""
    tmp = cache_path.with_name(cache_path.name + ".tmp")
    tmp.write_text(json.dumps(cache, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(cache_path)


def charger_suivi(chemin):
    """Dates d'ajout des cartes et journal (wiki_historique.json). Fichier illisible : mis de côté, repris à zéro."""
    vide = {"collections": {}, "journal": []}
    if not chemin.exists():
        return vide
    try:
        suivi = json.loads(chemin.read_text(encoding="utf-8"))
        suivi.setdefault("collections", {})
        suivi.setdefault("journal", [])
        return suivi
    except (json.JSONDecodeError, UnicodeDecodeError, AttributeError) as e:
        cote = chemin.with_name(chemin.stem + time.strftime(".illisible-%Y%m%d-%H%M%S") + chemin.suffix)
        shutil.copy2(chemin, cote)
        print(f"! {chemin.name} illisible ({e}) : copie gardée dans {cote.name}, suivi repris à zéro",
              file=sys.stderr)
        return vide


def sauver_suivi(chemin, suivi):
    """Même écriture sûre que sauver_cache."""
    tmp = chemin.with_name(chemin.name + ".tmp")
    tmp.write_text(json.dumps(suivi, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(chemin)


def date_fr(iso):
    """2026-11-08 -> 08/11/2026."""
    a, m, j = iso.split("-")
    return f"{j}/{m}/{a}"


def suivre_collection(suivi, slug, nom, toutes, aujourdhui):
    """
    Compare les cartes de la page à l'état gardé dans suivi["collections"][slug].
    Renvoie (date de dernière mise à jour, événement ou None).
    Un événement n'est créé que si une carte est ajoutée, retirée ou modifiée.
    Premier passage (collection jamais suivie) : l'état est noté sans événement, date d'ajout inconnue.
    """
    empreintes = {e["cle"]: hashlib.md5(e["carte"].encode("utf-8")).hexdigest() for e in toutes}
    ancien = suivi["collections"].get(slug)
    if ancien is None:
        suivi["collections"][slug] = {"maj": aujourdhui,
                                      "cartes": {c: {"ajoutee": None, "h": h} for c, h in empreintes.items()}}
        return aujourdhui, None
    avant = ancien["cartes"]
    ajoutees = [c for c in empreintes if c not in avant]
    retirees = [c for c in avant if c not in empreintes]
    modifiees = [c for c in empreintes if c in avant and avant[c]["h"] != empreintes[c]]
    if not (ajoutees or retirees or modifiees):
        return ancien["maj"], None
    cartes = {}
    for c, h in empreintes.items():
        if c in ajoutees:
            cartes[c] = {"ajoutee": aujourdhui, "h": h}
        else:
            cartes[c] = {"ajoutee": avant[c]["ajoutee"], "h": h}
    suivi["collections"][slug] = {"maj": aujourdhui, "cartes": cartes}
    evenement = {"date": aujourdhui, "collection": nom, "ajoutees": ajoutees,
                 "retirees": retirees, "modifiees": len(modifiees)}
    return aujourdhui, evenement


def _liste_titres(titres):
    """Trois titres au plus, puis le nombre restant."""
    txt = ", ".join(html.escape(t) for t in titres[:3])
    return txt + (f" … (+{len(titres) - 3})" if len(titres) > 3 else "")


def ligne_journal(evt):
    parties = []
    if evt["ajoutees"]:
        parties.append(f"{len(evt['ajoutees'])} ajoutée(s) : {_liste_titres(evt['ajoutees'])}")
    if evt["retirees"]:
        parties.append(f"{len(evt['retirees'])} retirée(s) : {_liste_titres(evt['retirees'])}")
    if evt["modifiees"]:
        parties.append(f"{evt['modifiees']} modifiée(s)")
    return f"- **{date_fr(evt['date'])}** · {html.escape(evt['collection'])} — " + " ; ".join(parties)


def mettre_a_jour_journal(index_path, evenements):
    """Bloc « Dernières modifications » de index.md : réécrit entre ses repères, ajouté en fin de page sinon."""
    if not evenements or not index_path.exists():
        return
    bloc = "\n".join([DEBUT_JOURNAL, "## Dernières modifications", ""]
                     + [ligne_journal(e) for e in evenements] + [FIN_JOURNAL])
    texte = index_path.read_text(encoding="utf-8")
    i, j = texte.find(DEBUT_JOURNAL), texte.find(FIN_JOURNAL)
    if i != -1 and j > i:
        texte = texte[:i] + bloc + texte[j + len(FIN_JOURNAL):]
    else:
        texte = texte.rstrip() + "\n\n" + bloc + "\n"
    index_path.write_text(texte, encoding="utf-8")


def trouver_docs(sortie):
    """Dossier docs/ de Zensical, situé au-dessus de --sortie."""
    parts = sortie.resolve().parts
    if "docs" not in parts:
        sys.exit(f"Le dossier d'enregistrement doit être dans le docs/ de Zensical (reçu : {sortie}). "
                 f'Règle CONFIG["dossier"] dans le script.')
    i = len(parts) - 1 - parts[::-1].index("docs")
    return Path(*parts[:i + 1])


def telecharger_image(nom, dossier_img, prefixe):
    """Télécharge l'image (largeur configurée) dans dossier_img ; renvoie le chemin relatif depuis la page.
    Si le réseau est coupé ou si Wikimedia refuse, le lien distant est utilisé (relance plus tard)."""
    global IMAGES_TELECHARGEES, RESEAU_COUPE
    nom = nom_original(nom)
    ext = (Path(nom).suffix or ".jpg").lower()
    # Wikimedia renvoie un PNG pour un SVG demandé en largeur : l'extension doit correspondre aux octets
    if ext == ".svg":
        ext = ".png"
    # nom unique : deux images qui ne diffèrent que par accents ou ponctuation ne s'écrasent pas
    fichier = slugify(Path(nom).stem)[:60] + "-" + hashlib.md5(nom.encode("utf-8")).hexdigest()[:8] + ext
    dest = dossier_img / fichier
    if not dest.exists():
        if RESEAU_COUPE:
            return url_image(nom)
        try:
            octets, site = octets_image(nom)
            dest.write_bytes(octets)
            IMAGES_TELECHARGEES += 1
            print(f"  [image {IMAGES_TELECHARGEES}] {nom}" + (f" (depuis {site})" if site != CONFIG["commons"] else ""))
        except Abandon as e:
            RESEAU_COUPE = str(e)
            print(f"  ! téléchargement des images arrêté : {e} (liens distants utilisés)", file=sys.stderr)
            return url_image(nom)
        except Exception as e:
            print(f"  ! image {nom} : {e} (lien distant utilisé)", file=sys.stderr)
            return url_image(nom)
    return f"{prefixe}{fichier}"


RE_TUILE = re.compile(r'<a class="wp-album" href="([^"]+)/">.*?</a>', re.S)


def fusionner_tuiles(index_path, nouvelles):
    """
    Tuiles de la page d'accueil : celles déjà présentes (autres collections) sont conservées,
    celles des albums de ce lancement sont mises à jour sur place, les nouvelles s'ajoutent à la suite.
    nouvelles : liste de (slug, html).
    """
    existantes = []
    if index_path.exists():
        existantes = [(m.group(1), m.group(0))
                      for m in RE_TUILE.finditer(index_path.read_text(encoding="utf-8"))]
    maj = dict(nouvelles)
    resultat = [maj.get(slug, h) for slug, h in existantes]
    vus = {slug for slug, _ in existantes}
    resultat += [h for slug, h in nouvelles if slug not in vus]
    return resultat


RE_FICHE = re.compile(r'^<div class="wp-fiche" id="([^"]+)".*$', re.M)
RE_TITRE_CATEGORIE = re.compile(r'<summary class="wp-categorie-titre">(.*?)</summary>')


def bloc_genere(texte):
    """Partie générée d'une page (entre les repères), ou toute la page pour une ancienne page sans repères."""
    i, j = texte.find(DEBUT_REPERE), texte.find(FIN_BLOC)
    return texte[i:j] if i != -1 and j > i else texte


def lire_cartes_existantes(page_path):
    """
    Cartes déjà présentes sur la page d'album, rangées par catégorie, dans l'ordre de la page :
    liste de (nom de la catégorie, ou None hors catégorie, [dict {cle, id, carte, fiche}]).
    cle = titre de l'article (le <h2> de la carte) ; id = identifiant de la fiche (popovertarget).
    Lit les pages à catégories repliables comme les anciennes pages à une seule grille.
    """
    if not page_path.exists():
        return []
    texte = bloc_genere(page_path.read_text(encoding="utf-8"))
    fiches = {f.group(1): f.group(0) for f in RE_FICHE.finditer(texte)}
    sections = []
    categorie = None      # catégorie en cours (None = hors catégorie)
    dans_grille = False
    for ligne in texte.split("\n"):
        s = ligne.strip()
        m = RE_TITRE_CATEGORIE.search(s)
        if m:
            categorie = RE_COMPTE.sub("", nettoyer_html(m.group(1))).strip()
            continue
        if s == "</details>":
            categorie, dans_grille = None, False
            continue
        if s.startswith('<div class="wp-grille"'):
            dans_grille = True
            continue
        if not dans_grille or not s:
            continue
        if s == "</div>":
            dans_grille = False
            continue
        t = re.search(r"<h2>(.*?)</h2>", ligne)
        i = re.search(r'popovertarget="([^"]+)"', ligne)
        idf = i.group(1) if i else ""
        if not sections or sections[-1][0] != categorie:
            sections.append((categorie, []))
        sections[-1][1].append({"cle": html.unescape(t.group(1)) if t else ligne, "id": idf,
                                "carte": ligne, "fiche": fiches.get(idf, "")})
    return sections


def bloc_categorie(nom, entrees):
    """Catégorie repliable : un clic sur son titre déplie / replie ses cartes (sans JavaScript)."""
    ouvert = " open" if CONFIG["categories_ouvertes"] else ""
    return (f'<details class="wp-categorie"{ouvert}>\n'
            f'<summary class="wp-categorie-titre">{html.escape(nom)} ({len(entrees)})</summary>\n'
            '<div class="wp-grille">\n' + "\n".join(e["carte"] for e in entrees) + "\n</div>\n</details>")


def assembler_page(ancienne, nom, genere):
    """Page de collection : le bloc généré est remplacé, ce qui est écrit autour est gardé.
    Une page sans repères (créée par une ancienne version) est réécrite entièrement, comme avant."""
    bloc = f"{DEBUT_BLOC}\n\n{genere.strip()}\n\n{FIN_BLOC}"
    if ancienne:
        i, j = ancienne.find(DEBUT_REPERE), ancienne.find(FIN_BLOC)
        if i != -1 and j > i:
            return ancienne[:i] + bloc + ancienne[j + len(FIN_BLOC):]
    return f"# {nom}\n\n{bloc}\n"


RE_BLOC_ALBUMS = re.compile(r'(<div class="wp-albums">\n)(.*?)(\n</div>)', re.S)


def mettre_a_jour_index(index_path, nouvelles):
    """
    Crée index.md, ou le modifie s'il existe : seul le bloc des tuiles est réécrit (collections déjà
    présentes conservées, celles de ce lancement mises à jour ou ajoutées), le reste de la page
    (texte ajouté à la main, par exemple) n'est pas touché. Le titre est toujours CONFIG["titre_page"].
    """
    titre = f"# {CONFIG['titre_page']}"
    toutes = fusionner_tuiles(index_path, nouvelles)
    bloc = "\n".join(toutes)
    fm = ""  # front matter (title, description…) : gardé tel quel, en tête de page
    if index_path.exists():
        texte = index_path.read_text(encoding="utf-8")
        m_fm = re.match(r"---\n.*?\n---\n", texte, re.S)
        if m_fm:
            fm, texte = m_fm.group(0), texte[m_fm.end():]
        if RE_BLOC_ALBUMS.search(texte):
            texte = RE_BLOC_ALBUMS.sub(lambda m: m.group(1) + bloc + m.group(3), texte, count=1)
        else:  # pas de bloc de tuiles : on l'ajoute à la fin de la page
            texte = texte.rstrip() + f'\n\n<div class="wp-albums">\n{bloc}\n</div>\n'
        # titre fixe : remplace le premier titre, ou l'ajoute en tête
        if re.match(r"\s*# ", texte):
            texte = re.sub(r"^\s*# .*$", lambda m: titre, texte, count=1, flags=re.M)
        else:
            texte = titre + "\n\n" + texte.lstrip()
    else:
        texte = f'{titre}\n\n<div class="wp-albums">\n{bloc}\n</div>\n\n{PIED}'
    index_path.write_text(fm + texte, encoding="utf-8")


def tronquer(texte, n):
    if not n or len(texte) <= n:
        return texte
    coupe = texte[:n].rsplit(" ", 1)[0]
    return coupe + "…"


def html_carte(carte_col, w, src_img, idf):
    """Vignette de la carte. Clic sur l'image ou le « + » : ouvre la fiche #idf (voir fiche_carte)."""
    e = html.escape
    titre = carte_col["titre"]
    if w.get("introuvable"):
        return (f'<div class="wp-carte wp-introuvable"><div class="wp-corps">'
                f'<h2>{e(titre)}</h2><p class="wp-desc">{e(carte_col.get("description") or "Article introuvable sur Wikipédia")}</p>'
                f'</div></div>')

    extra = ""
    if carte_col.get("rarete"):
        extra = f'<span class="wp-rarete">{e(str(carte_col["rarete"]))}</span>'

    if w.get("image"):
        img_html = (f'<figure class="wp-image"><button type="button" class="wp-ouvrir" popovertarget="{idf}">'
                    f'<img src="{e(src_img)}" alt="{e(w["titre_article"])}" loading="lazy"></button></figure>')
    else:
        img_html = f'<figure class="wp-image wp-sans-image"><button type="button" class="wp-ouvrir" popovertarget="{idf}">?</button></figure>'

    return (f'<div class="wp-carte">{extra}{img_html}<div class="wp-corps">'
            f'<h2>{e(w["titre_article"])}</h2>'
            f'<p class="wp-desc">{e(w.get("description") or carte_col.get("description", ""))}</p>'
            f'<button type="button" class="wp-plus" popovertarget="{idf}" title="Voir la fiche">+</button>'
            f'</div></div>')


def fiche_carte(carte_col, w, src_img, idf):
    """Fiche plein écran de la carte : photo à gauche, texte et licence à droite, lien vers Wikipédia."""
    if w.get("introuvable"):
        return ""
    e = html.escape
    fig = ""
    credit = ""
    if w.get("image"):
        fig = f'<figure class="wp-fiche-image"><img src="{e(src_img)}" alt="{e(w["titre_article"])}"></figure>'
        lic = w["image"].get("licence")
        if lic:
            credit = (f'<p class="wp-licence">Image : <a href="{e(lic["page_fichier"])}">{e(lic["auteur"])}</a>'
                      f' — {e(lic["licence"])} (Wikimedia Commons)</p>')
    resume = w.get("resume", "")
    return (f'<div class="wp-fiche" id="{idf}" popover>'
            f'<div class="wp-panneau"><button type="button" class="wp-fermer" popovertarget="{idf}" '
            f'popovertargetaction="hide" aria-label="Fermer">×</button>'
            f'{fig}<div class="wp-texte">'
            f'<h2>{e(w["titre_article"])}</h2>'
            f'<p class="wp-desc">{e(w.get("description") or carte_col.get("description", ""))}</p>'
            f'<p>{e(resume)}</p>'
            f'{credit}'
            f'<p><a class="wp-wiki" href="{e(w.get("url", ""))}">Voir sur Wikipédia →</a></p>'
            f'</div></div></div>')


PIED = ("\n\n<p class=\"wp-mentions\">Textes : Wikipédia et Wikidata, sous licence "
        "<a href=\"https://creativecommons.org/licenses/by-sa/4.0/deed.fr\">CC BY-SA 4.0</a>. "
        "Images : Wikimedia Commons, auteur et licence indiqués sous chaque image.</p>\n")


def interactif():
    """Questions seulement dans un terminal (aucune question, et rien de supprimé, en tâche planifiée)."""
    return sys.stdin.isatty()


def choisir_retraits(page_nom, liste):
    """liste = [(clé, nom, nb_page, nb_fichier)]. Renvoie l'ensemble des clés de catégories à retirer."""
    if not liste:
        return set()
    print(f"\nCatégories de {page_nom} :")
    for n, (_, nom, nb_page, nb_fichier) in enumerate(liste, 1):
        infos = []
        if nb_page is not None:
            infos.append(f"{nb_page} carte(s) sur la page")
        if nb_fichier is not None:
            infos.append(f"{nb_fichier} entrée(s) dans le fichier")
        print(f"  {n:2}. {nom}  ({', '.join(infos)})")
    if not interactif():
        print("(pas de terminal : aucune catégorie retirée)")
        return set()
    rep = input("\nNuméros des catégories à retirer (ex. 1,3), Entrée pour n'en retirer aucune : ").strip()
    retire = set()
    for x in re.split(r"[,;\s]+", rep):
        if x.isdigit() and 1 <= int(x) <= len(liste):
            retire.add(liste[int(x) - 1][0])
    if retire:
        print("Retirées (titre et cartes) : " + ", ".join(nom for k, nom, _, _ in liste if k in retire))
    return retire


def confirmer_suppressions(absentes):
    """absentes = [(nom de la catégorie ou None, carte)]. True si l'utilisateur confirme la suppression."""
    if not absentes or not interactif():
        return False
    print(f"\n{len(absentes)} carte(s) sur la page mais plus dans le fichier (catégories mises à jour) :")
    for nom, e in absentes:
        print(f"  - {e['cle']}" + (f"  [{nom}]" if nom else ""))
    rep = input("\nLes supprimer ? [o/N] (Entrée = les garder) ").strip().lower()
    return rep in ("o", "oui", "y", "yes")


def preparer_page(album, sortie, cache):
    """Lit la page de l'album et pose les questions AVANT toute requête ou écriture :
    catégories à retirer, puis cartes de la page absentes du fichier. Renvoie le plan de la page."""
    page_path = sortie / f"{slugify(album['nom'])}.md"
    ancienne = page_path.read_text(encoding="utf-8") if page_path.exists() else None
    sections = lire_cartes_existantes(page_path)
    nb_page = sum(len(e) for _, e in sections)
    print(f"\nPage {page_path.name} : "
          + (f"{len({cle_categorie(n) for n, _ in sections if n})} catégorie(s), {nb_page} carte(s)"
             if ancienne is not None else "nouvelle"))

    # 1. catégories de la page puis du fichier, avec leur nombre de cartes
    page_cats, fichier_cats = {}, {}
    for nom, entrees in sections:
        if nom:
            k = cle_categorie(nom)
            page_cats[k] = (page_cats.get(k, (nom, 0))[0], page_cats.get(k, (nom, 0))[1] + len(entrees))
    for nom, cartes in album["categories"]:
        if nom:
            k = cle_categorie(nom)
            fichier_cats[k] = (nom, fichier_cats.get(k, (nom, 0))[1] + len(cartes))
    ordre = list(page_cats) + [k for k in fichier_cats if k not in page_cats]
    retirees = choisir_retraits(page_path.name, [
        (k, (fichier_cats.get(k) or page_cats[k])[0],
         page_cats[k][1] if k in page_cats else None,
         fichier_cats[k][1] if k in fichier_cats else None) for k in ordre])
    categories = [(nom, cartes) for nom, cartes in album["categories"]
                  if not (nom and cle_categorie(nom) in retirees)]

    # 2. cartes de la page absentes du fichier, dans les catégories que le fichier met à jour
    #    (les cartes hors catégorie ne sont concernées que s'il n'y a pas de catégories : une page par album)
    titres_fichier = set()
    for _, cartes in categories:
        for c in cartes:
            titres_fichier.add(cle_titre(c["titre"]))
            w = cache.get(c["titre"]) or {}
            if w.get("titre_article"):
                titres_fichier.add(cle_titre(w["titre_article"]))
    mises_a_jour = {cle_categorie(nom) for nom, _ in categories if nom}
    if not any(nom for nom, _ in album["categories"]):
        mises_a_jour.add(None)
    absentes = [(nom, e) for nom, entrees in sections for e in entrees
                if (cle_categorie(nom) if nom else None) in mises_a_jour
                and cle_titre(e["cle"]) not in titres_fichier]
    supprimer = confirmer_suppressions(absentes)
    if supprimer:
        print(f"{len(absentes)} carte(s) seront supprimée(s).")
    elif absentes:
        print(f"\n{len(absentes)} carte(s) absente(s) du fichier gardée(s).")
    return {"page_path": page_path, "ancienne": ancienne, "sections": sections, "retirees": retirees,
            "categories": categories, "a_supprimer": {id(e) for _, e in absentes} if supprimer else set()}



def main():
    global RESEAU_COUPE
    p = argparse.ArgumentParser(description="Collection wiki-pick -> pages Markdown Zensical")
    p.add_argument("entree", nargs="?", default=CONFIG["entree"],
                   help="texte d'extraction Album ou JSON (défaut : CONFIG[\"entree\"])")
    p.add_argument("--sortie", default=CONFIG["dossier"],
                   help="dossier où écrire index.md et les pages d'album (doit exister)")
    p.add_argument("--cache", default="wiki_cache.json")
    p.add_argument("--images", choices=["local", "distant"], default="local",
                   help="local = images téléchargées dans sortie/img ; distant = liens Wikimedia")
    p.add_argument("--refresh", action="store_true",
                   help="redemander à Wikipédia les cartes du fichier (le reste du cache est gardé)")
    args = p.parse_args()

    sortie = Path(args.sortie).expanduser()
    trouver_docs(sortie)                      # vérifie que le dossier est bien dans docs/
    if not Path(args.entree).exists():
        sys.exit(f"Fichier d'entrée introuvable : {args.entree}")
    sortie.mkdir(parents=True, exist_ok=True)  # créé s'il n'existe pas

    albums = charger_collection(args.entree)
    if not albums:
        sys.exit("Aucune carte trouvée dans le fichier : chaque carte est une ligne « **Titre** », "
                 "suivie de sa description.")
    print(f"Fichier {args.entree} : catégorie(s) " + ", ".join(f"« {a['nom']} »" for a in albums)
          + f", {sum(len(a['cartes']) for a in albums)} carte(s)")
    if CONFIG["collection"]:
        # une seule collection au nom choisi : toutes les cartes du fichier y sont regroupées,
        # rangées par catégorie (repliable) si CONFIG["categories"]
        if CONFIG["categories"]:
            categories = [(None if a.get("sans_categorie") else a["nom"], a["cartes"]) for a in albums]
        else:
            categories = [(None, [c for a in albums for c in a["cartes"]])]
        albums = [{"nom": CONFIG["collection"], "categories": categories}]
    else:
        # une page par album du fichier, en une seule grille
        albums = [{"nom": a["nom"], "categories": [(None, a["cartes"])]} for a in albums]
    cache_path = Path(args.cache)
    cache = charger_cache(cache_path)
    suivi_path = cache_path.with_name("wiki_historique.json")
    suivi = charger_suivi(suivi_path)
    aujourdhui = time.strftime("%Y-%m-%d")
    evenements = []

    # 0. Questions sur ce qui est déjà sur les pages, avant d'ajouter quoi que ce soit
    plans = [preparer_page(album, sortie, cache) for album in albums]

    # 1. Récupération Wikipédia (seulement ce qui manque au cache, catégories retirées exclues)
    titres = sorted({c["titre"] for plan in plans for _, cartes in plan["categories"] for c in cartes})
    print()
    # à (re)demander : jamais vues, vues sans image (l'image a pu être ajoutée depuis), ou notées
    # « introuvable » par une ancienne version (peut-être à cause d'un refus 429 et non d'un 404)
    a_faire = [t for t in titres if args.refresh or t not in cache
               or (cache[t].get("introuvable") and "http" not in cache[t])
               or (not cache[t].get("introuvable") and not cache[t].get("image"))]
    # images dont la licence n'a pas pu être lue la dernière fois
    licences = [t for t in titres if t not in a_faire and (cache[t].get("image") or {}).get("fichier")
                and cache[t]["image"].get("licence") is None]
    print(f"{len(titres)} cartes, {len(a_faire)} à récupérer sur Wikipédia"
          + (f", {len(licences)} licence(s) à compléter" if licences else ""))
    try:
        for i, t in enumerate(a_faire, 1):
            debut, avant = time.monotonic(), REQUETES
            try:
                r = recuperer_carte(t)
            except Abandon as e:
                RESEAU_COUPE = str(e)
                break
            if r is not None:
                cache[t] = r
            print(f"  [{i}/{len(a_faire)}] {t} : {etat_carte(r)} "
                  f"({REQUETES - avant} requête(s), {time.monotonic() - debut:.1f} s)")
            if i % 20 == 0:  # sauvegarde régulière
                sauver_cache(cache_path, cache)
        for i, t in enumerate(licences if not RESEAU_COUPE else [], 1):
            try:
                lic = infos_licence(cache[t]["image"]["fichier"])
            except Abandon as e:
                RESEAU_COUPE = str(e)
                break
            if lic is not None:
                cache[t]["image"]["licence"] = lic
            print(f"  [licence {i}/{len(licences)}] {t} : {'complétée' if lic else 'toujours introuvable'}")
    finally:
        sauver_cache(cache_path, cache)   # même après Ctrl+C ou un arrêt : rien de ce qui a été trouvé n'est perdu
    if RESEAU_COUPE:
        print(f"\n! Requêtes arrêtées : {RESEAU_COUPE}.\n"
              f"  Le cache garde ce qui a été trouvé ; relance plus tard pour la suite.\n")

    sans_image = [t for t in titres if t in cache and not cache[t].get("image")]
    if sans_image:
        print(f"{len(sans_image)} carte(s) sans image (ni article ni Wikidata) : "
              + ", ".join(sans_image[:10]) + (" …" if len(sans_image) > 10 else ""))

    # 2. Génération des pages Markdown (images chargées depuis Wikimedia)
    docs = trouver_docs(sortie)
    dossier_img = docs / CONFIG["dossier_images"]
    racine = "/" + CONFIG["dossier_images"] + "/"  # chemin absolu depuis la racine du site

    def source(w, prefixe):
        if not w.get("image"):
            return ""
        if args.images == "distant":
            return url_image(w["image"]["fichier"])
        dossier_img.mkdir(parents=True, exist_ok=True)  # dossier de Zensical, seulement en mode local
        return telecharger_image(w["image"]["fichier"], dossier_img, racine)

    tuiles = []
    total = 0
    en_attente = []
    for album, plan in zip(albums, plans):
        slug = slugify(album["nom"])
        page_path = plan["page_path"]
        ancienne = plan["ancienne"]

        # les cartes déjà sur le site restent (sauf suppression confirmée), même si elles ne sont plus
        # dans le fichier d'entrée, et gardent leur catégorie ; les catégories de la page absentes du
        # fichier restent aussi (sauf si elles ont été retirées au menu)
        ordre, noms, contenu = [], {}, {}

        def categorie(nom):
            k = cle_categorie(nom) if nom else None
            if k not in contenu:
                contenu[k] = []
                ordre.append(k)
            if nom:
                noms[k] = nom          # le nom du fichier remplace celui de la page (emoji changé…)
            return k

        for nom, entrees in plan["sections"]:
            contenu[categorie(nom)].extend(entrees)
        existantes = [e for k in ordre for e in contenu[k]]
        par_cle = {e["cle"]: (e, k) for k in ordre for e in contenu[k]}
        ids_pris = {e["id"] for e in existantes if e["id"]}
        compteur = 0

        def nouvel_id():
            nonlocal compteur
            while True:
                compteur += 1
                idf = f"c-{slug}-{compteur}"
                if idf not in ids_pris:
                    ids_pris.add(idf)
                    return idf

        vus = set()
        reclamees = set()         # cartes déjà sur la page que le fichier contient (jamais supprimées)
        creees = maj = rangees = doublons = 0
        for nom_cat, cartes in plan["categories"]:
            k = categorie(nom_cat)
            for c in cartes:
                w = cache.get(c["titre"])
                if w is None:
                    # pas encore récupérée (réseau coupé, refus 429) : pas de fausse carte « introuvable »,
                    # elle sera ajoutée au prochain lancement (si elle est déjà sur la page, elle y reste)
                    if c["titre"] in par_cle:
                        reclamees.add(id(par_cle[c["titre"]][0]))
                    else:
                        en_attente.append(c["titre"])
                    continue
                cle = c["titre"] if w.get("introuvable") else w["titre_article"]
                if cle in vus:            # même carte dans deux catégories : gardée dans la première
                    doublons += 1
                    continue
                vus.add(cle)
                e, k_actuelle = par_cle.get(cle, (None, None))
                if e is None:             # nouvelle carte, ajoutée à la suite de sa catégorie
                    idf = nouvel_id()
                    src = source(w, "../")
                    e = {"cle": cle, "id": idf, "carte": html_carte(c, w, src, idf),
                         "fiche": fiche_carte(c, w, src, idf)}
                    contenu[k].append(e)
                    par_cle[cle] = (e, k)
                    creees += 1
                    continue
                reclamees.add(id(e))
                if not w.get("introuvable"):  # ne pas remplacer une carte complète par une carte « introuvable »
                    idf = e["id"] or nouvel_id()
                    # pages d'album : sortie/<album>.md -> URL sortie/<album>/, donc "../img/"
                    src = source(w, "../")
                    e["carte"], e["fiche"], e["id"] = html_carte(c, w, src, idf), fiche_carte(c, w, src, idf), idf
                    maj += 1
                if (k is not None and k != k_actuelle) or (k is None and k_actuelle in plan["retirees"]):
                    # déjà sur la page : rangée dans sa catégorie du fichier
                    contenu[k_actuelle] = [x for x in contenu[k_actuelle] if x is not e]
                    contenu[k].append(e)
                    par_cle[cle] = (e, k)
                    rangees += 1

        # catégories retirées au menu : leurs cartes partent (sauf celles que le fichier range ailleurs)
        retirees_cartes = 0
        for k in plan["retirees"]:
            retirees_cartes += len(contenu.get(k, []))
            contenu[k] = []
        # cartes absentes du fichier, suppression confirmée (une carte que le fichier contient
        # sous un autre titre, une redirection par exemple, est gardée)
        supprimees = 0
        if plan["a_supprimer"]:
            for k in contenu:
                garde = [e for e in contenu[k] if id(e) not in plan["a_supprimer"] or id(e) in reclamees]
                supprimees += len(contenu[k]) - len(garde)
                contenu[k] = garde

        avec_categorie = [k for k in ordre if k is not None and contenu[k]]
        hors = contenu.get(None, [])
        toutes = [e for k in avec_categorie for e in contenu[k]] + hors
        total += len(toutes)
        blocs = [bloc_categorie(noms[k], contenu[k]) for k in avec_categorie]
        if hors:
            blocs.append('<div class="wp-grille">\n' + "\n".join(e["carte"] for e in hors) + "\n</div>")

        # clé du suivi = chemin depuis docs/ (deux pages peuvent porter le même nom dans deux dossiers)
        cle_page = page_path.resolve().relative_to(trouver_docs(sortie)).as_posix()
        date_maj, evt = suivre_collection(suivi, cle_page, album["nom"], toutes, aujourdhui)
        if evt:
            evenements.append(evt)
        genere = (f"{len(toutes)} cartes · [← retour à la collection](index.md)"
                  f" · mise à jour le {date_fr(date_maj)}\n\n"
                  + "\n\n".join(blocs) + "\n\n"
                  + "\n".join(e["fiche"] for e in toutes if e["fiche"]) + "\n" + PIED)
        page_path.write_text(assembler_page(ancienne, album["nom"], genere), encoding="utf-8")

        restantes = {id(e) for e in toutes}
        gardees = sum(1 for e in existantes if id(e) in restantes and id(e) not in reclamees)
        print(f"\n{page_path.name} : {len(toutes)} cartes (avant : {len(existantes)})")
        print(f"  créées                        : {creees}")
        print(f"  mises à jour                  : {maj}")
        if avec_categorie:
            print(f"  rangées dans leur catégorie   : {rangees}")
        print(f"  gardées (absentes du fichier) : {gardees}")
        if plan["retirees"]:
            print(f"  retirées avec leur catégorie  : {retirees_cartes}")
        if supprimees:
            print(f"  supprimées (confirmé)         : {supprimees}")
        if doublons:
            print(f"  doublons ignorés              : {doublons}")
        if avec_categorie:
            print(f"  catégories repliables         : {len(avec_categorie)}"
                  f" ({'dépliées' if CONFIG['categories_ouvertes'] else 'repliées'} à l'ouverture)")
            for k in avec_categorie:
                print(f"    - {noms[k]} ({len(contenu[k])})")
        if hors and avec_categorie:
            print(f"  hors catégorie (à la fin)     : {len(hors)}")

        # couverture de l'accueil : première image des cartes de la page
        couverture = ""
        for e in toutes:
            m = re.search(r'<img src="([^"]+)"', e["carte"])
            if m:
                couverture = html.unescape(m.group(1))
                break
        img = f'<img src="{html.escape(couverture)}" alt="" loading="lazy">' if couverture else ""
        tuiles.append((slug, f'<a class="wp-album" href="{slug}/">{img}'
                             f'<span>{html.escape(album["nom"])} ({len(toutes)})</span></a>'))

    # suivi des dates et journal : sauvegardés après les pages, avant la page d'accueil
    if evenements:
        suivi["journal"] = (evenements + suivi["journal"])[:JOURNAL_GARDES]
    sauver_suivi(suivi_path, suivi)

    # page d'accueil : si index.md existe, il est modifié sur place (seul le bloc des tuiles change)
    mettre_a_jour_index(sortie / "index.md", tuiles)
    mettre_a_jour_journal(sortie / "index.md", suivi["journal"][:JOURNAL_AFFICHES])

    print(f"\nPages Markdown écrites dans {sortie} ({len(albums)} albums, {total} cartes)")
    print(f"Requêtes Wikimedia : {REQUETES} · images téléchargées : {IMAGES_TELECHARGEES} · durée : {duree()}")
    if en_attente:
        print(f"! {len(en_attente)} carte(s) pas encore récupérée(s), ajoutée(s) au prochain lancement : "
              + ", ".join(en_attente[:10]) + (" …" if len(en_attente) > 10 else ""))


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nInterrompu. Le cache est sauvegardé ; relance le script pour terminer.")
        sys.exit(130)
