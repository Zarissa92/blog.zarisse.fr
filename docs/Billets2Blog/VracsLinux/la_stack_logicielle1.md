---
date:
  created: 2026-11-08 17:07
  updated: 2026-11-08 17:47
weight: -202611081707
---
# Ma stack logicielle, partie 1

[Ici](La_stack_logicielle.md) je définis ce que j'utilise comme logiciels sur ce serveur.
On peut dire que ce premier billet était un sommaire, pour les suivants.
Dans ce billet, je vais expliciter mes choix, sauf certains qui semblent évidents, comme OpenSSH ou fail2ban.

## Debian

![Logo de Debian](https://commons.wikimedia.org/wiki/Special:FilePath/Openlogo-debianV2.svg?width=150)

Pourquoi Debian ? Déjà ce qu'il faut savoir avec Debian, c'est que chaque version porte le nom d'un personnage de la franchise d'animation "Toy Story". Donc déjà ça fait un point, non ?

En vrai, Debian c'est un peu la reine d'un groupe élargi de distributions Linux. C'est la "maman" d'Ubuntu, et donc la grand-mère de Linux Mint, pour ne citer que ces deux-là.

Debian a une philosophie aussi qui n'est pas la même que des distros en vogue comme Arch Linux ou openSUSE. Debian a un cycle logiciel lent, on ne cherche pas la dernière version de chaque logiciel ou librairie, mais plutôt la stabilité.

Et quand on fait tourner un site autohébergé, ça c'est ce que l'on cherche, de la stabilité.

De base, Debian vient aussi sans logiciels propriétaires, même s'ils sont disponibles à l'installation. Il n'y a aucun souci avec ça.
Ça en fait une distribution de base, légère et épurée.

Dans ses dépôts sont disponibles la plupart des logiciels dont on a besoin pour faire de l'autohébergement.

D'un point de vue pratique, le gestionnaire de paquets est lui aussi très user friendly, je trouve. Et la philosophie restreinte fait que l'on n'en a pas plusieurs à gérer _(coucou YaY, AUR)_

Bref, je pense que je n'ai rien à dire sur le plan technique pour justifier mon choix. Sauf que Debian est légère, épurée, et a tout ce qu'il faut pour faire un serveur un minimum sécurisé.

## Zensical et Python

Alors pourquoi ai-je choisi Zensical ?

L'actu va me donner raison, mais pour des raisons de sécurité et de simplicité aussi, je ne voulais pas de PHP sur mon système et surtout pas d'une base de données complète, comme MariaDB ou MySQL, ni même SQLite.

Avec Zensical, on a un site statique. C'est-à-dire que vous générez des fichiers HTML et ce qui va avec (CSS, JS), et vous déployez comme vous voulez, avec Rsync, scp ou SFTP. Je trouve ce logiciel pour le moment et à la vue de mon besoin très satisfaisant. Il est simple, on écrit ses billets ou ses pages en Markdown, et on organise son arborescence avec des dossiers et des sous-dossiers. C'est juste génial, pour le long terme.

Car si je veux perdurer dans mes écrits futurs, il ne faut pas que la dette technique soit lourde. Je ne suis pas informaticienne, ce n'est pas mon job. J'ai juste le besoin de m'exprimer.

## Tailscale

![Logo de Tailscale](https://commons.wikimedia.org/wiki/Special:FilePath/Tailscale-Logo-Black.svg?width=250)

Ici ça coince un peu. C'est un logiciel qui se comporte comme WireGuard, mais en mode pour les débutants. Débutants pas trop quand même. Le gros avantage est d'avoir en deux trois clics un réseau virtuel partagé, et de confiance avec des contacts, et ça simplement, sans déployer un service WireGuard, et donc sans maintenance.

![Logo de WireGuard](https://commons.wikimedia.org/wiki/Special:FilePath/Logo_of_WireGuard.svg?width=300)

Il faut néanmoins que maintenant je me renseigne sur Headscale, qui permet d'assurer une compatibilité en mode "open source".

Voila, fin de mon premier billet. ou plutot de mon ode à debian. 

o7