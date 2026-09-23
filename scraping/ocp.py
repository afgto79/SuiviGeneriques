"""Extraction OCP Pharmalia — méthode validée le 25/08/2026 (voir plan).

Utilise l'API interne /ocp-back/edata/achatGenerique, appelée depuis le contexte
de la page (fetch credentials:'include') pour réutiliser la session déjà
authentifiée dans le profil de navigateur persistant. Aucune saisie d'identifiants ici.
"""
from __future__ import annotations

from datetime import date

from playwright.sync_api import Page

from config import OCP_API_PATH, OCP_LABEL_MAP, OCP_MAX_AGE_JOURS, OCP_URL
from thresholds import parse_amount_fr

from . import DonneesPerimees, SessionExpired

# cache:'no-store' + paramètre _=horodatage (comme le fait le site OCP lui-même) :
# sans ça, Chromium a resservi la même réponse depuis son cache HTTP du 14/09 au
# 23/09/2026 (montant Biogaran figé à 148€ alors que le portail affichait 300€).
_FETCH_JS = """
async () => {
    const r = await fetch(%r + '?_=' + Date.now(), {credentials: 'include', cache: 'no-store'});
    const ct = r.headers.get('content-type') || '';
    if (!ct.includes('json')) {
        return {ok: false, status: r.status, notJson: true};
    }
    const data = await r.json();
    return {ok: true, status: r.status, data};
}
""" % OCP_API_PATH


def fetch_ocp_amounts(page: Page, today: date | None = None) -> tuple[dict[str, float], date]:
    """Retourne ({"Biogaran": montant, "Viatris": montant, "Sandoz": montant} (brut HT),
    date de mise à jour des données côté OCP).

    Lève SessionExpired si la session n'est plus valide (l'API ne répond pas en JSON,
    typiquement parce qu'elle a redirigé vers une page de login), et DonneesPerimees si
    la date de mise à jour OCP est trop ancienne ou d'un autre mois (en début de mois,
    'MoisEnCours' contient encore le total du mois précédent pendant 1-2 jours).
    """
    today = today or date.today()
    page.goto(OCP_URL, wait_until="domcontentloaded")
    result = page.evaluate(_FETCH_JS)

    if not result.get("ok"):
        raise SessionExpired(f"OCP: réponse non-JSON (status {result.get('status')}) — session probablement expirée")

    data = result["data"]
    try:
        date_maj = date.fromisoformat(data["dateMAJ"][:10])
    except (KeyError, TypeError, ValueError):
        raise DonneesPerimees(f"OCP: dateMAJ absente ou illisible ({data.get('dateMAJ')!r})") from None
    if (date_maj.year, date_maj.month) != (today.year, today.month):
        raise DonneesPerimees(f"OCP: données du {date_maj:%d/%m/%Y}, pas encore basculées sur le mois en cours")
    if (today - date_maj).days > OCP_MAX_AGE_JOURS:
        raise DonneesPerimees(f"OCP: données du {date_maj:%d/%m/%Y}, plus de {OCP_MAX_AGE_JOURS} jours")

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

    return amounts, date_maj
