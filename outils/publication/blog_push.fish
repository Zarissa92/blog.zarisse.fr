function blog_push --description "Synchronise zarisse/site/ vers meli@192.168.1.13:/home/meli/blog/ (rsync --delete). Arguments supplémentaires passés à rsync, ex: blog_push --dry-run"
    set -l src /home/melissandre/zarisse.fr/site/
    set -l dest meli@192.168.1.13:/home/meli/blog/

    if not test -d $src
        echo "Source introuvable : $src" >&2
        return 1
    end

    # --checksum : compare le contenu des fichiers, pas leur date. build.py réécrit tout site/
    # (nouvelles dates partout) : sans cette option, rsync renvoie tous les fichiers à chaque fois.
    # --exclude : ne jamais publier les fichiers cachés (site/.git, .directory de Dolphin…).
    # --delete-excluded : les retire aussi du serveur s'ils y ont déjà été envoyés.
    rsync -avz --checksum --delete --delete-excluded --exclude='.*' --human-readable --progress $argv $src $dest
end
