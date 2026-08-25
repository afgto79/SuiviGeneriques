"""Petit état persistant local (pas de secrets dedans) : dernier relevé, dernier
envoi d'email, dernier statut affiché en tray. Permet à la boucle interne de savoir
si le relevé du jour / l'email de la semaine ont déjà été faits, sans tâche planifiée
externe.
"""
from __future__ import annotations

import json
from typing import Any

from config import STATE_FILE

_DEFAULT_STATE: dict[str, Any] = {
    "last_daily_date": None,   # "YYYY-MM-DD"
    "last_email_week": None,   # "YYYY-Www" (ISO)
    "last_niveau": "ok",       # "ok" / "attention" / "urgent" / "erreur"
}


def load() -> dict[str, Any]:
    if not STATE_FILE.exists():
        return dict(_DEFAULT_STATE)
    try:
        return {**_DEFAULT_STATE, **json.loads(STATE_FILE.read_text(encoding="utf-8"))}
    except (json.JSONDecodeError, OSError):
        return dict(_DEFAULT_STATE)


def save(state: dict[str, Any]) -> None:
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
