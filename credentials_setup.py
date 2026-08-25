"""À lancer UNE FOIS, à la main, dans un terminal, pour enregistrer les secrets
dans le Gestionnaire d'identifiants Windows (jamais dans un fichier en clair).

Usage :
    python credentials_setup.py

Saisie en clair (pas masquée) : la saisie masquée (getpass) perd parfois des
caractères lors d'un copier-coller dans certains terminaux Windows. Le texte
est visible un instant dans votre terminal, mais n'est jamais écrit dans un
fichier — uniquement dans le Gestionnaire d'identifiants Windows.
"""
from __future__ import annotations

import keyring

from config import KEYRING_KEYS, KEYRING_SERVICE


def _preview(value: str) -> str:
    if len(value) <= 6:
        return "*" * len(value)
    return f"{value[:3]}...{value[-3:]}"


def _set(label: str, key: str, expected_hint: str) -> None:
    value = input(f"{label} — collez puis Entrée ({expected_hint}) : ").strip()
    if not value:
        print(f"  -> vide, ignoré ({key} non modifié)\n")
        return
    keyring.set_password(KEYRING_SERVICE, key, value)
    print(f"  -> enregistré : {len(value)} caractères, aperçu {_preview(value)}")
    print(f"     Vérifiez que la longueur correspond à ce que vous avez copié ({expected_hint}).\n")


def main() -> None:
    print("=== Enregistrement des secrets Suivi Génériques ===")
    print("(laisser vide + Entrée pour ne pas modifier un secret déjà enregistré)\n")

    print("1) Mot de passe d'APPLICATION Gmail (Compte Google > Sécurité > Mots de passe des"
          " applications) — PAS votre vrai mot de passe Gmail.")
    _set("Mot de passe d'application Gmail", KEYRING_KEYS["gmail_app_password"], "16 caractères, espaces ou non")

    print("2) Token GitHub (fine-grained ou classic) pour publier la page.")
    _set("Token GitHub", KEYRING_KEYS["github_token"], "commence par 'github_pat_' ou 'ghp_', assez long")

    print("Terminé. Les identifiants OCP/Alliance eux-mêmes ne sont PAS stockés ici : "
          "la connexion se fait une fois pour toutes via first_login.py, dans un profil "
          "de navigateur persistant.")


if __name__ == "__main__":
    main()
