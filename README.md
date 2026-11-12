# zarisse.fr

Site du blog de Zaza, généré avec [Zensical](https://zensical.org) (configuration : `zensical.toml`).
Les sources sont dans `docs/`, le site généré dans `site/` (ne pas modifier à la main).

## Structure

| Chemin | Rôle |
|---|---|
| `docs/` | Pages sources (Markdown) et ressources (`docs/assets/`) |
| `overrides/` | Gabarits du thème (en-tête, RSS, page de profil, pluie : `partials/pluie.html`) |
| `zensical.toml` | Configuration du site, du thème et du plugin RSS |
| `build.py` | Point d'entrée unique du build (voir ci-dessous), et l'aperçu local avec `--serve` |
| `scripts/build/` | Étapes appelées par `build.py` : `index_dossiers.py`, `dater_pages.py`, `billets_index.py`, `post_build_dates.py`, `post_build_og_images.py`, `post_build_og.py`, et `empreintes.py` (cache des images de partage) |
| `scripts/wikipick/` | `wikipick_site.py` (pages de collections « wiki-pick »), `corriger_dates_wikipick.py` (correctif ponctuel, peut être supprimé) |
| `donnees/wikipick/` | Données de wikipick : `wiki_cache.json` (cache des fiches Wikipédia), `wiki_historique.json` (dates d'ajout et journal), `listes/` (fichiers d'entrée, avec `archive/`) |
| `INdex>HTML/` | Site racine `zarisse.fr` : page qui liste les projets et les liens. Pas de build et aucun JavaScript — le contenu (photo, liens, contact) est écrit en HTML directement dans `index.html`. Liens : blog, GitHub, Mastodon, Discord (`discord.gg/QSCfR2NHJ`). Thème repris de `gauchiasses.fr` (panneau noir opaque, police Russo One dans `fonts/` avec sa licence `OFL.txt`, liens en boutons), avec la pluie matricielle en CSS pur aux seules couleurs du drapeau trans : 40 colonnes `<i>` écrites une fois dans `index.html`, même méthode que `rain()` de `gauchiasses.fr/bin/build_site.py` |
| `outils/publication/` | Fonctions fish de publication : `blog_push.fish`, `zarisse_push.fish` |
| `outils/previews/` | Previews du site sur le serveur : `deploy-preview.sh`, `setup-previews.sh`, notes (voir plus bas) |
| `outils/nginx/` | `exclure_lan_nginx.py` : journaux nginx sans le réseau local |
| `outils/contact/` | `contact.py` : formulaire de contact de kioske.fr et commentaires sous les articles (voir plus bas). `deploy_contact.sh` (installation et mise à jour sur le serveur), `activer_ssi_blog.sh` (ajoute `ssi on;` au blog), `contact.service`, `contact-import.service` et `contact-import.timer` (modèles d'unités ; l'import tourne toutes les 5 minutes), `nginx-contact.conf`, `nginx-commentaires.conf` : mise en service |
| `overrides/main.html` | Ajoute, sous chaque article (page avec une date), l'include SSI des commentaires |
| `outils/fail2ban_crawlers/` | Jails anti-robots (voir plus bas) |
| `venv_blog/` | Environnement Python contenant Zensical. Non synchronisé (voir « Environnement Python ») |
| `requirements.txt` | Paquets du venv, pour le recréer |
| `venv.txt` | Nom du venv à créer (`venv_blog`) |

## Thème

Le blog reprend le thème de `gauchiasses.fr`, avec uniquement les couleurs du drapeau trans (bleu `#5bcefa`, rose `#f5a9b8`, blanc), pour la pluie comme pour le reste. Pas de cycle rouge / vert / trans comme sur `gauchiasses.fr`.

- **Repris de gauchiasses.fr** : fond noir, panneaux **opaques** sans translucidité ni flou (choix de lisibilité), angles droits, cadres lumineux, police Russo One partout sauf dans le code, titre `h1` en majuscules qui scintille, curseur `_` clignotant en bas du panneau, boutons `>` inversés au survol. Pas de halo sur le texte courant.
- **Aucun JavaScript pour le thème** : la pluie est en CSS pur. Ses 40 colonnes `<i>` sont écrites une fois dans `overrides/partials/pluie.html` (même méthode que `rain()` de `gauchiasses.fr/bin/build_site.py`, graine 42), incluses avant l'en-tête par `overrides/main.html`. L'ancien `pluie.js` (canvas) a été supprimé.
- **Fichiers** : `docs/assets/pluie.css` contient tout le thème et ses variables (`--bleu`, `--rose`, `--texte`, `--panneau`, `--r-tete`/`--r-haut`/`--r-moyen` pour la pluie…). Les anciens noms `--violet` et `--violet-doux` restent comme alias du texte blanc, pour les autres feuilles. `collection.css` (cartes wikipick, opaques, angles droits) et `accueil.css` suivent le même style.
- **Police** : `docs/assets/fonts/russo-one.woff2`, avec sa licence `OFL.txt`, servie depuis le site (aucune police externe). Le code reste en Fira Code / police à chasse fixe du système.
- **Mouvements réduits** (`prefers-reduced-motion`) : la pluie s'arrête, le titre et le curseur ne clignotent plus.

## Build

```bash
venv_blog/bin/python build.py            # ne refait que les images de prévisualisation modifiées
venv_blog/bin/python build.py --forcer   # refait toutes les images de prévisualisation
venv_blog/bin/python build.py --serve    # build complet, puis aperçu sur http://localhost:8000 (Ctrl+C pour arrêter)
```

`build.py` est le point d'entrée unique : il lance les étapes dans l'ordre ci-dessous. Il s'arrête dès qu'une étape échoue, avec un code de sortie non nul. Il écrit dans `site/`, et dans `docs/` uniquement pour les quatre premières étapes (index.md manquants et repères de liste, front matter des dates et du poids de navigation, listes des pages entre leurs repères ; le texte des pages n'est jamais modifié).

1. **Index des dossiers** : `index_dossiers.py` crée un `index.md` dans chaque dossier de `docs/` qui contient au moins une page `.md` (directement ou dans un sous-dossier) et n'en a pas encore. L'index créé contient un front matter avec `title`, tiré du nom du dossier (`_` remplacé par une espace), suivi des repères `<!-- billets:debut -->` / `<!-- billets:fin -->` : la liste des pages du dossier s'y remplit toute seule à l'étape 3 ; à toi d'écrire le texte autour. **Un `index.md` existant qui n'a pas ces repères les reçoit à la fin du fichier** (ajout à la suite, sur place : le texte n'est pas modifié et le fichier garde sa date de naissance), si bien que tous les index ont leur liste, accueil et `Fiches_Wiki/` compris. Pour placer la liste ailleurs dans la page, déplace les deux repères à la main : le script ne les rajoute pas tant qu'ils sont là. Un index qui n'a qu'un seul des deux repères est signalé et laissé tel quel. Ignorés : `docs/assets/`, les dossiers cachés et ceux sans page (`img/`…). Simulation seule : `venv_blog/bin/python scripts/build/index_dossiers.py`.
2. **Dates des pages** : `dater_pages.py` ajoute `date` (création et modification) au front matter des pages qui n'en ont pas encore, au format `AAAA-MM-JJ HH:MM`, en heure française (`Europe/Paris`, heure d'été comprise). Sur une page déjà datée, la date de création ne change pas ; la date de modification avance quand le fichier a été modifié depuis la date notée. Une date notée sans heure reçoit l'heure du fichier si c'est le même jour, sinon elle reste sans heure. Noter la date ne compte pas comme une modification : la date de modification du fichier est remise à sa valeur d'avant. Les pages affichent « Créée le 10/11/2026 à 16h08 · modifiée le … » (`overrides/main.html`), ou la date seule quand il n'y a pas d'heure. Attention au front matter : `created` et `updated` doivent être décalés de deux espaces sous `date:`, sinon ils ne sont pas lus comme dates.
3. **Liste des billets** : `billets_index.py` réécrit la liste entre les repères `<!-- billets:debut -->` et `<!-- billets:fin -->` de **tous les `index.md` de `docs/`** (l'étape 1 garantit qu'ils les ont tous ; `docs/assets/` et les dossiers cachés sont ignorés), avec les pages du dossier de l'index (billet le plus récent en haut : le tri suit `date.created`, **heure comprise**, donc deux billets du même jour sont classés par heure de création ; une date sans heure compte pour 00:00, et le nom de fichier ne départage que les ex æquo). Le build s'arrête si les repères sont absents de `docs/Billets2Blog/index.md`. Les sous-dossiers (ex. `VracsLinux/`, `divers/Animé&Manga/`) sont listés sous les pages, dans « Sections ». Dans `Fiches_Wiki/index.md`, la liste s'ajoute sous les blocs de wikipick, qui ne réécrit que ses propres repères. Réécrire une liste compte comme une modification de l'index : sa date `updated` avance au build suivant.
4. **Ordre de la navigation** : `nav_ordre.py` écrit `weight: -AAAAMMJJHHMM` dans le front matter de chaque page de `docs/` (`index.md` exclus). La date est celle de `billets_index.py` (`date.created`, sinon la date notée, sinon la date du fichier), donc la barre latérale suit le même ordre que les listes de billets. Le plugin `mkdocs-nav-weight` (`zensical.toml`) trie la barre latérale d'après ce poids, du plus petit au plus grand : le plus récent est en haut. Le poids est recalculé à chaque build ; seule la ligne `weight:` change, et la date de modification du fichier est remise à sa valeur d'avant. Les pages `index.md` (sections) gardent le poids par défaut du plugin (-10). Simulation seule : `venv_blog/bin/python scripts/build/nav_ordre.py`.
5. **Build Zensical** : `venv_blog/bin/zensical build`, qui écrit `site/`. Si Zensical échoue, le script s'arrête avec le même code de sortie.
6. **Dates des flux** : `post_build_dates.py` (voir plus bas). Elle passe avant la vérification pour que celle-ci contrôle le résultat final.
7. **Flux RSS** : vérifie que, dans `site/`, la feuille `rss.xsl` existe, que `feed_rss_created.xml` et `feed_rss_updated.xml` existent, qu'ils sont du XML valide avec un élément `<channel>`, et qu'ils contiennent au moins un article. Ces deux flux sont ceux référencés par `overrides/main.html` et `overrides/partials/header.html`.
8. **Images de partage** : `post_build_og_images.py` crée, pour chaque page, une image 1200×630 avec son titre et sa description, dans `site/assets/og/`. Les pages qui ont un `og_image` dans leur front matter gardent leur image. Une image n'est redessinée que si le titre, la description, l'avatar ou le script ont changé ; sinon sa copie de `.cache/og/` est recopiée (Zensical vide `site/` à chaque build).
9. **Balises Open Graph** : `post_build_og.py` (voir plus bas). Il utilise l'image de la page, ou l'image générée à l'étape précédente.

Les messages `✓` et `✗` s'affichent à chaque étape. Le message final « Site prêt dans … » indique que tout s'est bien passé.

Pour publier, il suffit de déployer le dossier `site/`.

### Aperçu local

Utilise `venv_blog/bin/python build.py --serve` : il fait le build complet puis sert `site/` tel qu'il sera déployé (une page absente affiche le `404.html` du site). Il ne se met pas à jour tout seul : relance-le après une modification.

**N'utilise pas `zensical serve` (ni `zensical build`) avant de déployer.** Ils réécrivent `site/` sans les étapes post-build : les dates des flux redeviennent la date du build, et les images et balises de partage disparaissent. Si tu l'as fait, relance `venv_blog/bin/python build.py` avant de déployer.

### Dépendances

- Toutes les commandes Python passent par le venv `venv_blog/` (voir ci-dessous), jamais par le Python du système.
- Zensical, PyYAML et Pillow sont dans `requirements.txt`. Pillow sert à `post_build_og_images.py` ; la police Fira Sans est utilisée si elle est installée, sinon DejaVu ou la police par défaut de Pillow.
- La commande `stat` (GNU coreutils) pour `post_build_dates.py`
- La base des fuseaux horaires (`tzdata`, présente par défaut sur Arch et Debian) : `dater_pages.py` et `post_build_dates.py` écrivent les dates en heure française avec `zoneinfo` (`Europe/Paris`)

### Environnement Python

- `venv_blog/` **n'est jamais uploadé** : ni sur le serveur, ni dans une copie du projet. Chaque machine le recrée à partir de `requirements.txt`.
- `requirements.txt` liste les paquets exacts (`pip freeze` du venv actuel).
- `venv.txt` indique le nom du venv à créer : `venv_blog`.

Recréer le venv :

```bash
python3 -m venv venv_blog
venv_blog/bin/python -m pip install -r requirements.txt
```

## Post-build

### `post_build_dates.py` : dates des flux

Les flux produits par Zensical datent tous les articles de la date du build. Ce script les remplace par les dates des fichiers sources.

- Le fichier source d'un article est retrouvé à partir de son lien : `https://zarisse.fr/<chemin>/` correspond à `docs/<chemin>.md` ou `docs/<chemin>/index.md`.
- **Flux « créés »** (`feed_rss_created.xml`, `feed_json_created.json`) : date de **création**, lue d'abord dans `date.created` du front matter. Si elle n'a pas d'heure, c'est l'heure de naissance du fichier (`stat -c %W`) quand c'est le même jour, sinon minuit. Sans `date.created`, c'est la naissance du fichier.
- **Flux « mis à jour »** (`feed_rss_updated.xml`, `feed_json_updated.json`) : date de **modification**.
- Dans le JSON, `date_published` contient la création et `date_modified` la modification, dans les deux flux.
- Si la date de création n'est pas disponible, la date de modification est utilisée. Un article sans fichier source garde la date du build.
- Toutes les dates des flux sont en heure française (`+0100` l'hiver, `+0200` l'été).
- **Les pages d'index (`index.md`) sont retirées des flux** : accueil, sommaires de dossier et listes de billets ne sont pas des articles. Comme le plugin `rss` ne sait pas les exclure, `zensical.toml` lui demande 40 entrées (`length`), et le script ne garde que les 20 articles les plus récents (`ARTICLES_MAX`) une fois les index retirés.
- Les articles sont triés du plus récent au plus ancien, et la date de la chaîne suit l'article le plus récent.
- Le XML est modifié en texte brut, pour conserver l'instruction `xml-stylesheet` (feuille `rss.xsl`).

**Limite** : la date de naissance d'un fichier change s'il est recréé (certains éditeurs font une sauvegarde en créant un nouveau fichier, `sed -i`, une synchronisation ou une copie peuvent aussi le faire). Une fois `date.created` notée dans le front matter, c'est elle qui compte : la recréation du fichier ne change plus la date de création. La date de modification, elle, suit toujours le fichier.

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

Ordre de recherche de l'image d'une carte : image principale de l'article, puis image Wikidata (P18), puis paramètre `image =` (ou `logo =`) de l'infobox de l'article. Les cartes sans image dans le cache (`wiki_cache.json`) sont redemandées au prochain lancement ; les articles introuvables ne le sont pas.

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
| `entree` | Fichier d'entrée par défaut, relatif à `donnees/wikipick/listes/` |
| `categories` | Ranger les cartes par catégorie |
| `categories_ouvertes` | Catégories dépliées à l'ouverture (sinon repliées) |
| `largeur_image` | Largeur des images, en px (330, 500, 960…) |
| `longueur_resume` | Longueur maximale du résumé (0 = complet) |
| `titre_page` | Titre de la page d'accueil de la section |
| `dossier_images` | Dossier des images téléchargées, dans `docs/` |

Les réglages avancés (API, User-Agent, pauses entre requêtes) sont juste en dessous.

### Utilisation

```bash
venv_blog/bin/python scripts/wikipick/wikipick_site.py                       # réglages de CONFIG
venv_blog/bin/python scripts/wikipick/wikipick_site.py archive/queens.txt    # autre fichier, relatif à donnees/wikipick/listes/
venv_blog/bin/python scripts/wikipick/wikipick_site.py --refresh             # redemande les fiches du fichier à Wikipédia
venv_blog/bin/python scripts/wikipick/wikipick_site.py --images distant      # liens Wikimedia au lieu de copies locales
```

Le fichier d'entrée est cherché tel quel, puis à partir de la racine du projet, puis dans `donnees/wikipick/listes/`.

Options : `--sortie` (dossier de sortie), `--cache` (fichier de cache, `donnees/wikipick/wiki_cache.json` par défaut).

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
| `donnees/wikipick/wiki_cache.json` | Fiches Wikipédia (titre, description, résumé, image, licence) | Jamais vidé. Un fichier illisible est mis de côté avant d'être repris à zéro. |
| `donnees/wikipick/wiki_historique.json` | Dates d'ajout des cartes, empreintes, journal | Pas de Wikipédia dedans. Un fichier illisible est mis de côté. |
| `docs/<dossier>/<collection>.md` | Page de collection | Le texte hors repères est gardé. |
| `docs/<dossier>/index.md` | Page d'accueil de la section | Le titre est fixé par `titre_page`. |

Les fichiers de données sont toujours cherchés dans `donnees/wikipick/`, quel que soit le dossier courant. Le dossier de sortie doit être situé dans `docs/`.

### Correctif ponctuel : `corriger_dates_wikipick.py`

Initialise les dates de toutes les pages wikipick et de toutes les cartes à la date du jour. Sans option, il simule. Avec `--appliquer`, il écrit les pages et `wiki_historique.json`. Il n'a pas à être relancé et peut être supprimé.

```bash
venv_blog/bin/python scripts/wikipick/corriger_dates_wikipick.py               # simulation
venv_blog/bin/python scripts/wikipick/corriger_dates_wikipick.py --appliquer   # écriture
```

## Publication

Deux sites partent de ce dossier, vers deux cibles différentes sur le serveur. Les
deux fonctions fish vivent dans `outils/publication/` et suivent la même logique :
`rsync --checksum` (comparaison du contenu, pas des dates), `--delete`, exclusion
des fichiers cachés, et tout argument supplémentaire passé à rsync.

| Fonction | Source | Destination | À faire avant |
|---|---|---|---|
| `blog_push` | `site/` | `meli@192.168.1.13:/home/meli/blog/` | `venv_blog/bin/python build.py` |
| `zarisse_push` | `INdex>HTML/` | `meli@192.168.1.13:/home/meli/html/` | rien, pas de build |

```bash
blog_push --dry-run      # vérifier ce qui partirait
blog_push
zarisse_push --dry-run
zarisse_push
```

Pour installer les fonctions dans fish, un lien symbolique garde le projet comme
référence — modifier le fichier ici suffit alors à mettre la fonction à jour :

```bash
ln -sfn /home/melissandre/zarisse.fr/outils/publication/zarisse_push.fish ~/.config/fish/functions/zarisse_push.fish
ln -sfn /home/melissandre/zarisse.fr/outils/publication/blog_push.fish ~/.config/fish/functions/blog_push.fish
```

Le nom du dossier `INdex>HTML` contient un `>` : il doit rester entre guillemets
dans tout script shell, sinon il est interprété comme une redirection.

### Previews

`outils/previews/deploy-preview.sh <nom> [utilisateur@serveur] [options rsync]` publie
une preview du site dans `/var/www/previews/<nom>/` : il lance `venv_blog/bin/python build.py`, puis
`rsync --checksum --delete --delete-excluded`, comme `blog_push`. `--dry-run` simule.
Ne pas remplacer `build.py` par `zensical build` : il saute les étapes post-build.

`setup-previews.sh` se lance une fois, en root, **sur le serveur**. Les étapes manuelles
(DNS, certificat wildcard) et les questions ouvertes sont dans `session-nginx-previews.md`.

## Serveur : protection anti-robots

`outils/fail2ban_crawlers/` contient deux jails fail2ban qui bannissent 7 jours les
aspirateurs de site et les scanners de failles, **sans jamais toucher au flux RSS** :

- `zarisse-scans` : une seule requête vers un chemin inexistant ici (`wp-login.php`,
  `/.env`, `/.git/config`, n'importe quel `.php`…) suffit à bannir.
- `zarisse-cadence` : plus de 30 pages HTML en 60 secondes depuis la même IP, quel
  que soit le user-agent déclaré.

Le flux RSS, les ressources statiques, les moteurs de recherche et les robots
d'aperçu du fédivers ne sont jamais comptés. Le ban est appliqué par nginx
(`banaction = nginx-geo-ban`), pas par le pare-feu.

Installation et réglages : voir `outils/fail2ban_crawlers/README.md`. À installer en
root **sur le serveur**, après une mesure à blanc :

```bash
rsync -av outils/fail2ban_crawlers meli@192.168.1.13:/home/meli/
ssh meli@192.168.1.13
cd ~/fail2ban_crawlers && sudo ./installer.sh --tester   # ne modifie rien
sudo ./installer.sh
```

## Formulaire de contact (kioske.fr)

`outils/contact/contact.py` est le formulaire de contact de kioske.fr, en un seul fichier
(bibliothèque standard, aucun JavaScript) :

- `GET /contact` : affiche le formulaire, avec une question anti-robot (« Combien font
  4 + 7 ? »). La réponse est signée (HMAC) dans un jeton caché : elle n'est pas lisible
  dans la page, et le jeton expire au bout d'une heure.
- `POST /contact` : reçoit l'envoi et l'enregistre dans `/home/meli/contact/messages.db`
  (SQLite, table `messages` : `pseudo`, `message`, `date`, `ip`). Écoute sur
  `127.0.0.1:8765`, donc seul nginx peut le joindre.
- `/home/meli/contact/cle.secret` : clé de signature, créée au premier lancement
  (600). La supprimer invalide les questions en cours, sans autre effet.

Le champ `site` est un piège à robots, caché et à laisser vide.

Garde-fous du script : origine limitée à `https://kioske.fr`, format de formulaire
imposé, 8 Ko maximum, question anti-robot, 5 envois par visiteur sur 10 minutes (en
mémoire), champs nettoyés, en-têtes de sécurité. Ces réglages sont en tête de `contact.py`.

Le CAPTCHA est une question d'addition : il arrête les robots simples, pas ceux qui
sont conçus pour ce type de question. Un CAPTCHA en image demanderait une bibliothèque
(Pillow) ; je ne l'ai pas ajoutée.

**L'adresse IP de chaque envoi est conservée 60 jours**, pour agir en cas de contenu
haineux. Passé ce délai, elle est effacée à chaque nouvel envoi (`CONSERVATION_IP_JOURS`
dans `contact.py`) ; le message reste en base. Ce choix doit être indiqué sur la page de
kioske.fr (finalité, durée de conservation, contact), car c'est une donnée personnelle.

### Mise en service

**Avec le script** (recommandé) : après la synchronisation de `outils/contact/` sur le Lenovo,
lancer depuis ce dossier :

```bash
sudo bash deploy_contact.sh install   # première fois : unité systemd, snippets, vérifications
sudo bash deploy_contact.sh maj       # après une mise à jour de contact.py
```

Le script sauvegarde ce qu'il remplace dans `~/sauvegardes_deploiement/`, redémarre le
service et vérifie qu'il répond. Il ne modifie jamais les sites nginx : si une ligne manque
(`include snippets/contact.conf;` pour kioske.fr, `ssi on;` et `include snippets/commentaires.conf;`
pour blog.zarisse.fr), il l'affiche et s'arrête. Ajoutez-la à la main, puis relancez `install`.
Les noms des fichiers de sites sont dans l'en-tête du script (`SITE_KIOSKE`, `SITE_BLOG`).

**Activer les commentaires dans nginx** : `sudo bash activer_ssi_blog.sh` ajoute `ssi on;` et
l'include des commentaires dans le bloc de blog.zarisse.fr, juste après sa ligne `server_name`.
Il cible le bloc HTTPS de ce domaine (celui qui a `listen 443` et son certificat), en
exigeant qu'il soit unique : les blocs du port 80 sont ignorés. Il vérifie aussi que
`sites-enabled/default` est un lien vers `sites-available/default` (nginx ne lit que
`sites-enabled/`) ; sinon il remplace la copie par un lien, après sauvegarde, et s'arrête si la
copie diffère du fichier modifié. Il sauvegarde le fichier, teste `nginx -t` et restaure
l'original si le test échoue. Il peut être relancé sans risque.

Les étapes ci-dessous détaillent ce que fait le script, pour le suivre ou le refaire à la main.

Fichiers prêts : `outils/contact/contact.service` (unité systemd) et
`outils/contact/nginx-contact.conf` (bloc nginx). Rien n'est modifié sur le serveur tant
que les commandes suivantes ne sont pas lancées. Toutes les commandes `sudo` sont à lancer
à la main sur le Lenovo.

**1. Synchroniser le dossier** (depuis Garuda, à la racine du projet). Simuler d'abord :

```bash
rsync -av --dry-run outils/contact/ meli@192.168.1.13:/home/meli/zarisse.fr/outils/contact/
rsync -av outils/contact/ meli@192.168.1.13:/home/meli/zarisse.fr/outils/contact/
```

**2. Préparer le dossier de données et vérifier le Python du projet** (sur le Lenovo) :

```bash
mkdir -m 700 /home/meli/contact
ls -l /home/meli/zarisse.fr/venv_blog/bin/python
```

Si le venv n'existe pas sur le serveur, le recréer à partir de `requirements.txt`
(voir « Environnement Python »). Le script n'utilise que la bibliothèque standard, donc
le venv suffit.

**3. Tester à la main, avant le service** (sur le Lenovo, Ctrl+C pour arrêter) :

```bash
cd /home/meli/zarisse.fr/outils/contact && /home/meli/zarisse.fr/venv_blog/bin/python contact.py
```

Dans un second terminal : `curl -s http://127.0.0.1:8765/contact | head -n 5` doit
afficher le début du formulaire.

**4. Installer le service** (sudo, sur le Lenovo) :

```bash
sudo cp /home/meli/zarisse.fr/outils/contact/contact.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now contact.service
systemctl status contact.service
```

Le journal se lit avec `journalctl -u contact.service -n 50`. Le script ne journalise
rien sur les visiteurs : le journal ne contient que les démarrages et les erreurs.

**5. Brancher nginx** : sauvegarder d'abord la configuration de kioske.fr, puis ajouter
le bloc. Le fichier de configuration de kioske.fr n'est pas dans ce projet : il faut
le nommer avant de continuer.

```bash
sudo cp /etc/nginx/sites-available/<fichier-kioske> /home/meli/sauvegarde-nginx-kioske-$(date +%F).conf
sudo cp /home/meli/zarisse.fr/outils/contact/nginx-contact.conf /etc/nginx/snippets/contact.conf
```

Puis, dans le bloc `server { }` de kioske.fr, ajouter la ligne
`include snippets/contact.conf;`, et enfin :

```bash
sudo nginx -t && sudo systemctl reload nginx
```

**6. Vérifier** : `curl -I https://kioske.fr/contact` doit répondre `200`, et un envoi
depuis la page doit apparaître dans `/home/meli/contact/messages.db`.

**Limite à connaître** : nginx garde ses propres journaux d'accès (`/var/log/nginx/`),
où les adresses IP apparaissent aussi, et ceux-ci ne sont pas effacés après 60 jours. La
conservation de 60 jours ne vaut que pour la base du formulaire. Pour l'annoncer
correctement sur la page, il faut en tenir compte.

**Annulation** : `sudo systemctl disable --now contact.service`, retirer la ligne
`include` de kioske.fr, `sudo nginx -t && sudo systemctl reload nginx`.

## Commentaires sous les articles (zarisse.fr)

Chaque article (page avec une date) affiche, en bas, les commentaires validés et un
formulaire. Pas de JavaScript : nginx inclut le fragment au moment de l'affichage
(SSI), donc un commentaire validé apparaît sans reconstruire le blog.

**Parcours d'un commentaire**

1. Le visiteur envoie le formulaire : `POST /commentaire` (contrôle d'origine
   `https://blog.zarisse.fr`, question anti-robot, champ piège, 5 envois par 10 minutes).
2. `contact.py` écrit un fichier texte dans `/home/meli/contact/commentaires/`, nommé
   `AAAA-MM-JJ_HHMMSS_pseudo_xxxxxx.txt` :

   ```
   valide: 0
   article: divers/cv.md
   pseudo: Zaza
   date: 2026-11-11 17:18
   ip: 203.0.113.7

   Le message, sur une ou plusieurs lignes.
   ```

3. **Vous validez à la main** : vous ouvrez le fichier et vous mettez `valide: 1`.
4. **Le timer `contact-import.timer` lance l'import toutes les 5 minutes** (`contact.py importer`).
   Le commentaire entre dans la table `commentaires` de `messages.db`, s'affiche sous l'article,
   et **son fichier texte est supprimé**. Les fichiers `valide: 0` restent en attente.
   Pour lancer l'import tout de suite : `sudo systemctl start contact-import.service`.

Une fois importé, un commentaire n'existe plus que dans la base. Pour le retirer, supprimer sa
ligne (`delete from commentaires where id = …;`, avec `sqlite3`). Le timer et les unités sont
installés par `deploy_contact.sh` (install comme maj). Journal : `journalctl -u contact-import.service`.

**Conservation** : le message reste. L'adresse IP est effacée après 60 jours, dans la base
et dans les fichiers en attente (`ip: (effacée)`). L'import fait ce nettoyage, comme le script à
chaque envoi pour la table `messages`. Un fichier validé est supprimé à l'import, donc son IP
n'existe plus que dans la base. Un fichier jamais validé reste en attente, et son IP suit la
même règle de 60 jours.

**Lecture de la base** (sur le Lenovo) : `sqlite3 /home/meli/contact/messages.db "select article, pseudo, date from commentaires;"`
(paquet `sqlite3` requis).

**Désactiver les commentaires** : depuis ce poste, `commentaires_off` ; pour les réactiver,
`commentaires_on`. Les deux fonctions (`outils/publication/`) créent ou suppriment, sur le serveur,
le fichier `~/contact/commentaires.desactives`. Tant qu'il existe, `contact.py` affiche une section
vide sous les articles (les commentaires déjà validés sont masqués) et refuse les envois (503). Pas
de redémarrage ni de rebuild : le script regarde le fichier à chaque requête. L'import continue
de tourner, sans effet visible.

**Ce qui s'affiche sous un article** : `overrides/main.html` ajoute l'include SSI
`<!--#include virtual="/commentaire?article={{ page.url | urlencode }}" -->` aux pages qui ont une
date, sauf les pages d'index (celles qui contiennent le repère `billets:debut`). L'identifiant
de l'article est donc son URL (`divers/cv/`), pas son chemin source. La section est mise en
forme par `docs/assets/pluie.css` (fin du fichier : `.commentaires`, `.commentaire`).

**Mise en service** (en plus de celle du formulaire kioske.fr) :

1. Sur le Lenovo, `sudo bash deploy_contact.sh install` (depuis `outils/contact/`) : service,
   snippets, vérifications.
2. `sudo bash activer_ssi_blog.sh` : ajoute `ssi on;` et l'include dans le bloc HTTPS de
   blog.zarisse.fr, et vérifie que `sites-enabled/default` est un lien vers
   `sites-available/default`.
3. Publier le blog : `venv_blog/bin/python build.py`, puis `blog_push` (simulation d'abord).
4. Vérifier : `curl -s "https://blog.zarisse.fr/commentaire?article=divers%2Fcv%2F"` doit
   renvoyer la section « Commentaires ».

Depuis le poste de travail, `zarisse_update` synchronise `outils/contact/` puis lance
`activer_ssi_blog.sh` sur le serveur (`--dry-run` : synchronisation simulée seulement).

**Piège rencontré** : nginx lit `/etc/nginx/sites-enabled/`, pas `sites-available/`. Sur le
serveur, `sites-enabled/default` était une copie et non un lien : les modifications faites dans
`sites-available/` n'étaient pas chargées, et la route renvoyait 404. `activer_ssi_blog.sh`
contrôle désormais ce lien.

**Vérifications en fonctionnement** :

- après un build, la section doit apparaître sur un article (pas sur un index) ;
- `systemctl list-timers contact-import.timer` affiche la prochaine importation (toutes les 5 minutes) ;
- `journalctl -u contact-import.service -n 20` montre les derniers imports.

Après chaque mise à jour de `contact.py` ou des modèles d'unités, `sudo bash deploy_contact.sh maj`
réinstalle les unités (service et timer) et redémarre le service.

**Sauvegarde** : le contenu de `/home/meli/contact/` n'a pas été vérifié dans la sauvegarde de
3 h (`/usr/local/sbin/sauvegarde.sh` n'est pas lisible depuis le compte utilisateur).

Pas encore fait : le panneau d'administration. Pour l'instant, la validation se fait dans les
fichiers texte.

## Licences

Les textes des collections proviennent de Wikipédia et Wikidata, sous [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/deed.fr). Les images proviennent de Wikimedia Commons ; l'auteur et la licence sont indiqués sous chaque image.
