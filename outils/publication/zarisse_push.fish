function zarisse_push --description "Synchronise 'INdex>HTML' vers meli@192.168.1.13:/home/meli/html/ (rsync --delete). Arguments supplémentaires passés à rsync, ex: zarisse_push --dry-run"
    # Le nom du dossier contient un « > » : il doit rester entre guillemets partout,
    # sinon fish y voit une redirection.
    set -l src "/home/melissandre/zarisse.fr/INdex>HTML/"
    set -l dest meli@192.168.1.13:/home/meli/html/

    if not test -d "$src"
        echo "Source introuvable : $src" >&2
        return 1
    end

    # Le site racine n'a pas de build : index.html charge contenu.md par fetch()
    # au moment de l'affichage. contenu.md doit donc être publié, ce n'est pas
    # une source de build.
    if not test -f "$src/contenu.md"
        echo "contenu.md manquant dans $src : la page s'afficherait vide." >&2
        return 1
    end

    # --checksum : compare le contenu des fichiers, pas leur date, comme blog_push.
    # --exclude : ne jamais publier les fichiers cachés (.directory de Dolphin…).
    # --delete-excluded : les retire aussi du serveur s'ils y ont déjà été envoyés.
    rsync -avz --checksum --delete --delete-excluded --exclude='.*' --human-readable --progress $argv "$src" $dest
end
