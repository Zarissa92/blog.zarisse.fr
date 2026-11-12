---
date: 2026-11-11
categories:
  - Linux
  - Réseau
tags:
  - ssh
  - tunnel
  - debian
weight: -202611110625
---

# Tunnel SSH local : accéder à un service sans l'exposer sur Internet

SSH, on s'en sert surtout pour ouvrir un shell sur une machine distante. Mais il sait aussi transporter du trafic réseau dans sa connexion chiffrée : c'est le **port forwarding**, ou **tunnel SSH**.

Le cas d'usage le plus courant, et celui de cet article, c'est le **forwarding local** (`ssh -L`). Il répond à une situation que tout admin connaît : un service tourne sur le serveur (interface web d'admin, base de données, outil de monitoring…), il n'écoute qu'en local, et c'est très bien comme ça. Mais de temps en temps, on aimerait bien l'ouvrir dans son navigateur.

Plutôt que d'ouvrir un port sur le pare-feu, on fait passer la connexion dans SSH. Le seul port exposé reste le 22.

<!-- more -->

## Le principe

On note :

- `poste` : ta machine, celle où tu tapes la commande ;
- `serveur` : la machine sur laquelle tu te connectes en SSH (`user@serveur`).

```text
 poste                         serveur                     cible
┌──────────────┐   tunnel   ┌──────────────┐           ┌───────────┐
│ localhost:8080 ═══════════▶│     sshd     │──────────▶│ host:port │
└──────────────┘    SSH     └──────────────┘           └───────────┘
```

Un port s'ouvre **sur ton poste**. Tout ce qui y entre traverse le tunnel chiffré, ressort **côté serveur**, et le serveur se connecte à la cible.

Syntaxe :

```bash
ssh -L [adresse_locale:]port_local:hôte_cible:port_cible user@serveur
```

| Morceau | Signification |
|---------|---------------|
| `adresse_locale` | facultatif, sur quelle interface du poste écouter (par défaut `127.0.0.1`) |
| `port_local` | le port à ouvrir sur ton poste |
| `hôte_cible` | la machine à atteindre, **vue depuis le serveur** |
| `port_cible` | le port du service sur la cible |

!!! warning "Le piège classique"
    `hôte_cible` est résolu **depuis le serveur**, pas depuis ton poste.
    Donc `localhost` dans la partie cible veut dire « le serveur lui-même ».

---

## Premier tunnel : une interface web qui n'écoute qu'en local

Tu as sur ton serveur un service d'admin (Syncthing, Grafana, phpMyAdmin…) qui écoute sur `127.0.0.1:8384`. Vérifions-le sur le serveur :

```bash
ss -ltn | grep 8384
# LISTEN 0  4096  127.0.0.1:8384  0.0.0.0:*
```

`127.0.0.1` : il n'est joignable que depuis le serveur lui-même. Depuis ton poste :

```bash
ssh -L 8384:localhost:8384 user@serveur
```

Tant que la session est ouverte, ouvre `http://localhost:8384` dans le navigateur de ton poste : tu arrives sur l'interface du serveur, à travers le tunnel.

Le port local n'a pas besoin d'être identique au port distant :

```bash
ssh -L 9000:localhost:8384 user@serveur
# → http://localhost:9000
```

!!! tip "Choisir le port local"
    Prends un port libre au-dessus de 1024 : en dessous, il faut les droits root.

---

## Atteindre une machine derrière le serveur

La cible n'est pas forcément le serveur lui-même. Elle peut être n'importe quelle machine que **le serveur** sait joindre, par exemple un NAS ou une imprimante sur son réseau local en `192.168.1.50` :

```bash
ssh -L 8443:192.168.1.50:443 user@serveur
```

`https://localhost:8443` sur ton poste → l'interface du NAS, alors que ton poste n'a aucune route vers `192.168.1.50`.

Le serveur sert de **rebond**. Entre le serveur et la cible, le trafic n'est plus chiffré par SSH : c'est le protocole d'origine (ici HTTPS, donc ça va).

---

## Une base de données, pas seulement du web

Le tunnel transporte n'importe quel flux TCP. Exemple avec PostgreSQL qui écoute en local sur le serveur :

```bash
ssh -N -L 5433:localhost:5432 user@serveur
```

Puis depuis le poste, avec ton client habituel :

```bash
psql -h localhost -p 5433 -U utilisateur_bdd ma_base
```

On utilise `5433` côté poste pour ne pas entrer en conflit avec un éventuel PostgreSQL local. Même chose pour MariaDB (`3306`), Redis (`6379`), etc.

---

## Plusieurs tunnels d'un coup

On peut empiler les `-L` :

```bash
ssh -N \
  -L 8384:localhost:8384 \
  -L 3000:localhost:3000 \
  -L 5433:localhost:5432 \
  user@serveur
```

Une seule connexion SSH, trois services accessibles.

---

## Options pratiques

| Option | Rôle |
|--------|------|
| `-N` | n'exécute aucune commande : juste le tunnel, pas de shell |
| `-f` | passe en arrière-plan après l'authentification |
| `-T` | pas de pseudo-terminal |
| `-o ExitOnForwardFailure=yes` | échoue franchement si le port local est déjà pris |

Tunnel en tâche de fond :

```bash
ssh -fNT -o ExitOnForwardFailure=yes -L 8384:localhost:8384 user@serveur
```

Le retrouver et le couper :

```bash
ss -ltnp | grep 8384          # quel processus tient le port ?
pkill -f "L 8384:localhost"   # le fermer
```

---

## Partager le tunnel avec ton réseau local

Par défaut, le port ouvert sur le poste écoute sur `127.0.0.1` : seul ton poste peut l'utiliser. Pour qu'une autre machine de ton réseau (une tablette, un autre PC) s'en serve aussi, précise l'adresse d'écoute :

```bash
ssh -N -L 0.0.0.0:8384:localhost:8384 user@serveur
```

!!! danger "À utiliser en connaissance de cause"
    N'importe quelle machine qui peut joindre ton poste accède alors au service distant, sans passer par l'authentification SSH.
    Sur un Wi-Fi public, c'est non.

Le même effet s'obtient avec `-g`, mais l'adresse explicite est plus lisible.

---

## Tout ranger dans `~/.ssh/config`

Retaper ces options à chaque fois devient vite pénible. On les déclare une fois pour toutes dans `~/.ssh/config` sur le poste :

```text
Host serveur
    HostName serveur.exemple.fr
    User user
    IdentityFile ~/.ssh/id_ed25519

Host tunnel-admin
    HostName serveur.exemple.fr
    User user
    IdentityFile ~/.ssh/id_ed25519
    LocalForward 8384 localhost:8384
    LocalForward 3000 localhost:3000
    LocalForward 5433 localhost:5432
    SessionType none
    ExitOnForwardFailure yes
    ServerAliveInterval 30
    ServerAliveCountMax 3
```

Ensuite, une seule commande :

```bash
ssh -f tunnel-admin
```

| Directive | Équivalent CLI | Rôle |
|-----------|----------------|------|
| `LocalForward` | `-L` | déclare un tunnel local |
| `SessionType none` | `-N` | pas de shell |
| `ExitOnForwardFailure yes` | `-o …` | échoue si un port est déjà pris |
| `ServerAliveInterval` | `-o …` | garde la connexion en vie, détecte les coupures |

!!! info "Version d'OpenSSH"
    `SessionType` existe depuis OpenSSH 8.7. Sur une version plus ancienne, garde `-N` en ligne de commande.

---

## Un tunnel toujours ouvert avec systemd

Si tu utilises ces tunnels tous les jours, autant qu'ils se montent tout seuls à l'ouverture de session et se relancent en cas de coupure. Avec le `Host tunnel-admin` défini plus haut :

```ini title="~/.config/systemd/user/tunnel-admin.service"
[Unit]
Description=Tunnels SSH locaux vers le serveur
After=network-online.target
Wants=network-online.target

[Service]
ExecStart=/usr/bin/ssh -N tunnel-admin
Restart=always
RestartSec=10

[Install]
WantedBy=default.target
```

```bash
systemctl --user daemon-reload
systemctl --user enable --now tunnel-admin.service
systemctl --user status tunnel-admin.service
```

`Restart=always` relance le tunnel s'il tombe : pas besoin d'`autossh`.

!!! note "Et la passphrase ?"
    Un service ne peut pas taper ta passphrase. Soit ta clé est chargée dans un `ssh-agent` accessible à la session, soit tu crées une clé dédiée sans passphrase, **restreinte côté serveur** comme expliqué juste après.

---

## Côté serveur : autoriser et restreindre

Le forwarding local est autorisé par défaut dans OpenSSH. On peut le régler dans `/etc/ssh/sshd_config` (ou mieux, un fichier dans `/etc/ssh/sshd_config.d/`) :

```text
AllowTcpForwarding local      # yes | no | local | remote
PermitOpen localhost:8384 localhost:3000 localhost:5432
```

- `AllowTcpForwarding local` autorise `-L` mais pas `-R` ;
- `PermitOpen` liste les seules cibles autorisées. Un `-L` vers autre chose sera refusé.

On peut aussi restreindre **par clé**, dans `~/.ssh/authorized_keys` du serveur. Exemple d'une clé qui ne sert qu'à ouvrir les tunnels admin, et rien d'autre :

```text
restrict,port-forwarding,permitopen="localhost:8384",permitopen="localhost:3000",permitopen="localhost:5432" ssh-ed25519 AAAA... tunnel-admin
```

- `restrict` coupe tout (shell, agent, X11, forwarding…) ;
- `port-forwarding` rouvre uniquement le forwarding ;
- `permitopen` limite les cibles autorisées.

Si cette clé fuit, on ne peut rien en faire d'autre qu'ouvrir ces trois tunnels. C'est la bonne pratique pour toute clé sans passphrase.

Après modification de `sshd_config` :

```bash
sudo sshd -t && sudo systemctl reload ssh
```

`sshd -t` vérifie la syntaxe avant de recharger : pratique pour ne pas se couper l'accès.

---

## Dépannage

**`bind [127.0.0.1]:8384: Address already in use`**
Le port local est déjà pris, souvent par un ancien tunnel resté ouvert :

```bash
ss -ltnp | grep 8384
```

**`channel 2: open failed: connect failed: Connection refused`**
Le tunnel fonctionne, mais rien n'écoute sur la cible. Vérifie l'hôte et le port **vus depuis le serveur** : sur le serveur, `ss -ltn` doit montrer le service.

**`channel 2: open failed: administratively prohibited: open failed`**
Le serveur refuse ce forwarding : regarde `AllowTcpForwarding`, `PermitOpen`, ou les options de la clé dans `authorized_keys`.

**La page charge mais redirige vers une autre adresse**
Certaines applications web redirigent vers leur URL « officielle » (nom de domaine, port d'origine). Utilise le même port local que le port distant, ou règle l'URL de base de l'application.

**Pour tout le reste :** le mode verbeux.

```bash
ssh -v -N -L 8384:localhost:8384 user@serveur
```

---

## Pour aller plus loin : les autres modes

Le forwarding local couvre la majorité des besoins, mais SSH en propose deux autres, plus un raccourci bien pratique. Pour s'y retrouver, une règle simple : **la lettre indique où le port s'ouvre**.

### Forwarding distant (`-R`)

C'est le miroir de `-L` : le port s'ouvre **sur le serveur**, et le trafic revient vers une cible **vue depuis ton poste**.

```bash
ssh -N -R 9000:localhost:3000 user@serveur
```

Sur le serveur, `localhost:9000` mène au site qui tourne sur `localhost:3000` de ton poste.

L'usage typique, c'est le **reverse tunnel** : une machine chez toi, injoignable depuis Internet (pas de redirection de port, CGNAT…), ouvre elle-même un tunnel vers ton serveur public :

```bash
# lancé depuis la machine à la maison
ssh -N -R 2222:localhost:22 user@serveur
```

Depuis le serveur, `ssh -p 2222 user_maison@localhost` te ramène à la maison. Pour que ce port soit joignable depuis l'extérieur, il faut `GatewayPorts` côté `sshd`, mais un reverse proxy devant est souvent plus sûr.

### Forwarding dynamique (`-D`)

Au lieu d'un tunnel vers **une** cible fixe, `-D` ouvre sur ton poste un **proxy SOCKS5** :

```bash
ssh -N -D 1080 user@serveur
```

Configure ton navigateur pour utiliser le proxy SOCKS5 `127.0.0.1:1080`, avec le DNS distant activé, et toute ta navigation sort avec l'adresse IP du serveur. Pour vérifier :

```bash
curl --socks5-hostname 127.0.0.1:1080 https://ifconfig.me
```

Un « VPN du pauvre » très efficace sur un Wi-Fi public douteux.

### Rebondir avec `ProxyJump`

Pas exactement du forwarding de port, mais de la même famille : se connecter en SSH à une machine **à travers** une autre.

```bash
ssh -J user@serveur user_nas@192.168.1.50
```

Ou dans `~/.ssh/config` :

```text
Host nas
    HostName 192.168.1.50
    User user_nas
    ProxyJump serveur
```

Et les `LocalForward` déclarés sur `nas` passent eux aussi par le rebond.

### Le mémo

```bash
# Local : mon port 8080 → cible vue depuis le serveur
ssh -N -L 8080:localhost:80 user@serveur

# Remote : port 9000 du serveur → cible vue depuis mon poste
ssh -N -R 9000:localhost:3000 user@serveur

# Dynamic : proxy SOCKS5 sur mon port 1080
ssh -N -D 1080 user@serveur

# Rebond
ssh -J user@serveur user@machine_interne
```

Avec `-L` et un `~/.ssh/config` bien rangé, la plupart des besoins « je voudrais accéder à ce truc, mais sans l'ouvrir sur Internet » sont réglés. Et quand ça ne suffit plus, `-R` et `-D` sont là.
