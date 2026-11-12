function commentaires_off --description "Désactive les commentaires du blog : crée le fichier interrupteur sur le serveur (effet immédiat, sans redémarrage)"
    ssh meli@192.168.1.13 'touch ~/contact/commentaires.desactives && echo "Commentaires désactivés." && ls -l ~/contact/commentaires.desactives'
end
