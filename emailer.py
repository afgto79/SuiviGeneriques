"""Envoi de l'email récapitulatif hebdomadaire via le Gmail existant de la pharmacie.

Le mot de passe d'application est lu dans le Gestionnaire d'identifiants Windows
(keyring) — jamais en clair, jamais saisi par ce code lui-même : c'est l'utilisateur
qui l'y a déposé via credentials_setup.py.
"""
from __future__ import annotations

import smtplib
from datetime import date
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import keyring

from config import (
    KEYRING_KEYS,
    KEYRING_SERVICE,
    RECIPIENT_EMAILS,
    SENDER_EMAIL,
    SMTP_HOST,
    SMTP_PORT,
)
from thresholds import LaboStatus

_NIVEAU_EMOJI = {"ok": "✅", "attention": "🟠", "urgent": "🔴"}


def _format_ligne(s: LaboStatus) -> str:
    emoji = _NIVEAU_EMOJI[s.niveau]
    if s.atteint:
        return f"{emoji} {s.repartiteur} — {s.labo} : {s.montant:.0f}€ (seuil atteint)"
    return f"{emoji} {s.repartiteur} — {s.labo} : {s.montant:.0f}€, reste {s.reste:.0f}€ avant {s.seuil:.0f}€ (J-{s.jours_restants})"


def build_body(statuses: list[LaboStatus], scrape_errors: dict[str, str], today: date | None = None) -> tuple[str, str]:
    today = today or date.today()
    lignes = [_format_ligne(s) for s in statuses]
    urgents = [s for s in statuses if s.niveau == "urgent"]

    plain_lines = [f"Suivi remises génériques — semaine du {today.isoformat()}", ""]
    if urgents:
        plain_lines.append(f"⚠️ {len(urgents)} labo(s) à risque de perdre la remise ce mois-ci :")
        for s in urgents:
            plain_lines.append("  " + _format_ligne(s))
        plain_lines.append("")
    plain_lines.append("Détail complet :")
    plain_lines.extend("  " + l for l in lignes)

    if scrape_errors:
        plain_lines.append("")
        plain_lines.append("⚠️ Données indisponibles (reconnexion manuelle nécessaire) :")
        for repartiteur, err in scrape_errors.items():
            plain_lines.append(f"  - {repartiteur} : {err}")

    subject = "Suivi génériques"
    if urgents:
        subject += f" — {len(urgents)} labo(s) à surveiller cette semaine"
    elif scrape_errors:
        subject += " — reconnexion nécessaire"
    else:
        subject += " — RAS"

    return subject, "\n".join(plain_lines)


def send_weekly_email(statuses: list[LaboStatus], scrape_errors: dict[str, str], today: date | None = None) -> None:
    app_password = keyring.get_password(KEYRING_SERVICE, KEYRING_KEYS["gmail_app_password"])
    if not app_password:
        raise RuntimeError(
            "Mot de passe d'application Gmail introuvable dans le Gestionnaire d'identifiants. "
            "Lancez credentials_setup.py."
        )

    subject, body = build_body(statuses, scrape_errors, today)

    msg = MIMEMultipart()
    msg["From"] = SENDER_EMAIL
    msg["To"] = ", ".join(RECIPIENT_EMAILS)
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain", "utf-8"))

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
        server.starttls()
        server.login(SENDER_EMAIL, app_password)
        server.send_message(msg)
