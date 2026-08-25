"""Extraction OCP Pharmalia — méthode validée le 25/08/2026 (voir plan).

Utilise l'API interne /ocp-back/edata/achatGenerique, appelée depuis le contexte
de la page (fetch credentials:'include') pour réutiliser la session déjà
authentifiée dans le profil de navigateur persistant. Aucune saisie d'identifiants ici.
"""
from __future__ import annotations

from playwright.sync_api import Page

from config import OCP_API_PATH, OCP_LABEL_MAP, OCP_URL
from thresholds import parse_amount_fr

from . import SessionExpired

_FETCH_JS = """
async () => {
    const r = await fetch(%r, {credentials: 'include'});
    const ct = r.headers.get('content-type') || '';
    if (!ct.includes('json')) {
        return {ok: false, status: r.status, notJson: true};
    }
    const data = await r.json();
    return {ok: true, status: r.status, data};
}
""" % OCP_API_PATH


def fetch_ocp_amounts(page: Page) -> dict[str, float]:
    """Retourne {"Biogaran": montant, "Viatris": montant, "Sandoz": montant} (brut HT).

    Lève SessionExpired si la session n'est plus valide (l'API ne répond pas en JSON,
    typiquement parce qu'elle a redirigé vers une page de login).
    """
    page.goto(OCP_URL, wait_until="domcontentloaded")
    result = page.evaluate(_FETCH_JS)

    if not result.get("ok"):
        raise SessionExpired(f"OCP: réponse non-JSON (status {result.get('status')}) — session probablement expirée")

    data = result["data"]
    periodes = data.get("listePeriodes", [])
    mois_en_cours = next((p for p in periodes if p.get("periode") == "MoisEnCours"), None)
    if mois_en_cours is None:
        raise SessionExpired("OCP: 'MoisEnCours' absent de la réponse — structure inattendue")

    raw_amounts = {a["marque"]: a["valeur"] for a in mois_en_cours.get("listeAchats", [])}

    amounts: dict[str, float] = {}
    for raw_label, canonical in OCP_LABEL_MAP.items():
        raw_value = raw_amounts.get(raw_label)
        if raw_value is None:
            # Marque absente cette période : ne pas fabriquer de valeur, on l'omet.
            continue
        amounts[canonical] = parse_amount_fr(raw_value)

    return amounts
