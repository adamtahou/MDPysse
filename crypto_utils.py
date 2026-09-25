# -*- coding: utf-8 -*-
"""
crypto_utils.py — Dérivation déterministe du générateur de mots de passe.

Repris à l'identique du CryPyte desktop (fonctions pures, zéro effet de
bord). Toute la partie "clés Fernet du coffre" (get_crypto_key,
get_private_crypto_key, bcrypt...) a été volontairement supprimée : cette
appli n'a aucun coffre, aucune authentification, rien à chiffrer au repos
à part l'historique de sites (voir storage.py).

⚠️ CONSTANTES IMMUABLES : les modifier change silencieusement tous les mots
   de passe déjà générés pour l'utilisateur. Ne jamais les modifier sans le
   signaler explicitement.
"""

import hashlib

_PWDGEN_ITERATIONS = 300_000  # OWASP 2024 — NE JAMAIS MODIFIER
_PWDGEN_INTERDITS  = set(" \"'\\,;:<>[]{}()|`")
_PWDGEN_CHARS_OK   = [chr(c) for c in range(33, 127) if chr(c) not in _PWDGEN_INTERDITS]  # ~78 caractères
_PWDGEN_SPECIALS   = "!@#$%&*+?=-_"


def deriver_cle_generateur(maitre: str, site: str, n: int) -> bytes:
    """
    Dérive 32 octets déterministes via PBKDF2-HMAC-SHA256 à partir du
    triplet (maitre, site, n). Fonction pure, coûteuse (300k itérations) —
    à appeler depuis un thread séparé, jamais depuis le thread UI Kivy.

    Args:
        maitre (str): Mot de passe maître, en clair (jamais stocké).
        site   (str): Nom du site cible (fait partie du sel).
        n      (int): Compteur de "leaks" (fait aussi partie du sel).

    Returns:
        bytes: 32 octets dérivés, à passer à construire_mot_de_passe().
    """
    sel = f"{site}:{n}".encode("utf-8")
    return hashlib.pbkdf2_hmac("sha256", maitre.encode("utf-8"), sel, _PWDGEN_ITERATIONS, dklen=32)


def construire_mot_de_passe(dk: bytes, site: str, longueur: int) -> str:
    """
    Convertit les 32 octets dérivés en un mot de passe lisible de
    `longueur` caractères, puis applique un secours de complexité
    déterministe (positions fixes) si un critère est absent. Fonction
    pure, sans effet de bord — identique au CryPyte desktop.

    Args:
        dk       (bytes): Sortie de deriver_cle_generateur() (32 octets).
        site     (str)  : Nom du site — source du secours de complexité.
        longueur (int)  : Longueur du mot de passe à produire (8 à 64).

    Returns:
        str: Mot de passe final.
    """
    base   = len(_PWDGEN_CHARS_OK)
    valeur = int.from_bytes(dk, "big")

    mdp_chars = []
    for _ in range(longueur):
        mdp_chars.append(_PWDGEN_CHARS_OK[valeur % base])
        valeur //= base

    if not any(c.islower() for c in mdp_chars):
        mdp_chars[0] = chr((ord(site[0]) % 26) + 97)
    if not any(c.isupper() for c in mdp_chars):
        mdp_chars[1] = chr((ord(site[-1]) % 26) + 65)
    if not any(c.isdigit() for c in mdp_chars):
        mdp_chars[2] = str(len(site) % 10)
    if not any(not c.isalnum() for c in mdp_chars):
        mdp_chars[3] = _PWDGEN_SPECIALS[len(site) % len(_PWDGEN_SPECIALS)]

    return "".join(mdp_chars)
