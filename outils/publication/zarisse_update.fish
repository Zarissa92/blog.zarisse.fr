function zarisse_update --description "Synchronise outils/contact vers le serveur, puis lance activer_ssi_blog.sh (sudo demandé sur le serveur). Avec --dry-run : simulation seule, rien n'est lancé sur le serveur"
    # Le formulaire et les commentaires (contact.py et ses fichiers) vivent dans outils/contact/.
    # Pas de --delete : rien n'est retiré du serveur.
    set -l src /home/melissandre/zarisse.fr/outils/contact/
    set -l dest meli@192.168.1.13:/home/meli/zarisse.fr/outils/contact/
    set -l distant /home/meli/zarisse.fr/outils/contact

    if not test -d $src
        echo "Source introuvable : $src" >&2
        return 1
    end

    rsync -avz --checksum --exclude='__pycache__/' --human-readable $argv $src $dest
    or return 1

    if contains -- --dry-run $argv; or contains -- -n $argv
        echo "Simulation : la commande n'est pas lancée sur le serveur."
        return 0
    end

    # -t : le terminal reste ouvert pour le mot de passe demandé par sudo.
    ssh -t meli@192.168.1.13 "cd $distant && sudo bash activer_ssi_blog.sh"
end
