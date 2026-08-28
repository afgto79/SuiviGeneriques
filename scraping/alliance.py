"""Extraction Alliance Healthcare/Cencora — méthode validée le 25/08/2026 (voir plan).

Pas d'API : on clique l'onglet "Mois en cours" puis on lit document.body.innerText
(PAS get_page_text-style extraction basée sur le DOM visible : la page plante sur les SVG
du bar chart secondaire). Aucune saisie d'identifiants n'est écrite ici — si le cookie de
session a expiré, on ne fait que cliquer "SE CONNECTER" quand le profil Chromium persistant
a déjà pré-rempli le formulaire via son gestionnaire de mots de passe (autofill natif,
mémorisé lors d'un précédent first_login.py) ; si ce n'est pas le cas (ex. mémorisation
expirée, code de vérification demandé), on abandonne et first_login.py reste le filet de
sécurité pour une reconnexion manuelle.
"""
from __future__ import annotations

import re

from playwright.sync_api import Page, TimeoutError as PlaywrightTimeoutError

from config import ALLIANCE_LABEL_MAP, ALLIANCE_URL, BASE_DIR
from thresholds import parse_amount_fr

from . import SessionExpired

_LOGIN_MARKERS = ("Connexion", "Mot de passe", "Nom d'utilisateur")
_DEBUG_SCREENSHOT = BASE_DIR / "debug_alliance_timeout.png"


def _attempt_auto_relogin(page: Page) -> bool:
    """Clique "SE CONNECTER" si (et seulement si) Chromium a déjà rempli les champs
    nom d'utilisateur/mot de passe via son autofill natif. On ne saisit jamais nous-mêmes
    de valeur dans ces champs. Retourne True si le tableau des laboratoires apparaît
    ensuite, False sinon (mémorisation absente, identifiants refusés, code de
    vérification demandé, etc.) — dans tous les cas d'échec, l'appelant retombe sur
    SessionExpired et first_login.py reste la voie de reconnexion manuelle.
    """
    try:
        username = page.get_by_label("Nom d'utilisateur", exact=False).first
        password = page.get_by_label("Mot de passe", exact=False).first
        if not username.input_value().strip() or not password.input_value().strip():
            return False  # rien de mémorisé par Chromium : on ne saisit rien nous-mêmes
        page.get_by_role("button", name=re.compile("se connecter", re.I)).first.click()
    except Exception:
        return False

    try:
        page.wait_for_selector("text=Laboratoires Génériques", timeout=20000)
        return True
    except PlaywrightTimeoutError:
        return False


def fetch_alliance_amounts(page: Page, *, _allow_relogin: bool = True) -> dict[str, float]:
    """Retourne {"Biogaran": montant, "Viatris": montant, "Sandoz": montant} (net)."""
    page.goto(ALLIANCE_URL, wait_until="domcontentloaded")
    try:
        page.wait_for_load_state("networkidle", timeout=15000)
    except PlaywrightTimeoutError:
        pass  # l'app Angular peut garder des requêtes de fond ouvertes ; pas bloquant en soi

    try:
        page.wait_for_selector("text=Laboratoires Génériques", timeout=30000)
    except PlaywrightTimeoutError:
        text_now = page.evaluate("document.body.innerText")
        if any(marker in text_now for marker in _LOGIN_MARKERS):
            if _allow_relogin and _attempt_auto_relogin(page):
                # Reconnexion automatique réussie : on relit la page depuis le début
                # (une seule tentative, pour ne pas boucler indéfiniment).
                return fetch_alliance_amounts(page, _allow_relogin=False)
            raise SessionExpired(
                "Alliance: écran de login détecté — session expirée et reconnexion "
                "automatique impossible (identifiants non mémorisés par Chromium ou "
                "code de vérification requis) — reconnexion manuelle nécessaire "
                "(first_login.py)"
            )
        try:
            page.screenshot(path=str(_DEBUG_SCREENSHOT))
            hint = f" (capture sauvegardée : {_DEBUG_SCREENSHOT.name})"
        except Exception:
            hint = ""
        raise SessionExpired(f"Alliance: page 'laboratoires-generiques' non chargée après 30s{hint}")

    # Onglet "Mois en cours" : clic par texte exact (comme validé manuellement),
    # puis on laisse le temps au rendu Angular de se mettre à jour.
    try:
        page.get_by_text("Mois en cours", exact=True).first.click()
    except Exception:
        pass  # si le clic échoue, on retente quand même la lecture (l'onglet est parfois déjà actif)
    page.wait_for_timeout(2500)

    text = page.evaluate("document.body.innerText")

    if any(marker in text for marker in _LOGIN_MARKERS) and "Laboratoires Génériques" not in text:
        raise SessionExpired("Alliance: écran de login détecté après clic — session probablement expirée")

    amounts: dict[str, float] = {}
    for raw_label, canonical in ALLIANCE_LABEL_MAP.items():
        # Ex: "BIOGARAN\n\t\n2 938,98 €" -> capture "2 938,98"
        pattern = re.compile(
            re.escape(raw_label) + r"\s*\n\t\n\s*(-,--|[\d\s ]+,\d{2})\s*€"
        )
        match = pattern.search(text)
        if match is None:
            # Labo absent du tableau cette période : ne pas fabriquer de valeur, on l'omet.
            continue
        amounts[canonical] = parse_amount_fr(match.group(1))

    return amounts
