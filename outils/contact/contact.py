#!/usr/bin/env python3
"""Formulaire de contact de kioske.fr et commentaires sous les articles de zarisse.fr.

Bibliothèque standard uniquement. Aucun JavaScript.
Tourne sur le Lenovo, écoute en local seulement (127.0.0.1), derrière nginx.

Lancement :
  venv_blog/bin/python contact.py            serveur (service systemd)
  venv_blog/bin/python contact.py importer   importe les commentaires validés (lancé toutes les 5 min par le timer)

Kioske.fr (/contact) :
  GET  /contact : formulaire complet, avec une question anti-robot.
  POST /contact : message enregistré dans messages.db (table messages).

Zarisse.fr (/commentaire) :
  GET  /commentaire?article=... : fragment HTML, commentaires validés + formulaire.
       Inclus dans chaque article par SSI (nginx), donc à jour sans reconstruire le blog.
  POST /commentaire : écrit un fichier texte dans commentaires/, avec « valide: 0 ».
       Pour publier : mettre « valide: 1 » dans ce fichier. Le timer importe toutes les
       5 minutes, puis supprime le fichier : le commentaire vit alors dans la base.
       Pour retirer un commentaire publié : le supprimer de la table commentaires (SQL).

Conservation : l'adresse IP est effacée après CONSERVATION_IP_JOURS jours (base et
fichiers). Le message reste. Pas de journal séparé.
Le champ « site » est un piège à robots : il doit rester vide.
"""

import contextlib
import glob
import hashlib
import hmac
import html
import os
import re
import secrets
import sqlite3
import sys
import threading
import time
from collections import defaultdict, deque
from datetime import datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs

# --- Réglages : seuls endroits à modifier ---
HOTE = "127.0.0.1"                       # jamais sur 0.0.0.0 : seul nginx doit joindre le script
PORT = 8765
DOSSIER_DONNEES = os.path.join(os.path.expanduser("~"), "contact")  # ~ = dossier de l'utilisateur qui lance le script
BASE = os.path.join(DOSSIER_DONNEES, "messages.db")
CLE = os.path.join(DOSSIER_DONNEES, "cle.secret")                   # signature du CAPTCHA
DOSSIER_COMMENTAIRES = os.path.join(DOSSIER_DONNEES, "commentaires")
COMMENTAIRES_OFF = os.path.join(DOSSIER_DONNEES, "commentaires.desactives")  # fichier présent = commentaires désactivés
CHEMIN_CONTACT = "/contact"
CHEMIN_COMMENTAIRE = "/commentaire"
ORIGINES = {                             # un envoi venu d'un autre site est refusé
    CHEMIN_CONTACT: {"https://kioske.fr"},
    CHEMIN_COMMENTAIRE: {"https://blog.zarisse.fr"},
}
TAILLE_MAX = 8 * 1024                    # octets acceptés dans le corps de la requête
PSEUDO_MAX = 40                          # caractères
MESSAGE_MAX = 2000                       # caractères
ARTICLE_MAX = 200                        # caractères (chemin de l'article dans docs/)
TEMPS_MAX_REQUETE = 5                    # secondes avant de couper une connexion lente
CONSERVATION_IP_JOURS = 60               # au-delà, l'adresse IP est effacée
ENVOIS_PAR_FENETRE = 5                   # envois acceptés par visiteur...
FENETRE_SECONDES = 600                   # ...sur cette durée (10 minutes)
VALIDITE_QUESTION = 3600                 # secondes pendant lesquelles une question reste valable
FORMAT_DATE = "%Y-%m-%d %H:%M"
IP_EFFACEE = "(effacée)"
# ---------------------------------------------

SCHEMA = """
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pseudo TEXT NOT NULL,
    message TEXT NOT NULL,
    date TEXT NOT NULL,
    ip TEXT
);
CREATE TABLE IF NOT EXISTS commentaires (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    article TEXT NOT NULL,
    pseudo TEXT NOT NULL,
    message TEXT NOT NULL,
    date TEXT NOT NULL,
    ip TEXT,
    fichier TEXT NOT NULL UNIQUE
);
"""

# Caractères de contrôle interdits (on garde tab, retour à la ligne et retour chariot).
CONTROLE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")

VERROU = threading.Lock()
ENVOIS = defaultdict(deque)  # IP -> dates des derniers envois (en mémoire seulement)
CLE_SIGNATURE = b""          # chargée au démarrage par charger_cle()


# ---------- Clé, CAPTCHA ----------

def charger_cle():
    """Lit la clé de signature, ou la crée (lisible par le seul compte du script)."""
    global CLE_SIGNATURE
    if not os.path.exists(CLE):
        with open(CLE, "wb") as f:
            f.write(secrets.token_bytes(32))
        os.chmod(CLE, 0o600)
    with open(CLE, "rb") as f:
        CLE_SIGNATURE = f.read()


def signer(expiration, reponse):
    message = f"{expiration}:{reponse}".encode()
    return hmac.new(CLE_SIGNATURE, message, hashlib.sha256).hexdigest()


def nouvelle_question():
    """Retourne (question affichée, jeton à renvoyer avec la réponse)."""
    a = secrets.randbelow(9) + 1
    b = secrets.randbelow(9) + 1
    expiration = int(time.time()) + VALIDITE_QUESTION
    jeton = f"{expiration}.{signer(expiration, a + b)}"
    return f"Combien font {a} + {b} ?", jeton


def question_valide(jeton, reponse):
    """Vrai si la réponse correspond au jeton et que le jeton n'a pas expiré."""
    try:
        expiration_txt, signature = jeton.split(".", 1)
        expiration = int(expiration_txt)
        reponse_entiere = int(reponse.strip())
    except (ValueError, AttributeError):
        return False
    if time.time() > expiration:
        return False
    return hmac.compare_digest(signature, signer(expiration, reponse_entiere))


def commentaires_actifs():
    """Faux si le fichier d'interrupteur existe : pas de section, pas d'envoi. Vérifié à chaque requête."""
    return not os.path.exists(COMMENTAIRES_OFF)


def autorise_ip(ip):
    """Vrai si ce visiteur n'a pas dépassé le nombre d'envois sur la fenêtre."""
    maintenant = time.monotonic()
    with VERROU:
        recents = ENVOIS[ip]
        while recents and maintenant - recents[0] > FENETRE_SECONDES:
            recents.popleft()
        if len(recents) >= ENVOIS_PAR_FENETRE:
            return False
        recents.append(maintenant)
        if len(ENVOIS) > 10_000:  # évite que le dictionnaire grossisse sans fin
            for cle in [k for k, v in ENVOIS.items() if not v or maintenant - v[-1] > FENETRE_SECONDES]:
                del ENVOIS[cle]
        return True


# ---------- Base SQLite et conservation ----------

@contextlib.contextmanager
def base():
    con = sqlite3.connect(BASE, timeout=5)
    try:
        con.executescript(SCHEMA)
        yield con
        con.commit()
    finally:
        con.close()


def limite_conservation(maintenant):
    """Date (texte) en deçà de laquelle une adresse IP doit être effacée."""
    return (maintenant - timedelta(days=CONSERVATION_IP_JOURS)).strftime(FORMAT_DATE)


def purger_ip(con, limite):
    con.execute("UPDATE messages SET ip = NULL WHERE ip IS NOT NULL AND date < ?", (limite,))
    con.execute("UPDATE commentaires SET ip = NULL WHERE ip IS NOT NULL AND date < ?", (limite,))


def enregistrer_message(pseudo, message, ip):
    maintenant = datetime.now().astimezone()
    with base() as con:
        purger_ip(con, limite_conservation(maintenant))
        con.execute(
            "INSERT INTO messages (pseudo, message, date, ip) VALUES (?, ?, ?, ?)",
            (pseudo, message, maintenant.strftime(FORMAT_DATE), ip),
        )


# ---------- Textes ----------

def nettoyer_ligne(texte):
    """Texte d'une seule ligne (pseudo, article) : retours à la ligne remplacés par des espaces."""
    texte = CONTROLE.sub("", texte).replace("\r", " ").replace("\n", " ")
    return texte.strip()


def nettoyer_texte(texte):
    """Texte sur plusieurs lignes (message)."""
    texte = texte.replace("\r\n", "\n").replace("\r", "\n")
    return CONTROLE.sub("", texte).strip()


def page(titre, corps):
    return f"""<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="referrer" content="no-referrer">
<title>{html.escape(titre)}</title>
</head>
<body>
<h1>{html.escape(titre)}</h1>
<p>{html.escape(corps)}</p>
<p><a href="/">Retour</a></p>
</body>
</html>
""".encode("utf-8")


def formulaire_contact(erreur=""):
    """Page complète du formulaire de kioske.fr, avec une nouvelle question anti-robot."""
    question, jeton = nouvelle_question()
    avertissement = f"<p><strong>{html.escape(erreur)}</strong></p>" if erreur else ""
    return f"""<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="referrer" content="no-referrer">
<title>Contact</title>
</head>
<body>
<h1>Écrire</h1>
{avertissement}
<form method="post" action="{CHEMIN_CONTACT}">
  <p>
    <label for="contact-pseudo">Pseudo <span>(facultatif)</span></label><br>
    <input id="contact-pseudo" name="pseudo" type="text" maxlength="{PSEUDO_MAX}" autocomplete="nickname">
  </p>
  <p>
    <label for="contact-message">Message</label><br>
    <textarea id="contact-message" name="message" rows="6" maxlength="{MESSAGE_MAX}" required></textarea>
  </p>
  <p>
    <label for="contact-reponse">{html.escape(question)}</label><br>
    <input id="contact-reponse" name="reponse" type="text" inputmode="numeric" required autocomplete="off">
  </p>
  <input type="hidden" name="jeton" value="{jeton}">
  <!-- Piège à robots : ce champ doit rester vide. Les humains ne le voient pas. -->
  <p hidden>
    <label for="contact-site">Ne pas remplir</label>
    <input id="contact-site" name="site" type="text" tabindex="-1" autocomplete="off">
  </p>
  <p>
    <button type="submit">Envoyer</button>
  </p>
</form>
<p><a href="/">Retour à kioske.fr</a></p>
</body>
</html>
""".encode("utf-8")


def fragment_commentaires(article):
    """Fragment HTML inclus dans l'article : commentaires validés, puis formulaire."""
    with base() as con:
        lignes = con.execute(
            "SELECT pseudo, message, date FROM commentaires WHERE article = ? ORDER BY date, id",
            (article,),
        ).fetchall()

    morceaux = []
    for pseudo, message, date in lignes:
        corps = html.escape(message).replace("\n", "<br>")
        morceaux.append(
            '<article class="commentaire">'
            f'<p class="commentaire-entete"><strong>{html.escape(pseudo)}</strong> · {html.escape(date)}</p>'
            f"<p>{corps}</p>"
            "</article>"
        )
    liste = "\n".join(morceaux) if morceaux else '<p class="commentaire-vide">Aucun commentaire pour l’instant.</p>'

    question, jeton = nouvelle_question()
    return f"""<section class="commentaires" id="commentaires">
<h2>Commentaires</h2>
{liste}
<h3>Laisser un commentaire</h3>
<form method="post" action="{CHEMIN_COMMENTAIRE}" class="commentaire-formulaire">
  <input type="hidden" name="article" value="{html.escape(article, quote=True)}">
  <input type="hidden" name="jeton" value="{jeton}">
  <p>
    <label for="com-pseudo">Pseudo <span>(facultatif)</span></label><br>
    <input id="com-pseudo" name="pseudo" type="text" maxlength="{PSEUDO_MAX}" autocomplete="nickname">
  </p>
  <p>
    <label for="com-message">Commentaire</label><br>
    <textarea id="com-message" name="message" rows="5" maxlength="{MESSAGE_MAX}" required></textarea>
  </p>
  <p>
    <label for="com-reponse">{html.escape(question)}</label><br>
    <input id="com-reponse" name="reponse" type="text" inputmode="numeric" required autocomplete="off">
  </p>
  <p hidden>
    <label for="com-site">Ne pas remplir</label>
    <input id="com-site" name="site" type="text" tabindex="-1" autocomplete="off">
  </p>
  <p>
    <button type="submit">Envoyer</button>
  </p>
</form>
</section>
""".encode("utf-8")


# ---------- Commentaires : fichiers texte ----------

def ecrire_commentaire(article, pseudo, message, ip):
    maintenant = datetime.now().astimezone()
    os.makedirs(DOSSIER_COMMENTAIRES, mode=0o700, exist_ok=True)
    etiquette = re.sub(r"[^A-Za-z0-9]+", "-", pseudo).strip("-")[:30] or "anonyme"
    nom = f"{maintenant:%Y-%m-%d_%H%M%S}_{etiquette}_{secrets.token_hex(3)}.txt"
    contenu = (
        "valide: 0\n"
        f"article: {article}\n"
        f"pseudo: {pseudo}\n"
        f"date: {maintenant.strftime(FORMAT_DATE)}\n"
        f"ip: {ip}\n"
        "\n"
        f"{message}\n"
    )
    with open(os.path.join(DOSSIER_COMMENTAIRES, nom), "x", encoding="utf-8") as f:
        f.write(contenu)


def lire_commentaire(chemin):
    """Retourne (champs de l'en-tête, corps du message), ou None si le format ne correspond pas."""
    with open(chemin, encoding="utf-8") as f:
        texte = f.read()
    entete, sep, corps = texte.partition("\n\n")
    if not sep:
        return None
    champs = {}
    for ligne in entete.splitlines():
        cle, sep2, valeur = ligne.partition(":")
        if sep2:
            champs[cle.strip()] = valeur.strip()
    return champs, corps.rstrip("\n")


def effacer_ip_fichier(chemin):
    """Remplace l'adresse IP de l'en-tête par « (effacée) ». Le reste du fichier ne change pas."""
    with open(chemin, encoding="utf-8") as f:
        texte = f.read()
    entete, sep, corps = texte.partition("\n\n")
    entete = re.sub(r"(?m)^ip:.*$", f"ip: {IP_EFFACEE}", entete, count=1)
    tmp = chemin + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(entete + sep + corps)
    os.replace(tmp, chemin)


def importer():
    """Enregistre en base les commentaires validés, puis supprime leur fichier.

    valide: 1 -> le commentaire est écrit dans la table commentaires, puis son fichier est supprimé.
    valide: 0 -> fichier en attente : il reste tel quel (son adresse IP est effacée après 60 jours).
    Le fichier n'est supprimé qu'après l'enregistrement en base : en cas d'erreur, il reste.
    """
    maintenant = datetime.now().astimezone()
    limite = limite_conservation(maintenant)
    publies = effaces = 0
    a_supprimer = []

    with base() as con:
        purger_ip(con, limite)
        for chemin in sorted(glob.glob(os.path.join(DOSSIER_COMMENTAIRES, "*.txt"))):
            nom = os.path.basename(chemin)
            lu = lire_commentaire(chemin)
            if lu is None:
                print(f"ignoré (format non reconnu) : {nom}", file=sys.stderr)
                continue
            champs, corps = lu
            date = champs.get("date", "")
            ip = champs.get("ip", "")
            ip_base = ip if re.fullmatch(r"[0-9a-fA-F.:]+", ip) else None

            if champs.get("valide") == "1":
                con.execute(
                    """INSERT INTO commentaires (article, pseudo, message, date, ip, fichier)
                       VALUES (?, ?, ?, ?, ?, ?)
                       ON CONFLICT(fichier) DO UPDATE SET
                           article = excluded.article,
                           pseudo = excluded.pseudo,
                           message = excluded.message,
                           date = excluded.date,
                           ip = COALESCE(excluded.ip, commentaires.ip)""",
                    (champs.get("article", ""), champs.get("pseudo", "anonyme") or "anonyme",
                     corps, date, ip_base, nom),
                )
                publies += 1
                a_supprimer.append(chemin)
                continue

            # Fichier en attente, ancien : on efface l'adresse IP qu'il contient encore.
            if ip and ip != IP_EFFACEE and date and date < limite:
                effacer_ip_fichier(chemin)
                effaces += 1

    # Les fichiers validés ne sont supprimés qu'une fois la base enregistrée.
    for chemin in a_supprimer:
        os.remove(chemin)

    print(f"commentaires publiés : {publies} (fichiers supprimés) · adresses IP effacées dans les fichiers en attente : {effaces}")


# ---------- Serveur HTTP ----------

class Gestionnaire(BaseHTTPRequestHandler):
    server_version = "contact"      # ne pas révéler la version de Python
    sys_version = ""
    timeout = TEMPS_MAX_REQUETE     # coupe les connexions qui traînent (anti-lenteur)

    def log_message(self, format, *args):
        # Pas de journal : aucune trace des visiteurs côté script.
        return

    def _repondre(self, code, corps):
        self.send_response(code)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(corps)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Security-Policy", "default-src 'none'; style-src 'none'; frame-ancestors 'none'")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        self.end_headers()
        self.wfile.write(corps)

    def do_GET(self):
        chemin, _, requete = self.path.partition("?")
        if chemin == CHEMIN_CONTACT:
            self._repondre(200, formulaire_contact())
            return
        if chemin == CHEMIN_COMMENTAIRE:
            if not commentaires_actifs():
                self._repondre(200, b"")  # rien à afficher sous l'article
                return
            article = nettoyer_ligne(parse_qs(requete).get("article", [""])[0])
            if not 1 <= len(article) <= ARTICLE_MAX:
                self._repondre(400, b"")
                return
            self._repondre(200, fragment_commentaires(article))
            return
        self._repondre(404, page("Introuvable", "Cette adresse n'existe pas."))

    def do_POST(self):
        chemin = self.path.partition("?")[0]
        if chemin not in ORIGINES:
            self._repondre(404, page("Introuvable", "Cette adresse n'existe pas."))
            return

        origine = self.headers.get("Origin")
        if origine is not None and origine not in ORIGINES[chemin]:
            self._repondre(403, page("Envoi refusé", "Ce formulaire n'accepte pas les envois depuis ce site."))
            return

        if chemin == CHEMIN_COMMENTAIRE and not commentaires_actifs():
            self._repondre(503, page("Commentaires fermés", "Les commentaires sont désactivés pour le moment."))
            return

        type_contenu = (self.headers.get("Content-Type") or "").split(";")[0].strip().lower()
        if type_contenu != "application/x-www-form-urlencoded":
            self._repondre(415, page("Format refusé", "Envoie le formulaire tel quel, sans format particulier."))
            return

        try:
            longueur = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            longueur = -1
        if longueur < 0 or longueur > TAILLE_MAX:
            self._repondre(413, page("Message trop long", "Ton envoi dépasse la taille acceptée."))
            return

        # L'adresse vient de nginx (X-Real-IP), pas du visiteur directement.
        ip = self.headers.get("X-Real-IP") or self.client_address[0]
        if not autorise_ip(ip):
            self._repondre(429, page("Trop d'envois", "Attends quelques minutes avant de réessayer."))
            return

        donnees = parse_qs(self.rfile.read(longueur).decode("utf-8", errors="replace"))

        def champ(nom):
            return donnees.get(nom, [""])[0]

        if champ("site").strip():
            # Un robot a rempli le champ caché : on fait semblant que tout va bien.
            self._repondre(200, page("Merci", "Ton envoi a bien été reçu."))
            return

        if not question_valide(champ("jeton"), champ("reponse")):
            if chemin == CHEMIN_CONTACT:
                self._repondre(400, formulaire_contact("Réponse fausse ou question expirée. Réessaie."))
            else:
                self._repondre(400, page("Réponse fausse", "Ta réponse est fausse ou la question a expiré. Reviens à l'article et réessaie."))
            return

        pseudo = nettoyer_ligne(champ("pseudo"))
        message = nettoyer_texte(champ("message"))
        if not message:
            self._repondre(400, page("Message vide", "Écris un message avant d'envoyer."))
            return
        if len(pseudo) > PSEUDO_MAX or len(message) > MESSAGE_MAX:
            self._repondre(400, page("Trop long", "Ton pseudo ou ton message dépasse la taille autorisée."))
            return
        pseudo = pseudo or "anonyme"

        if chemin == CHEMIN_CONTACT:
            try:
                enregistrer_message(pseudo, message, ip)
            except sqlite3.Error:
                self._repondre(500, page("Erreur", "Le message n'a pas pu être enregistré. Réessaie plus tard."))
                return
            self._repondre(200, page("Merci", "Ton message a bien été envoyé."))
            return

        article = nettoyer_ligne(champ("article"))
        if not 1 <= len(article) <= ARTICLE_MAX:
            self._repondre(400, page("Article inconnu", "Le commentaire ne correspond à aucun article."))
            return
        try:
            ecrire_commentaire(article, pseudo, message, ip)
        except OSError:
            self._repondre(500, page("Erreur", "Le commentaire n'a pas pu être enregistré. Réessaie plus tard."))
            return
        self._repondre(200, page("Merci", "Ton commentaire a bien été reçu. Il apparaîtra sous l'article après validation."))


def main():
    # Fichiers créés lisibles par le seul compte qui fait tourner le script.
    os.umask(0o077)
    os.makedirs(DOSSIER_DONNEES, mode=0o700, exist_ok=True)
    charger_cle()

    if len(sys.argv) > 1:
        if sys.argv[1] == "importer":
            importer()
            return
        print("usage : contact.py [importer]", file=sys.stderr)
        sys.exit(2)

    serveur = ThreadingHTTPServer((HOTE, PORT), Gestionnaire)
    print(f"contact.py à l'écoute sur {HOTE}:{PORT}", file=sys.stderr)
    serveur.serve_forever()


if __name__ == "__main__":
    main()
