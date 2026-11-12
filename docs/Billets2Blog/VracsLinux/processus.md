---
date:
  created: 2026-11-10 16:08
  updated: 2026-11-10 21:02
weight: -202611101608
---

# Surveillance des processus

1. **ps (Process Status)** : cette commande affiche des informations sur les processus en cours d'exécution. Vous pouvez utiliser `ps aux` pour voir tous les processus en cours, ou `ps -ef | grep nom_du_programme` pour ne voir que celui qui vous intéresse.

2. **lsof (List Open Files)** : cette commande liste tous les fichiers ouverts par un processus, y compris les bibliothèques chargées. Vous pouvez utiliser `lsof -p PID` pour voir les fichiers ouverts par un processus donné, où `PID` est son identifiant.

3. **strace (System Trace)** : cette commande suit les appels système effectués par un processus. Vous pouvez utiliser `strace -p PID` pour suivre un processus en cours, ou `strace nom_du_programme` pour suivre un programme au lancement.

4. **ltrace (Library Trace)** : cette commande suit les appels de bibliothèque effectués par un processus. Vous pouvez utiliser `ltrace -p PID` pour suivre un processus en cours, ou `ltrace nom_du_programme` pour suivre un programme au lancement.

5. **ldd (List Dynamic Dependencies)** : cette commande affiche les bibliothèques dynamiques utilisées par un exécutable. Vous pouvez utiliser `ldd nom_du_programme` pour voir les bibliothèques d'un programme.

6. **objdump (Object File Dumper)** : cette commande affiche des informations détaillées sur un fichier exécutable, y compris les bibliothèques utilisées. Vous pouvez utiliser `objdump -x nom_du_programme` pour voir ces informations sur un programme.