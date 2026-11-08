#!/usr/bin/env python3
"""Empreintes des images de prévisualisation : ne les régénérer que si leur contenu a changé.

Pour chaque image, on calcule un hachage (SHA-256) de ce qui la produit (texte de la page,
code du script, feuilles de style…). Le hachage est gardé dans .cache/empreintes.json, par groupe
(« og », « captures »). Une image est ignorée si son fichier existe encore et si son hachage
est identique à celui du build précédent.

`python3 build.py --forcer` ignore le cache et régénère toutes les images.
"""
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
MANIFESTE = ROOT / ".cache" / "empreintes.json"
FORCER = "--forcer" in sys.argv


def hache(*morceaux: bytes | str) -> str:
    """Hachage de plusieurs morceaux ; chaque morceau est préfixé par sa longueur (pas d'ambiguïté)."""
    h = hashlib.sha256()
    for morceau in morceaux:
        if isinstance(morceau, str):
            morceau = morceau.encode("utf-8")
        h.update(len(morceau).to_bytes(8, "big"))
        h.update(morceau)
    return h.hexdigest()


def _charger() -> dict:
    try:
        return json.loads(MANIFESTE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


class Empreintes:
    """Cache d'un groupe d'images. `enregistrer()` remplace le groupe : les pages supprimées en sortent."""

    def __init__(self, groupe: str):
        self.groupe = groupe
        self._anciennes = _charger().get(groupe, {})
        self._nouvelles: dict[str, str] = {}

    def a_jour(self, cle: str, empreinte: str, sortie: Path) -> bool:
        """Vrai si l'image existe et n'a pas changé depuis le dernier build."""
        return not FORCER and sortie.exists() and self._anciennes.get(cle) == empreinte

    def noter(self, cle: str, empreinte: str) -> None:
        self._nouvelles[cle] = empreinte

    def enregistrer(self) -> None:
        tout = _charger()
        tout[self.groupe] = self._nouvelles
        MANIFESTE.parent.mkdir(exist_ok=True)
        MANIFESTE.write_text(json.dumps(tout, indent=1, sort_keys=True), encoding="utf-8")
