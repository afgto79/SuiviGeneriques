"""Configuration centrale de l'appli Suivi Génériques.

Rien de secret ici : tous les mots de passe/tokens vivent dans le
Gestionnaire d'identifiants Windows (via `keyring`), jamais dans ce fichier.
"""
from pathlib import Path

# --- Seuils métier ---
SEUIL_EUR = 350.0
JOURS_ALERTE = 7  # déclenche l'alerte "urgent" si <= 7 jours avant fin de mois

# Labos suivis en priorité, et mapping des libellés bruts de chaque portail
# vers un nom canonique commun (cf. plan : Viatris = Mylan chez OCP = "Viatris Santé" chez Alliance)
OCP_LABEL_MAP = {
    "BIOGARAN": "Biogaran",
    "MYLAN": "Viatris",
    "SANDOZ": "Sandoz",
}
ALLIANCE_LABEL_MAP = {
    "BIOGARAN": "Biogaran",
    "VIATRIS SANTE": "Viatris",
    "SANDOZ": "Sandoz",
}
TRACKED_LABS = ["Biogaran", "Viatris", "Sandoz"]

# --- Email ---
SENDER_EMAIL = "pharmacie.depremont@gmail.com"
RECIPIENT_EMAILS = ["pharmacie.depremont@gmail.com"]
SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587

# --- Portails ---
OCP_URL = "https://www.ocp-pharmalia.fr/ocp-pharmacien/pilotage/edata/mes-achats-generiques"
OCP_API_PATH = "/ocp-back/edata/achatGenerique"
ALLIANCE_URL = "https://my.alliance-healthcare.fr/group/pro/laboratoires-generiques#/turnover/generics"

# --- Répertoires locaux ---
BASE_DIR = Path(__file__).resolve().parent
PLAYWRIGHT_PROFILE_DIR = BASE_DIR / "browser_profile"  # OCP : relancé à chaque relevé (headless)
ALLIANCE_PROFILE_DIR = BASE_DIR / "browser_profile_alliance"  # Alliance : relancé à chaque relevé aussi
# La session CAS d'Alliance est portée par un cookie de session qui ne survit PAS à la
# fermeture propre de Chromium (vérifié le 25/08/2026 : l'extraction marche juste après
# connexion, mais échoue systématiquement après un close()/relaunch, même fraîchement
# authentifié) — contrairement à celle d'OCP. Playwright storage_state() capture les
# cookies (session compris) indépendamment de ce nettoyage : on sauvegarde l'état juste
# après connexion (first_login.py) et après chaque relevé réussi (app.py), et on le
# réinjecte à chaque lancement du contexte Alliance via launch_persistent_context(...,
# storage_state=...).
ALLIANCE_STORAGE_STATE_FILE = BASE_DIR / "alliance_storage_state.json"
STATE_FILE = BASE_DIR / "state.json"

# --- Publication GitHub Pages (page anonymisée à URL secrète) ---
# Chemin d'un clone local du dépôt GitHub dédié à la page (créé manuellement, cf. README).
GITHUB_REPO_PATH = BASE_DIR / "page_repo"
GITHUB_REMOTE_USER = "afgto79"
GITHUB_REMOTE_REPO = "SuiviGeneriques"
GITHUB_BRANCH = "main"
# Dépôt public (repo privé indisponible avec GitHub Pages sur un compte Free) :
# la page est donc publiée à la racine — un chemin secret n'apporterait plus rien
# puisque le dépôt lui-même est parcourable par n'importe qui. Le contenu de la
# page reste anonymisé (ni nom de pharmacie, ni email) : voir page_publisher.py.
SECRET_PAGE_SLUG = ""
PAGE_PUBLIC_URL = f"https://{GITHUB_REMOTE_USER}.github.io/{GITHUB_REMOTE_REPO}/"

# --- Minutage de la boucle interne (pas de Task Scheduler) ---
POLL_INTERVAL_MINUTES = 30
DAILY_CHECK_HOUR = 8   # heure locale à partir de laquelle le relevé quotidien peut tourner
EMAIL_WEEKDAY = 0      # 0 = lundi (datetime.weekday())

# --- Identifiants keyring (service name / usernames) ---
KEYRING_SERVICE = "suivi_generiques"
KEYRING_KEYS = {
    "gmail_app_password": "gmail_app_password",
    "github_token": "github_token",
}
