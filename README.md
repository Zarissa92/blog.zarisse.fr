# zarisse.fr

Site du blog de Zaza, généré avec [Zensical](https://zensical.org) (configuration : `zensical.toml`).
Les sources sont dans `docs/`, le site généré dans `site/` (ne pas modifier à la main).

## Structure

| Chemin | Rôle |
|---|---|
| `docs/` | Pages sources (Markdown) et ressources (`docs/assets/`) |
| `overrides/` | Gabarits du thème (en-tête, RSS, page de profil) |
| `zensical.toml` | Configuration du site, du thème et du plugin RSS |
| `build.py` | Lance tout le build (voir ci-dessous), et l'aperçu local avec `--serve` |
| `billets_index.py` | Liste des billets dans `docs/Billets2Blog/index.md` |
| `post_build_dates.py` | Dates des flux RSS/JSON, d'après les fichiers sources |
| `post_build_og_images.py` | Crée une image de partage 1200×630 par page (`site/assets/og/`), seulement si elle a changé |
| `empreintes.py` | Hachages des images de prévisualisation (`.cache/empreintes.json`) qui permettent de ne refaire que les images modifiées |
| `post_build_og.py` | Balises Open Graph / Twitter des pages |
| `wikipick_site.py` | Génère les pages de collections « wiki-pick » à partir de fiches Wikipédia |
| `corriger_dates_wikipick.py` | Correctif ponctuel : remet les dates wikipick à aujourd'hui (peut être supprimé) |
| `dater_pages.py` | Date les pages dans leur front matter à chaque build : ajoute `date` (création et modification) aux pages qui n'en ont pas, et avance la date de modification des pages modifiées |
| `wiki_cache.json` | Cache des fiches Wikipédia (généré par wikipick) |
| `wiki_historique.json` | Dates d'ajout des cartes et journal des modifications (généré par wikipick) |
| `venv_blog/` | Environnement Python contenant Zensical |

## Build

```bash
python3 build.py            # ne refait que les images de prévisualisation modifiées
python3 build.py --forcer   # refait toutes les images de prévisualisation
python3 build.py --serve    # build complet, puis aperçu sur http://localhost:8000 (Ctrl+C pour arrêter)
```

`build.py` est le point d'entrée unique : il lance les étapes dans l'ordre ci-dessous. Il s'arrête dès qu'une étape échoue, avec un code de sortie non nul. Il écrit dans `site/`, et dans `docs/` uniquement pour les deux premières étapes (front matter des dates et liste des billets ; le texte des pages n'est jamais modifié).

1. **Dates des pages** : `dater_pages.py` ajoute `date` (création et modification) au front matter des pages qui n'en ont pas encore. Sur une page déjà datée, la date de création ne change pas ; la date de modification avance quand le fichier a été modifié depuis la date notée.
2. **Liste des billets** : `billets_index.py` réécrit la liste entre les repères `<!-- billets:debut -->` et `<!-- billets:fin -->` de `docs/Billets2Blog/index.md` (billet le plus récent en haut). Le build s'arrête si les repères sont absents.
3. **Build Zensical** : `venv_blog/bin/zensical build`, qui écrit `site/`. Si Zensical échoue, le script s'arrête avec le même code de sortie.
4. **Dates des flux** : `post_build_dates.py` (voir plus bas). Elle passe avant la vérification pour que celle-ci contrôle le résultat final.
5. **Flux RSS** : vérifie que, dans `site/`, la feuille `rss.xsl` existe, que `feed_rss_created.xml` et `feed_rss_updated.xml` existent, qu'ils sont du XML valide avec un élément `<channel>`, et qu'ils contiennent au moins un article. Ces deux flux sont ceux référencés par `overrides/main.html` et `overrides/partials/header.html`.
6. **Images de partage** : `post_build_og_images.py` crée, pour chaque page, une image 1200×630 avec son titre et sa description, dans `site/assets/og/`. Les pages qui ont un `og_image` dans leur front matter gardent leur image. Une image n'est redessinée que si le titre, la description, l'avatar ou le script ont changé ; sinon sa copie de `.cache/og/` est recopiée (Zensical vide `site/` à chaque build).
7. **Balises Open Graph** : `post_build_og.py` (voir plus bas). Il utilise l'image de la page, ou l'image générée à l'étape précédente.

Les messages `✓` et `✗` s'affichent à chaque étape. Le message final « Site prêt dans … » indique que tout s'est bien passé.

Pour publier, il suffit de déployer le dossier `site/`.

### Aperçu local

Utilise `python3 build.py --serve` : il fait le build complet puis sert `site/` tel qu'il sera déployé (une page absente affiche le `404.html` du site). Il ne se met pas à jour tout seul : relance-le après une modification.

**N'utilise pas `zensical serve` (ni `zensical build`) avant de déployer.** Ils réécrivent `site/` sans les étapes post-build : les dates des flux redeviennent la date du build, et les images et balises de partage disparaissent. Si tu l'as fait, relance `python3 build.py` avant de déployer.

### Dépendances

- Python 3 (stdlib uniquement pour `post_build_dates.py`, `dater_pages.py` et `wikipick_site.py`)
- PyYAML pour `billets_index.py`, `post_build_og.py` et `post_build_og_images.py` (`import yaml`), donc aussi pour `build.py` qui les importe
- Pillow pour `post_build_og_images.py` (`venv_blog/bin/python -m pip install pillow`) ; la police Fira Sans est utilisée si elle est installée, sinon DejaVu ou la police par défaut de Pillow
- La commande `stat` (GNU coreutils) pour `post_build_dates.py`
- Zensical dans `venv_blog/`

## Post-build

### `post_build_dates.py` : dates des flux

Les flux produits par Zensical datent tous les articles de la date du build. Ce script les remplace par les dates des fichiers sources.

- Le fichier source d'un article est retrouvé à partir de son lien : `https://zarisse.fr/<chemin>/` correspond à `docs/<chemin>.md` ou `docs/<chemin>/index.md`.
- **Flux « créés »** (`feed_rss_created.xml`, `feed_json_created.json`) : date de **création** du fichier, lue avec `stat -c %W`.
- **Flux « mis à jour »** (`feed_rss_updated.xml`, `feed_json_updated.json`) : date de **modification**.
- Dans le JSON, `date_published` contient la création et `date_modified` la modification, dans les deux flux.
- Si la date de création n'est pas disponible, la date de modification est utilisée. Un article sans fichier source garde la date du build.
- Les articles sont triés du plus récent au plus ancien, et la date de la chaîne suit l'article le plus récent.
- Le XML est modifié en texte brut, pour conserver l'instruction `xml-stylesheet` (feuille `rss.xsl`).

**Limite** : une date de création change si le fichier est recréé (certains éditeurs font une sauvegarde en créant un nouveau fichier, une synchronisation ou une copie peuvent aussi le faire). Pour garder la date d'origine, modifie les fichiers sur place.

### `post_build_og.py` : balises Open Graph

Ajoute les balises `og:*` et `twitter:*` aux pages HTML de `site/`. Les valeurs se règlent dans le front matter de chaque page source :

```yaml
---
description: "Texte de la meta description, repris pour og:description."
og_description: "Texte de partage, s'il diffère de la description (optionnel)."
og_image: "assets/img/image.jpg"   # optionnel, relatif à la racine du site
---
```

Par défaut, l'image est `assets/partage.jpg` (1200 × 630). Le script ne traite que `site/` et est idempotent : une page déjà traitée est ignorée.

## wikipick : pages de collections

`wikipick_site.py` transforme une liste de cartes en pages Zensical : une page par collection, avec les images et les descriptions tirées de Wikipédia et Wikidata, et l'attribution des images (auteur, licence) sous chaque image.

### Entrée

Un fichier texte (extraction du script Album) ou un fichier JSON :

```json
{
  "albums": [
    {"nom": "Châteaux de France",
     "cartes": [{"titre": "Château de Chambord"}, {"titre": "Château de Blois", "rarete": "rare"}]}
  ]
}
```

Les cartes peuvent aussi être de simples chaînes : `"cartes": ["Château de Chambord", ...]`.

Dans un fichier texte, chaque fichier de catégorie devient une catégorie repliable. Son nom est le nom du fichier, précédé des emojis de ses lignes de catégorie. Pour renommer une catégorie, renomme le fichier.

### Réglages

Le bloc `CONFIG` en haut de `wikipick_site.py` contient les réglages courants :

| Clé | Rôle |
|---|---|
| `dossier` | Dossier de sortie, à l'intérieur de `docs/` |
| `collection` | Nom de la collection. Vide = une page par album |
| `entree` | Fichier d'entrée par défaut |
| `categories` | Ranger les cartes par catégorie |
| `categories_ouvertes` | Catégories dépliées à l'ouverture (sinon repliées) |
| `largeur_image` | Largeur des images, en px (330, 500, 960…) |
| `longueur_resume` | Longueur maximale du résumé (0 = complet) |
| `titre_page` | Titre de la page d'accueil de la section |
| `dossier_images` | Dossier des images téléchargées, dans `docs/` |

Les réglages avancés (API, User-Agent, pauses entre requêtes) sont juste en dessous.

### Utilisation

```bash
python3 wikipick_site.py                       # réglages de CONFIG
python3 wikipick_site.py Queens.txt            # autre fichier d'entrée
python3 wikipick_site.py --refresh             # redemande les fiches du fichier à Wikipédia
python3 wikipick_site.py --images distant      # liens Wikimedia au lieu de copies locales
```

Options : `--sortie` (dossier de sortie), `--cache` (fichier de cache, `wiki_cache.json` par défaut).

### Ce que fait le script

1. Lit le fichier d'entrée et la page existante (si elle existe).
2. **Pose des questions avant toute requête** (seulement dans un terminal) :
   - quelles catégories retirer de la page (titre et cartes) ;
   - quelles cartes de la page ne sont plus dans le fichier, à supprimer ou à garder.
3. Interroge Wikipédia uniquement pour les cartes absentes du cache (ou sans image, ou « introuvable » avec une ancienne version).
4. Télécharge les images dans `docs/assets/img/`.
5. Écrit la page de collection, en réécrivant seulement le bloc entre les repères `wikipick:debut` et `wikipick:fin`. Le texte écrit à la main autour de ce bloc est gardé.
6. Met à jour `index.md` (la page d'accueil de la section) : les tuiles des collections et le journal.

Sans terminal (tâche planifiée), aucune question n'est posée et rien n'est supprimé.

### Ce qui n'est jamais supprimé sans accord

- les cartes déjà sur le site, sauf suppression confirmée ;
- les catégories absentes du fichier, sauf si tu les retires ;
- le texte écrit à la main sur une page ;
- les images déjà téléchargées ;
- le cache, même avec `--refresh`.

### Dates et journal

- **Date de collection** : chaque page affiche « mise à jour le JJ/MM/AAAA ». La date ne change que si une carte est ajoutée, retirée ou modifiée.
- **Date d'ajout par carte** : gardée dans `wiki_historique.json`, pas affichée sur les cartes (pour ne pas alourdir la page).
- **Journal** : le bloc « Dernières modifications » de `index.md` liste les 10 derniers événements (ajouts, retraits, modifications), entre les repères `wikipick:journal`. Le fichier garde les 100 derniers événements.
- Au premier passage sur une collection, son état est noté sans journal, et les cartes existantes n'ont pas de date d'ajout connue.
- La clé de suivi est le chemin de la page depuis `docs/` (deux pages peuvent porter le même nom dans deux dossiers).

### Fichiers générés

| Fichier | Contenu | Remarque |
|---|---|---|
| `wiki_cache.json` | Fiches Wikipédia (titre, description, résumé, image, licence) | Jamais vidé. Un fichier illisible est mis de côté avant d'être repris à zéro. |
| `wiki_historique.json` | Dates d'ajout des cartes, empreintes, journal | Pas de Wikipédia dedans. Un fichier illisible est mis de côté. |
| `docs/<dossier>/<collection>.md` | Page de collection | Le texte hors repères est gardé. |
| `docs/<dossier>/index.md` | Page d'accueil de la section | Le titre est fixé par `titre_page`. |

Le script est à lancer depuis la racine du projet, car les fichiers de cache sont cherchés dans le dossier courant. Il doit recevoir un dossier de sortie situé dans `docs/`.

### Correctif ponctuel : `corriger_dates_wikipick.py`

Initialise les dates de toutes les pages wikipick et de toutes les cartes à la date du jour. Sans option, il simule. Avec `--appliquer`, il écrit les pages et `wiki_historique.json`. Il n'a pas à être relancé et peut être supprimé.

```bash
python3 corriger_dates_wikipick.py               # simulation
python3 corriger_dates_wikipick.py --appliquer   # écriture
```

## Licences

Les textes des collections proviennent de Wikipédia et Wikidata, sous [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/deed.fr). Les images proviennent de Wikimedia Commons ; l'auteur et la licence sont indiqués sous chaque image.
