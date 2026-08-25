"""Extraction Alliance Healthcare/Cencora — méthode validée le 25/08/2026 (voir plan).

Pas d'API : on clique l'onglet "Mois en cours" puis on lit document.body.innerText
(PAS get_page_text-style extraction basée sur le DOM visible : la page plante sur les SVG
du bar chart secondaire). Aucune saisie d'identifiants ici — la session persistante
du profil Playwright doit déjà être authentifiée.
"""
from __future__ import annotations

import re

from playwright.sync_api import Page, TimeoutError as PlaywrightTimeoutError

from config import ALLIANCE_LABEL_MAP, ALLIANCE_URL, BASE_DIR
from thresholds import parse_amount_fr

from . import SessionExpired

_LOGIN_MARKERS = ("Connexion", "Mot de passe", "Nom d'utilisateur")
_DEBUG_SCREENSHOT = BASE_DIR / "debug_alliance_timeout.png"


def fetch_alliance_amounts(page: Page) -> dict[str, float]:
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
            raise SessionExpired("Alliance: écran de login détecté — session probablement expirée")
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
