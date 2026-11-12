# Jails anti-robots pour blog.zarisse.fr

Deux jails fail2ban qui éliminent les robots d'aspiration et les scanners, **sans
jamais toucher au flux RSS**. Le ban passe par nginx (`banaction = nginx-geo-ban`,
installé par `f2b.sh`) : l'IP est ajoutée à `/etc/nginx/banned_ips.conf` et reçoit
la page 403 « Tu es banni ». Aucune règle iptables/nftables.

Testé sur **Debian 13 (trixie)**, nginx en format de journal `COMBINED`.

## Les deux jails

| Jail | Déclenchement | Réglages |
|---|---|---|
| `zarisse-scans` | Une seule requête vers un chemin qui n'existe pas ici : `wp-login.php`, `/.env`, `/.git/config`, `phpmyadmin`, `eval-stdin.php`, n'importe quel `.php`, `.sql`, `.bak`… suivie d'un code 4xx/5xx | `maxretry = 1`, `bantime = 7d` |
| `zarisse-cadence` | Plus de **30 pages HTML en 60 secondes** depuis la même IP, quel que soit le user-agent | `maxretry = 30`, `findtime = 60`, `bantime = 7d` |

Le choix de la cadence plutôt que du user-agent est volontaire : un aspirateur qui
ment sur son user-agent (il se présente en Firefox) est attrapé quand même, tandis
qu'un robot bien élevé qui lit une page par minute ne gêne personne.

### Ce qui n'est jamais compté

- **Le flux RSS et ses à-côtés** : `feed_rss_*.xml`, `feed_json_*.json`, `rss.xsl`,
  `robots.txt`, `sitemap*`. Un robot peut lire le flux aussi souvent qu'il veut sans
  jamais se faire bannir. C'est la règle demandée.
- **Les ressources statiques** : CSS, JS, images, polices, images de partage. Seules
  les **pages** comptent — celles qui finissent par `/` ou par `.html`. Un visiteur
  humain charge beaucoup de fichiers d'un coup, ce n'est pas suspect.
- **Les moteurs de recherche** : Googlebot, Google-InspectionTool, Storebot-Google,
  bingbot, BingPreview, DuckDuckBot, Qwantify, Applebot. Sans eux, le blog
  disparaîtrait des résultats de recherche.
- **Les aperçus du fédivers et des messageries** : Mastodon, Pleroma, Akkoma,
  Misskey, Firefish, Iceshrimp, Friendica, Lemmy, Mbin, PeerTube, Synapse (Matrix),
  Discordbot, Slackbot, TelegramBot, Signal, WhatsApp, facebookexternalhit,
  Twitterbot, `http.rb`. Sans eux, un lien posté sur tech.lgbt s'afficherait sans
  titre ni image.
- **Les lecteurs de flux** : Nextcloud-News, Tiny Tiny RSS, FreshRSS, Feedbin,
  NetNewsWire, Miniflux, Liferea, Akregator.

Les robots d'IA (GPTBot, CCBot, ClaudeBot, Bytespider…) et les robots de
référencement commercial (AhrefsBot, SemrushBot…) ne sont **pas** dans ces listes :
ils sont bannis dès qu'ils dépassent la cadence, et ils peuvent lire le flux RSS.

## Installation

Ces fichiers vivent ici, sur le PC. Il faut les envoyer sur le serveur, puis les
installer en root **sur le serveur** — c'est là que tournent fail2ban et nginx.

```bash
# 1. Envoyer le dossier sur le serveur (depuis le PC)
rsync -av /home/melissandre/zarisse.fr/outils/fail2ban_crawlers meli@192.168.1.13:/home/meli/

# 2. Se connecter
ssh meli@192.168.1.13

# 3. Mesurer AVANT d'installer : combien d'IP seraient bannies dans les journaux existants
cd ~/fail2ban_crawlers && sudo ./installer.sh --tester

# 4. Si la liste ne contient aucune IP qui t'appartient : installer
sudo ./installer.sh
```

**Avec `bash`, pas avec `sh`.** Le script utilise des tableaux et `BASH_SOURCE` ;
lancé par `sudo sh installer.sh`, dash (le `sh` de Debian) répond `Bad substitution`.
Le script se relance maintenant tout seul sous bash si ça arrive, mais `sudo
./installer.sh` ou `sudo bash installer.sh` sont les formes correctes.

L'étape 3 n'installe rien. Elle passe les filtres sur `access.log` et ses archives
`.gz`, et affiche les IP qui **correspondent** à chaque filtre. Attention à la
lecture, elle n'est pas la même pour les deux jails :

- **`zarisse-scans`** : `maxretry = 1`, donc une correspondance = un ban. Un total
  élevé (quelques dizaines) est normal et sain, ce sont les scanners.
- **`zarisse-cadence`** : le filtre compte **toute requête de page**, donc chaque
  visiteuse humaine apparaît dans la liste. Le ban n'arrive qu'à 30 pages en 60
  secondes. Ce total est donc le nombre de visiteuses distinctes, **pas** le nombre
  de bans à venir.

C'est le moment de repérer un faux positif évident sur `zarisse-scans`, avant qu'il
ne coûte une semaine de blocage à quelqu'un.

### Désinstallation

```bash
sudo ./installer.sh --desinstaller
sudo truncate -s 0 /etc/nginx/banned_ips.conf && sudo systemctl reload nginx  # débannir tout
```

## Surveillance

```bash
sudo fail2ban-client status zarisse-scans
sudo fail2ban-client status zarisse-cadence
sudo tail -f /var/log/fail2ban.log
grep -c . /etc/nginx/banned_ips.conf                      # nombre d'IP bannies
sudo fail2ban-client set zarisse-cadence unbanip <ip>     # débannir une IP
```

## Réglage de la cadence

`maxretry = 30` dans `jail.d/zarisse-crawlers.local` est le seul chiffre à ajuster.

- **30 pages/minute** : une lectrice humaine n'y arrive pas, même en cliquant vite.
- **15** pour durcir, si des aspirateurs passent encore sous le radar.
- **60** si un faux positif apparaît — par exemple un lecteur de flux inconnu ou un
  service d'archivage légitime.

Après modification : `sudo fail2ban-client reload`.

## Points d'attention

- **Tu ne peux pas tester depuis le réseau local.** `outils/nginx/exclure_lan_nginx.py`
  exclut le LAN des journaux d'accès nginx : tes propres requêtes ne sont jamais
  enregistrées, donc jamais comptées ni bannies. C'est une protection, mais ça veut
  dire qu'un test doit venir de l'extérieur (partage de connexion du téléphone) ou
  passer par `fail2ban-regex` sur un journal d'exemple.
- **La liste blanche de user-agents est falsifiable.** Un aspirateur qui se présente
  en « Googlebot » échappe à la jail de cadence. La jail `zarisse-scans`, elle, ne
  regarde pas le user-agent, donc elle l'attrape s'il cherche des failles. Pour
  fermer complètement ce trou, il faudrait vérifier le reverse DNS des IP qui se
  déclarent Googlebot ; ce n'est pas fait ici.
- **Les bans s'accumulent dans un fichier nginx.** `banned_ips.conf` est lu à chaque
  reload : les IP restent bloquées même si fail2ban est arrêté. Avec 7 jours de ban,
  le fichier se vide tout seul au fur et à mesure des débans.
- **Un faux positif coûte 7 jours.** C'est le prix du « très restrictif » demandé.
  La commande `unbanip` ci-dessus le corrige en une seconde.

## Vérification des expressions régulières

`exemples/access-test.log` contient 19 lignes de journal représentatives : visiteuse
humaine, Googlebot, aperçu Mastodon, Discordbot, GPTBot sur le flux RSS, Scrapy,
`python-requests`, et six scans d'attaque. Il sert à vérifier un filtre après
modification, sans rien installer :

```bash
sudo fail2ban-regex exemples/access-test.log filter.d/zarisse-scans.conf
sudo fail2ban-regex exemples/access-test.log filter.d/zarisse-cadence.conf
```

Résultat attendu : `zarisse-scans` retient les 6 lignes de scan et rien d'autre ;
`zarisse-cadence` retient les pages de la visiteuse humaine, de ClaudeBot, de Scrapy
et de `python-requests`, mais ignore Googlebot, Mastodon, Discordbot, le flux RSS et
les ressources statiques.

## Fichiers

| Fichier | Rôle |
|---|---|
| `filter.d/zarisse-scans.conf` | Filtre : chemins de scan suivis d'un 4xx/5xx |
| `filter.d/zarisse-cadence.conf` | Filtre : requêtes de pages, hors flux RSS et robots autorisés |
| `jail.d/zarisse-crawlers.local` | Les deux jails, avec `banaction = nginx-geo-ban` |
| `installer.sh` | Installation, mesure (`--tester`) et désinstallation, en root sur le serveur |
| `exemples/access-test.log` | Journal d'exemple pour vérifier les filtres |
