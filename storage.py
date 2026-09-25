# -*- coding: utf-8 -*-
"""
storage.py — Persistance locale de l'historique (site, n) du générateur de
mots de passe déterministe, pour l'appli Android CryPyte PwdGen.

⚠️ MODÈLE DE SÉCURITÉ — DIFFÉRENT DU CryPyte DESKTOP D'ORIGINE :
   Le CryPyte desktop chiffrait cet historique avec une clé dérivée du mot
   de passe de connexion au coffre (Fernet,
   crypto_utils.get_pwdgen_storage_key). Cette appli n'a VOLONTAIREMENT
   AUCUNE authentification : il n'existe donc plus aucun secret dont
   dériver une clé de chiffrement pour ce fichier.

   L'historique est stocké EN CLAIR (JSON) dans le répertoire de données
   privé de l'application (App.user_data_dir), qui sur Android est
   sandboxé par le système : aucune autre application ne peut y accéder
   sans root. C'est un compromis assumé et explicite — remonté à
   l'utilisateur, pas une régression silencieuse. Rien de plus sensible
   que des noms de site n'y est stocké : ni le mot de passe maître, ni les
   mots de passe générés.

Ne stocke que des tuples (site: str, n: int) — jamais un mot de passe
généré, jamais le mot de passe maître.
"""

import difflib
import json
import os

HISTORY_FILENAME = "historique_sites.json"

# Seuil de similarité floue (identique au CryPyte desktop, pwdgen.py).
_SEUIL_RECHERCHE = 0.6


def _history_path(app_data_dir: str) -> str:
    """Construit le chemin du fichier d'historique dans le dossier de l'app."""
    return os.path.join(app_data_dir, HISTORY_FILENAME)


def lire_historique(app_data_dir: str) -> list[tuple[str, int]]:
    """
    Lit l'historique (site, n) depuis le JSON local. Retourne une liste
    vide si le fichier est absent, vide, ou corrompu (aucune exception ne
    remonte à l'appelant).

    Args:
        app_data_dir (str): App.user_data_dir de l'application Kivy.

    Returns:
        list[tuple[str, int]]: Entrées (site, n) dans l'ordre du fichier.
    """
    path = _history_path(app_data_dir)
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return [(str(e["site"]), int(e["n"])) for e in data]
    except (json.JSONDecodeError, KeyError, ValueError, OSError):
        return []


def ecrire_historique(entrees: list[tuple[str, int]], app_data_dir: str) -> bool:
    """
    Réécrit entièrement le fichier d'historique local (JSON), avec
    écriture atomique (.tmp + os.replace, même principe que le CryPyte
    desktop) pour éviter la corruption en cas d'interruption.

    Args:
        entrees      (list[tuple[str, int]]): Ensemble complet des entrées.
        app_data_dir (str): App.user_data_dir de l'application Kivy.

    Returns:
        bool: True si l'écriture a réussi, False sinon.
    """
    path = _history_path(app_data_dir)
    data = [{"site": s, "n": n} for s, n in entrees]
    try:
        os.makedirs(app_data_dir, exist_ok=True)
        tmp_path = path + ".tmp"
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp_path, path)
        return True
    except OSError:
        return False


def normaliser(chaine: str) -> str:
    """Minuscules + espaces supprimés, pour une comparaison tolérante."""
    return chaine.lower().replace(" ", "")


def correspond(site: str, terme: str) -> bool:
    """
    Détermine si `site` correspond au terme recherché — logique identique
    à pwdgen.correspond() du CryPyte desktop : correspondance directe,
    puis floue via difflib (seuil 0.6) si besoin.

    Args:
        site  (str): Nom de site à tester.
        terme (str): Terme recherché (brut, non normalisé par l'appelant).

    Returns:
        bool: True si `site` doit être affiché pour ce terme de recherche.
    """
    site_norm, terme_norm = normaliser(site), normaliser(terme)
    if not terme_norm:
        return True
    if terme_norm in site_norm:
        return True
    return difflib.SequenceMatcher(None, site_norm, terme_norm).ratio() >= _SEUIL_RECHERCHE
