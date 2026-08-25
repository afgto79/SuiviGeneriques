"""Point d'entrée : icône dans la barre système + boucle de fond qui gère elle-même
son minutage (relevé quotidien, email hebdomadaire). Pas de Task Scheduler : ce
processus doit simplement être lancé au démarrage de Windows (raccourci dans
shell:startup pointant vers cet interpréteur, cf. README) et reste ouvert.
"""
from __future__ import annotations

import json
import logging
import logging.handlers
import subprocess
import sys
import threading
import time
import webbrowser
from datetime import date, datetime

import pystray
from PIL import Image, ImageDraw
from playwright.sync_api import sync_playwright

import state_store
from config import (
    ALLIANCE_PROFILE_DIR,
    ALLIANCE_STORAGE_STATE_FILE,
    BASE_DIR,
    DAILY_CHECK_HOUR,
    EMAIL_WEEKDAY,
    PAGE_PUBLIC_URL,
    PLAYWRIGHT_PROFILE_DIR,
    POLL_INTERVAL_MINUTES,
)
from emailer import send_weekly_email
from page_publisher import publish as publish_page
from scraping import SessionExpired
from scraping.alliance import fetch_alliance_amounts
from scraping.ocp import fetch_ocp_amounts
from thresholds import build_statuses

# L'appli tourne via pythonw.exe (pas de console) : sans ce fichier journal, toute
# erreur (ex. token GitHub expiré, page down) disparaîtrait silencieusement dans le vide.
_LOG_FILE = BASE_DIR / "app.log"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[logging.handlers.RotatingFileHandler(_LOG_FILE, maxBytes=1_000_000, backupCount=3, encoding="utf-8")],
)
logger = logging.getLogger("suivi_generiques")

_LOCK = threading.Lock()  # évite deux relevés en parallèle (bouton "Vérifier maintenant" + boucle)

_COLORS = {"ok": (40, 170, 90), "attention": (220, 140, 0), "urgent": (210, 40, 40), "erreur": (150, 150, 150)}


def _make_icon_image(niveau: str) -> Image.Image:
    color = _COLORS.get(niveau, _COLORS["erreur"])
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.ellipse((8, 8, 56, 56), fill=color)
    return img


def _iso_week(d: date) -> str:
    y, w, _ = d.isocalendar()
    return f"{y}-W{w:02d}"


def _reset_window_placement() -> None:
    """Restaure une position de fenêtre normale (centrée, à l'écran) dans le profil Alliance.

    Le scraping Alliance ouvre une fenêtre headful poussée hors écran via
    --window-position. Chromium persiste cette position dans le profil
    (Preferences -> browser.window_placement) : sans ce correctif, une reconnexion
    manuelle ultérieure (first_login.py, "Reconnexion manuelle") hériterait de cette
    position et la fenêtre semblerait coincée hors de l'écran, sans rapport avec
    l'empreinte anti-bot — juste un artefact du profil.
    """
    prefs_path = ALLIANCE_PROFILE_DIR / "Default" / "Preferences"
    try:
        with open(prefs_path, encoding="utf-8") as f:
            data = json.load(f)
        window_placement = data.setdefault("browser", {}).setdefault("window_placement", {})
        window_placement.update({"left": 60, "top": 60, "right": 1180, "bottom": 900, "maximized": False})
        with open(prefs_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
    except Exception:
        # Purement cosmétique (position de fenêtre) : ne doit jamais faire échouer le relevé.
        logger.exception("Impossible de réinitialiser la position de fenêtre du profil Alliance")


def run_check(icon: pystray.Icon | None, force_email: bool = False) -> None:
    """Fait un relevé complet : scrape OCP + Alliance, publie la page, envoie l'email
    si c'est le jour prévu (ou si forcé via le menu). Robuste : une source en échec
    n'empêche pas de traiter l'autre.
    """
    if not _LOCK.acquire(blocking=False):
        return  # un relevé est déjà en cours
    try:
        try:
            _run_check_inner(icon, force_email)
        except Exception:
            # Filet de sécurité : une erreur totalement inattendue (ex. Chromium pas
            # installé, disque plein) ne doit jamais faire mourir silencieusement le
            # thread de fond — sans quoi plus aucun relevé n'aurait jamais lieu ensuite,
            # sans qu'on le sache, jusqu'au prochain redémarrage.
            logger.exception("Échec inattendu du relevé")
            state = state_store.load()
            state["last_niveau"] = "erreur"
            state_store.save(state)
            if icon is not None:
                icon.icon = _make_icon_image("erreur")
                icon.title = f"Suivi génériques — erreur inattendue, voir app.log ({datetime.now().strftime('%d/%m %H:%M')})"
    finally:
        _LOCK.release()


def _run_check_inner(icon: pystray.Icon | None, force_email: bool) -> None:
    today = date.today()
    scrape_errors: dict[str, str] = {}
    ocp_amounts: dict[str, float] = {}
    alliance_amounts: dict[str, float] = {}

    with sync_playwright() as p:
        # OCP : l'API interne (fetch credentials:'include') n'est pas gênée par le
        # fingerprint headless de Chromium — on reste en headless=True.
        context = p.chromium.launch_persistent_context(str(PLAYWRIGHT_PROFILE_DIR), headless=True)
        try:
            page = context.new_page()
            try:
                ocp_amounts = fetch_ocp_amounts(page)
            except SessionExpired as e:
                scrape_errors["OCP Pharmalia"] = str(e)
                logger.warning("OCP: %s", e)
        finally:
            context.close()

        # Alliance : le WAF (Azure Application Gateway) renvoie 403 spécifiquement sur
        # le fingerprint headless de Chromium — confirmé par debug_alliance_timeout.png
        # et par first_login.py (même profil, headless=False, qui charge la page sans
        # problème). Pas de contournement par la ruse : une vraie fenêtre headful,
        # poussée hors de l'écran visible pour rester discrète en fond de tâche
        # (--window-position ne change que le placement OS de la fenêtre, aucun impact
        # sur l'empreinte/la détection WAF). storage_state réinjecte la session CAS
        # sauvegardée par first_login.py/le relevé précédent : sans ça, le cookie de
        # session ne survit pas à la fermeture de ce contexte (vérifié le 25/08/2026).
        context = p.chromium.launch_persistent_context(
            str(ALLIANCE_PROFILE_DIR),
            headless=False,
            args=["--window-position=-2400,-2400", "--window-size=1280,900"],
        )
        try:
            # launch_persistent_context() n'a pas de paramètre storage_state (contrairement
            # à new_context()) : on réinjecte les cookies sauvegardés nous-mêmes.
            if ALLIANCE_STORAGE_STATE_FILE.exists():
                with open(ALLIANCE_STORAGE_STATE_FILE, encoding="utf-8") as f:
                    saved_state = json.load(f)
                if saved_state.get("cookies"):
                    context.add_cookies(saved_state["cookies"])

            page = context.new_page()
            try:
                alliance_amounts = fetch_alliance_amounts(page)
                # Session valide : on sauvegarde son état (le cookie CAS a pu être
                # renouvelé) pour le prochain relevé.
                context.storage_state(path=str(ALLIANCE_STORAGE_STATE_FILE))
            except SessionExpired as e:
                scrape_errors["Alliance Healthcare"] = str(e)
                logger.warning("Alliance: %s", e)
        finally:
            context.close()
            _reset_window_placement()

    statuses = build_statuses(ocp_amounts, alliance_amounts, today)
    total_failure = len(scrape_errors) >= 2  # OCP et Alliance en échec tous les deux

    if not total_failure:
        try:
            publish_page(statuses, scrape_errors, today)
        except Exception:  # la page est un bonus : ne doit jamais faire échouer tout le cycle
            logger.exception("Échec de publication de la page")

    state = state_store.load()

    if total_failure:
        # Échec probablement transitoire (réseau, portail HS) : on retente au
        # prochain réveil de la boucle (30 min) plutôt que d'attendre demain,
        # et on n'envoie pas d'email creux même si c'est le jour prévu.
        logger.error("Relevé en échec complet (%s) — nouvelle tentative au prochain cycle", scrape_errors)
    else:
        state["last_daily_date"] = today.isoformat()

        is_email_day = today.weekday() == EMAIL_WEEKDAY
        already_sent_this_week = state.get("last_email_week") == _iso_week(today)
        if force_email or (is_email_day and not already_sent_this_week):
            try:
                send_weekly_email(statuses, scrape_errors, today)
                state["last_email_week"] = _iso_week(today)
                logger.info("Email hebdomadaire envoyé")
            except Exception:
                logger.exception("Échec d'envoi de l'email")

    if scrape_errors:
        niveau = "erreur"
    elif any(s.niveau == "urgent" for s in statuses):
        niveau = "urgent"
    elif any(s.niveau == "attention" for s in statuses):
        niveau = "attention"
    else:
        niveau = "ok"
    state["last_niveau"] = niveau
    state_store.save(state)
    logger.info("Relevé terminé — niveau=%s, erreurs=%s", niveau, list(scrape_errors))

    if icon is not None:
        icon.icon = _make_icon_image(niveau)
        icon.title = f"Suivi génériques — {niveau} ({datetime.now().strftime('%d/%m %H:%M')})"


def _background_loop(icon: pystray.Icon) -> None:
    while True:
        state = state_store.load()
        today = date.today()
        already_done_today = state.get("last_daily_date") == today.isoformat()
        if not already_done_today and datetime.now().hour >= DAILY_CHECK_HOUR:
            run_check(icon)
        time.sleep(POLL_INTERVAL_MINUTES * 60)


def _menu_check_now(icon: pystray.Icon, _item: pystray.MenuItem) -> None:
    threading.Thread(target=run_check, args=(icon, True), daemon=True).start()


def _menu_open_page(_icon: pystray.Icon, _item: pystray.MenuItem) -> None:
    if PAGE_PUBLIC_URL and PAGE_PUBLIC_URL != "A_COMPLETER":
        webbrowser.open(PAGE_PUBLIC_URL)


def _menu_reconnect(_icon: pystray.Icon, _item: pystray.MenuItem) -> None:
    subprocess.Popen([sys.executable, "first_login.py"], cwd=str(BASE_DIR))


def _menu_quit(icon: pystray.Icon, _item: pystray.MenuItem) -> None:
    icon.stop()


def main() -> None:
    state = state_store.load()
    icon = pystray.Icon(
        "suivi_generiques",
        _make_icon_image(state.get("last_niveau", "ok")),
        "Suivi génériques",
        menu=pystray.Menu(
            pystray.MenuItem("Vérifier maintenant", _menu_check_now),
            pystray.MenuItem("Ouvrir la page", _menu_open_page),
            pystray.MenuItem("Reconnexion manuelle", _menu_reconnect),
            pystray.MenuItem("Quitter", _menu_quit),
        ),
    )
    threading.Thread(target=_background_loop, args=(icon,), daemon=True).start()
    icon.run()


if __name__ == "__main__":
    main()
