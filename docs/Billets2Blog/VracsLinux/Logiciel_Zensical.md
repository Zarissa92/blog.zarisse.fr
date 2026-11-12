---
title: "Tuto Zensical : créer et publier un site (blog et wiki) en Markdown"
description: Installer Zensical, structurer un projet, écrire des pages, personnaliser le style et mettre en ligne.
date:
  created: 2026-11-10 23:27
  updated: 2026-11-11 09:07
weight: -202611102327
---

# Zensical : créer et publier un site (blog et wiki) en Markdown

Ce tuto rassemble l'essentiel pour monter un site avec Zensical, de l'installation à la mise en ligne, sans réinventer la roue.

[Zensical](https://github.com/zensical/zensical), c'est un générateur de sites statiques écrit en [Rust](https://rust-lang.org/) et en Python, qui s'installe comme un paquet Python. C'est l'équipe derrière Material for MkDocs qui le développe, donc si vous connaissez MkDocs, vous ne serez pas perdu·e. Le principe est simple : on écrit ses pages en Markdown, Zensical en sort un site HTML qu'on pose sur n'importe quel serveur web.

Au programme : installation, structure d'un projet, configuration, rédaction, un peu de CSS et la mise en ligne avec nginx.

## 1. Prérequis

- Python 3 récent, avec son module `venv`
- Un terminal
- Un éditeur de texte (VSCodium, Neovim, ce que vous voulez)

!!! tip "Sous Debian / Ubuntu"
    Le module `venv` est dans un paquet à part. S'il n'est pas là, la création de l'environnement virtuel plante :

    ```bash
    sudo apt install python3-venv
    ```

## 2. Installation

Zensical s'installe avec `pip`, dans un environnement virtuel pour ne pas encombrer le Python du système :

```bash
mkdir ~/mon-site && cd ~/mon-site
python3 -m venv .venv
source .venv/bin/activate
pip install zensical
zensical --version
```

Si le terminal vous dit que `zensical` est introuvable, c'est potentiellement que l'environnement virtuel n'est pas activé. Le prompt doit commencer par `(.venv)`. Il faut le réactiver (`source .venv/bin/activate`) à chaque nouveau terminal.

Pour mettre Zensical à jour plus tard :

```bash
pip install --upgrade zensical
```

## 3. Créer le projet

Zensical sait générer un squelette de projet tout seul, avec un `zensical.toml` bien commenté :

```bash
zensical new .
```

Au quotidien, trois commandes suffisent :

| Commande         | Rôle                                         |
| ---------------- | -------------------------------------------- |
| `zensical new`   | Crée un nouveau projet                       |
| `zensical serve` | Lance un serveur local avec rechargement     |
| `zensical build` | Génère le site final dans `site/`            |

Si vous versionnez le projet avec Git, pensez à exclure l'environnement virtuel et le dossier de sortie :

```text title=".gitignore"
.venv/
site/
```

## 4. Structure d'un projet

Voilà à quoi ressemble un projet type :

```text
mon-site/
├── zensical.toml        # configuration du site
├── docs/                # toutes les pages Markdown et les fichiers publiés
│   ├── index.md         # page d'accueil
│   ├── blog/
│   │   ├── index.md
│   │   └── premier-article.md
│   ├── wiki/
│   │   └── index.md
│   └── assets/          # CSS, JS, images
│       ├── images/
│       ├── javascripts/
│       │   └── extra.js
│       └── stylesheets/
│           └── extra.css
├── overrides/           # surcharges de thème (optionnel, hors de docs/)
└── site/                # sortie du build (on n'y touche jamais à la main)
```

Les règles à retenir :

- Tout ce qui doit être publié est dans `docs/` : pages, images, CSS, JavaScript. Un fichier rangé ailleurs n'est tout simplement pas copié lors du build.
- La seule exception, c'est `overrides/`. Il reste à la racine du projet, à côté de `zensical.toml`, parce qu'il contient des gabarits du thème et pas du contenu.
- Chaque dossier peut avoir son `index.md`, qui devient la page d'accueil de la section.
- Si vous ne définissez pas de menu, Zensical le construit tout seul à partir de l'arborescence de `docs/`.
- Le dossier source ne peut pas être la racine du projet (`docs_dir = "."` est refusé). Gardez donc bien un sous-dossier `docs/`.

## 5. Le fichier de configuration `zensical.toml`

Le fichier généré par `zensical new` est long, parce qu'il explique chaque option. En voici une version réduite à l'essentiel :

```toml title="zensical.toml"
[project]
site_name = "Mon blog"
site_url = "https://example.com/"
site_description = "Blog et wiki personnel"
site_author = "Auteur"
copyright = "© 2026 Auteur"

# Menu explicite (facultatif : sans nav, c'est l'arborescence de docs/ qui compte)
nav = [
  { "Accueil" = "index.md" },
  { "Blog" = [
      { "Vue d'ensemble" = "blog/index.md" },
      { "Premier article" = "blog/premier-article.md" },
  ]},
  { "Wiki" = "wiki/index.md" },
]

extra_css = ["assets/stylesheets/extra.css"]

[project.theme]
language = "fr"
features = [
  "navigation.instant",
  "navigation.sections",
  "navigation.indexes",
  "navigation.top",
  "search.highlight",
  "content.code.copy",
]

[project.theme.palette]
scheme = "default"   # "slate" pour un thème sombre
```

Quelques points importants :

- Toutes les options vont sous `[project]` ou ses sous-sections (`[project.theme]`, etc.). Une option écrite au-dessus de `[project]` est ignorée.
- `site_url`, c'est l'adresse finale du site. Elle sert pour les liens, le plan du site et les flux RSS.
- `nav` définit le menu. Une page qui n'y figure pas reste accessible par son URL, mais n'apparaît pas dans la navigation.
- Les chemins de `nav`, `extra_css` et `extra_javascript` partent de `docs/`.
- Les extensions Markdown (encadrés, blocs repliables, coloration syntaxique, listes de tâches, notes de bas de page…) sont **déjà activées** dans le `zensical.toml` généré, sous `[project.markdown_extensions.*]`. Il n'y a rien à ajouter pour s'en servir. Par contre, vous pouvez en désactiver.

## 6. Lancer le site en local

```bash
zensical serve
```

Ensuite, direction <http://127.0.0.1:8000>. Le site se recharge tout seul à chaque sauvegarde, ce qui permet de voir le rendu au fil de la rédaction. ++ctrl+c++ pour arrêter le serveur.

Pour générer les fichiers finaux :

```bash
zensical build
```

Tout se retrouve dans `site/`. C'est ce dossier qu'on publie, pas `docs/`. C'est tout le principe d'un site statique : le serveur web n'a plus qu'à servir des fichiers HTML déjà prêts.

## 7. Écrire une page

Chaque page peut commencer par un en-tête (le *front matter*), entre deux lignes `---` :

```markdown title="docs/blog/premier-article.md"
---
title: Premier article
description: Ma première note sur le sujet
---

# Premier article

Un paragraphe d'introduction, en **gras** ou en *italique*.

## Une section

- un élément
- un autre élément

1. étape une
2. étape deux

Un [lien vers le wiki](../wiki/index.md), et une image :

![Texte alternatif](../assets/images/capture.png)
```

- `title` s'affiche dans l'onglet du navigateur et dans le menu. Le `# Titre`, lui, c'est celui qu'on voit dans la page.
- `description` remplit la balise `<meta name="description">`, que reprennent les moteurs de recherche et les aperçus de liens.
- Les liens internes pointent vers le **fichier `.md`**, en chemin relatif. Zensical les transforme en URL et vous prévient au build s'il y a un lien cassé.

### Blocs de code

````markdown
```python
def bonjour(nom: str) -> str:
    return f"Bonjour {nom}"
```
````

Avec `content.code.copy` activé, chaque bloc a son petit bouton de copie. On peut aussi donner un titre au bloc :

````markdown
```bash title="installer.sh"
pip install zensical
```
````

## 8. Personnaliser le style avec du CSS

On crée `docs/assets/stylesheets/extra.css` :

```css title="docs/assets/stylesheets/extra.css"
:root {
  --md-primary-fg-color: #2e7d32;
  --md-accent-fg-color: #66bb6a;
}

.md-typeset h2 {
  border-bottom: 2px solid #66bb6a;
}
```

Puis on le déclare dans `zensical.toml`, sous `[project]`. Si vous avez repris l'exemple de la section 5, c'est déjà fait :

```toml
[project]
extra_css = ["assets/stylesheets/extra.css"]
```

Même principe pour du JavaScript :

```toml
[project]
extra_javascript = ["assets/javascripts/extra.js"]
```

Et pour charger un script comme module ES, on remplace la simple chaîne par une table :

```toml
[project]
extra_javascript = [
  { path = "assets/javascripts/extra.js", type = "module" },
]
```

!!! warning "Une seule déclaration"
    `extra_css` et `extra_javascript` ne doivent apparaître qu'**une seule fois** dans le fichier. Avec deux lignes `extra_css = ...` sous `[project]`, le TOML devient invalide et le build refuse de démarrer.

Pour aller plus loin (modifier un gabarit, personnaliser la page 404, changer l'en-tête), on crée un dossier `overrides/` à la racine du projet et on le déclare dans le thème :

```toml
[project.theme]
custom_dir = "overrides"
```

Le chemin de `custom_dir` part du fichier de configuration. Les fichiers déposés dans `overrides/` remplacent les gabarits du thème qui portent le même nom, par exemple `overrides/main.html` ou `overrides/404.html`. Zensical fournit déjà une page 404 par défaut, pas besoin d'en créer une sauf si vous voulez la personnaliser.

## 9. Ajouter une page au menu

1. Créez le fichier, par exemple `docs/wiki/nouvelle-page.md`.
2. Si vous utilisez `nav`, ajoutez-y le chemin à partir de `docs/` (`wiki/nouvelle-page.md`). Sinon, la page apparaît toute seule.
3. Vérifiez avec `zensical serve`.

## 10. Publier sur un serveur (nginx)

Une fois le build fait, on copie le **contenu** de `site/` sur le serveur. 

```bash
rsync -av --delete site/ utilisateur@serveur:/var/www/example.com/
```

L'option `--delete` supprime sur le serveur les fichiers qui n'existent plus dans `site/`. Vérifiez donc bien le chemin de destination avant de lancer la commande. Au moindre doute, faites d'abord un essai avec `--dry-run`.

Bloc nginx minimal (`/etc/nginx/sites-available/example.com`) :

```nginx
server {
    listen 80;
    listen [::]:80;
    server_name example.com;

    root /var/www/example.com;
    index index.html;

    location / {
        try_files $uri $uri/ =404;
    }

    error_page 404 /404.html;
}
```

On active le site, on vérifie la configuration et on recharge nginx :

```bash
sudo ln -s /etc/nginx/sites-available/example.com /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```

Pour le certificat Let's Encrypt, `sudo certbot --nginx -d example.com` s'occupe de tout : il ajoute le bloc HTTPS et la redirection depuis HTTP. Pour un sous-domaine (`blog.example.com`, comme ici), on crée un second bloc `server` avec son propre `server_name` et son propre `root`, puis on relance certbot pour ce nom.

### Automatiser le build et la mise en ligne

Un petit script enchaîne le build et l'envoi, ce qui évite d'oublier une étape :

```bash title="publier.sh"
#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"
source .venv/bin/activate
zensical build
rsync -av --delete site/ utilisateur@serveur:/var/www/example.com/
```

```bash
chmod +x publier.sh
./publier.sh
```
s
Et voila, vous avez votre blog perso :) 