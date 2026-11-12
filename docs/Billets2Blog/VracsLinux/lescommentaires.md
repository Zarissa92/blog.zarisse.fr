---
date:
  created: 2026-11-11 18:00
  updated: 2026-11-11 18:45
weight: -202611111800
---
# Des commentaires sous les articles, sans JavaScript ni service tiers

Ce blog est un site statique : il n'a pas de base de données, pas de moteur, et chaque page est un fichier HTML généré une fois pour toutes. Ajouter des commentaires, c'est justement ce qui ne rentre pas dans ce modèle. Ce billet raconte comment j'ai fait quand même, et pourquoi j'ai fait ces choix. Le code a été écrit avec un assistant (Claude), que j'ai dirigé et relu ; les décisions sont les miennes.

## Le principe

- Sous chaque article, un formulaire : pseudo facultatif, message, et une petite question anti-robot.
- Pas de JavaScript, donc pas de script tiers, pas de reCAPTCHA, pas de service qui reçoit les commentaires à ma place.
- Les commentaires sont **validés à la main** : rien ne s'affiche sans que je le décide.
- Je peux **tout couper d'une commande**, et tout remettre de même.

## L'architecture

Trois morceaux, tous sur mon serveur :

1. **Un petit script Python** (`contact.py`), qui n'utilise que la bibliothèque standard. Il écoute sur la machine seulement, derrière nginx, et il sert à la fois le formulaire de contact d'un autre site et les commentaires de celui-ci.
2. **Des fichiers texte en attente.** Quand quelqu'un écrit un commentaire, le script crée un fichier `.txt` dont la première ligne est `valide: 0`. Pour publier, je remplace le 0 par un 1. C'est mon seul outil de modération, et il est volontairement simple.
3. **Une base SQLite.** Un timer systemd lance l'import toutes les 5 minutes : les commentaires validés entrent dans la base, et leur fichier est supprimé. Une fois en base, un commentaire ne vit plus que là.

Pour l'affichage, il n'y a pas de rebuild. Chaque article contient une ligne spéciale, une **directive SSI** : nginx la remplace, au moment où la page est servie, par la liste des commentaires validés et le formulaire. Un commentaire validé apparaît donc sans reconstruire le blog. La section prend toute la largeur de l'article, et sa mise en forme est dans la feuille de style du thème.

## Couper les commentaires

Il suffit d'une commande. Un fichier interrupteur sur le serveur : tant qu'il existe, la section disparaît sous les articles, y compris les commentaires déjà validés, et les envois sont refusés. Je le crée ou je le supprime depuis mon poste, sans redémarrer quoi que ce soit : le script vérifie le fichier à chaque requête. Pendant la coupure, les commentaires déjà en base restent en base ; ils reviennent quand je réactive.

## Les choix de sécurité

- **Origine vérifiée** : un envoi venu d'un autre site que le blog est refusé.
- **Question anti-robot** : une addition, signée côté serveur. La réponse n'est pas lisible dans la page, et la question expire au bout d'une heure. C'est simple, et ça arrête les robots les plus bêtes. Ça n'arrêtera pas un robot conçu pour ça : je l'assume.
- **Champ piège** : un champ caché que les humains ne voient pas. S'il est rempli, c'est un robot, et l'envoi est ignoré.
- **Limite d'envois** : cinq par visiteur sur dix minutes.
- **Taille et format** : 8 Ko maximum, format de formulaire imposé, champs nettoyés des caractères de contrôle.
- **En-têtes de sécurité** sur toutes les réponses du script.

## L'adresse IP : ce que je garde, et pourquoi

C'est le point le plus sensible, et je préfère le dire clairement.

Chaque envoi enregistre l'adresse IP de son auteur, pour pouvoir agir en cas de contenu haineux ou de harcèlement. **Elle est effacée automatiquement après 60 jours**, dans la base comme dans les fichiers en attente. Le message, lui, reste. Si vous écrivez un jour un commentaire ici, sachez que je peux voir l'adresse qui l'a envoyé pendant ces 60 jours, et que la base ne la garde pas au-delà.

Les journaux de nginx, eux, gardent les adresses comme ils le font pour tout le serveur : ce n'est pas le script qui les gère, et la règle des 60 jours ne les concerne pas.

## Ce qui m'a fait perdre du temps

Ces erreurs sont les plus instructives, donc je les note.

- **La directive SSI ne fonctionne pas sans `ssi on;`** dans le bon bloc du serveur. Sans cette ligne, la directive reste un commentaire HTML invisible : la page ne casse pas, mais rien ne s'affiche.
- **nginx ne lit pas `sites-available/`, mais `sites-enabled/`.** Sur mon serveur, le second était une copie figée, si bien que mes modifications n'étaient jamais chargées, et la route renvoyait un 404. Un script de déploiement qui modifie le « mauvais » fichier, c'est facile à faire et difficile à voir. Depuis, il vérifie que le lien est bien en place.
- **Un nom de variable inventé dans un gabarit.** J'ai écrit `page.file.src_uri`, qui n'existe pas dans Zensical. Le build a échoué, et heureusement : c'est lui qui l'a signalé, avant la publication. La bonne variable est `page.url`. Et les pages d'index, qui ont aussi une date, ont dû être exclues à part, par le repère qu'elles contiennent.
- **Deux blocs pour le même domaine.** Le domaine apparaissait deux fois dans la configuration nginx : un bloc HTTPS et un bloc port 80 qui renvoie 404. Mon premier script ne savait pas les distinguer, et il a eu raison de s'arrêter.

## Ce qui reste à faire

- Un **panneau d'administration**, pour valider sans ouvrir de fichiers. Ce n'est pas urgent : la validation à la main reste simple tant qu'il y a peu de commentaires.
- Vérifier que le dossier des commentaires est bien couvert par la sauvegarde nocturne. Ce n'est pas encore fait.
- Décider si les commentaires jamais validés doivent être supprimés au bout d'un certain temps.

Si vous voulez écrire un commentaire, il est sous n'importe quel article. Je le lirai, et je le publierai si je le trouve à sa place.
