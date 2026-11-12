function commentaires_on --description "Réactive les commentaires du blog : supprime le fichier interrupteur sur le serveur (effet immédiat, sans redémarrage)"
    ssh meli@192.168.1.13 'rm -f ~/contact/commentaires.desactives && echo "Commentaires réactivés."'
end
