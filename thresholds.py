"""Parsing des montants et calcul des seuils/alertes par (répartiteur x labo)."""
from __future__ import annotations

import calendar
import re
from dataclasses import dataclass
from datetime import date

from config import JOURS_ALERTE, SEUIL_EUR

_AMOUNT_RE = re.compile(r"[\s ]")  # espaces normaux + insécables (séparateur de milliers FR)


def parse_amount_fr(raw: str) -> float:
    """Convertit un montant au format FR ('2 938,98', '590', '-,--', '--') en float.

    Ne jamais fabriquer de valeur : une chaîne vide/illisible lève ValueError plutôt
    que d'être silencieusement traitée comme 0, SAUF les marqueurs explicites d'absence
    de données du portail ('-,--', '--', '-') qui signifient bien 0€.
    """
    if raw is None:
        raise ValueError("montant manquant (None)")
    s = raw.strip()
    if s in ("-,--", "--", "-", ""):
        return 0.0
    s = _AMOUNT_RE.sub("", s)
    s = s.replace(",", ".")
    return float(s)


@dataclass
class LaboStatus:
    repartiteur: str
    labo: str
    montant: float
    seuil: float
    reste: float
    jours_restants: int
    atteint: bool
    urgent: bool

    @property
    def niveau(self) -> str:
        if self.atteint:
            return "ok"
        if self.urgent:
            return "urgent"
        return "attention"


def jours_restants_dans_le_mois(today: date | None = None) -> int:
    today = today or date.today()
    dernier_jour = calendar.monthrange(today.year, today.month)[1]
    return dernier_jour - today.day


def compute_status(repartiteur: str, labo: str, montant: float, today: date | None = None) -> LaboStatus:
    reste = max(0.0, SEUIL_EUR - montant)
    jours = jours_restants_dans_le_mois(today)
    atteint = reste <= 0
    urgent = (not atteint) and jours <= JOURS_ALERTE
    return LaboStatus(
        repartiteur=repartiteur,
        labo=labo,
        montant=round(montant, 2),
        seuil=SEUIL_EUR,
        reste=round(reste, 2),
        jours_restants=jours,
        atteint=atteint,
        urgent=urgent,
    )


def build_statuses(ocp_amounts: dict[str, float], alliance_amounts: dict[str, float], today: date | None = None) -> list[LaboStatus]:
    """ocp_amounts / alliance_amounts : {nom_canonique_labo: montant} déjà mappés."""
    statuses: list[LaboStatus] = []
    for labo, montant in ocp_amounts.items():
        statuses.append(compute_status("OCP Pharmalia", labo, montant, today))
    for labo, montant in alliance_amounts.items():
        statuses.append(compute_status("Alliance Healthcare", labo, montant, today))
    return statuses
