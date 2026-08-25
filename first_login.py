"""À lancer UNE FOIS (et de nouveau si le statut passe en 'reconnexion requise'),
dans un terminal, pour se connecter soi-même aux deux portails, chacun dans son
profil de navigateur persistant que l'appli réutilisera ensuite en fond de tâche.

Ce script ouvre une fenêtre Chromium VISIBLE. Vous vous connectez vous-même
(identifiants + éventuel code de vérification) exactement comme d'habitude.
Rien n'est automatisé ici — c'est fait exprès.

Usage :
    python first_login.py
"""
from __future__ import annotations

from playwright.sync_api import sync_playwright

from config import (
    ALLIANCE_PROFILE_DIR,
    ALLIANCE_STORAGE_STATE_FILE,
    ALLIANCE_URL,
    OCP_URL,
    PLAYWRIGHT_PROFILE_DIR,
)


def main() -> None:
    PLAYWRIGHT_PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    ALLIANCE_PROFILE_DIR.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            str(PLAYWRIGHT_PROFILE_DIR),
            headless=False,
        )
        try:
            page = context.new_page()

            print(f"Ouverture de {OCP_URL}")
            print("-> Connectez-vous vous-même à OCP Pharmalia dans la fenêtre qui s'est ouverte.")
            page.goto(OCP_URL)
            input("Appuyez sur Entrée une fois connecté et la page des achats génériques affichée... ")

            print(f"\nSession OCP sauvegardée dans {PLAYWRIGHT_PROFILE_DIR}")
        finally:
            context.close()

    print("\nNB : si l'appli (icône barre système) tourne, fermez-la (menu -> Quitter) avant de")
    print("continuer, sinon l'ouverture ci-dessous risque d'échouer (profil déjà ouvert).")
    input("Appuyez sur Entrée pour continuer vers Alliance Healthcare... ")

    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            str(ALLIANCE_PROFILE_DIR),
            headless=False,
        )
        try:
            page = context.new_page()

            print(f"\nOuverture de {ALLIANCE_URL}")
            print("-> Connectez-vous vous-même à Alliance Healthcare dans la fenêtre qui s'est ouverte.")
            page.goto(ALLIANCE_URL)
            input("Appuyez sur Entrée une fois connecté et le tableau des laboratoires affiché... ")

            # Le cookie de session CAS d'Alliance ne survit pas à la fermeture propre de
            # Chromium (contrairement à OCP) : storage_state() capture l'état de la
            # session maintenant, pendant qu'elle est valide, pour que l'appli puisse le
            # réinjecter à chaque relevé sans avoir à se reconnecter.
            context.storage_state(path=str(ALLIANCE_STORAGE_STATE_FILE))

            print(f"\nSession Alliance sauvegardée dans {ALLIANCE_STORAGE_STATE_FILE.name}")
            print("L'appli en fond de tâche pourra réutiliser ces sessions sans que vous ayez à vous reconnecter,")
            print("tant qu'elles restent valides (relancez ce script si le statut repasse en 'reconnexion requise').")
        finally:
            context.close()


if __name__ == "__main__":
    main()
