"""Génère la page de compteurs (HTML statique, anonymisé) et la publie sur GitHub Pages.

Contenu strictement anonymisé : uniquement labo / répartiteur / montant / reste.
Aucun nom de pharmacie, d'utilisateur, d'email ou d'identifiant de compte.

Publication : commit + push vers un clone local du dépôt GitHub Pages dédié
(cf. README pour la création initiale du dépôt). Le token n'est jamais écrit sur
disque : il est passé uniquement en en-tête HTTP le temps du push, via `git -c
http.extraheader=...`, jamais persisté dans .git/config.
"""
from __future__ import annotations

import base64
import subprocess
from datetime import date, datetime

import keyring

from config import (
    GITHUB_BRANCH,
    GITHUB_REMOTE_REPO,
    GITHUB_REMOTE_USER,
    GITHUB_REPO_PATH,
    JOURS_ALERTE,
    KEYRING_KEYS,
    KEYRING_SERVICE,
    SECRET_PAGE_SLUG,
    SEUIL_EUR,
)
from thresholds import LaboStatus, jours_restants_dans_le_mois

# Une section par répartiteur, dans l'ordre d'affichage : titre court + couleurs de marque
# (Cencora = violet, OCP = vert). "Alliance Healthcare" est le nom de Cencora en France.
_SECTIONS = [
    ("Alliance Healthcare", "CENCORA", "cencora"),
    ("OCP Pharmalia", "OCP", "ocp"),
]


def _euros(montant: float) -> str:
    return f"{montant:,.0f}".replace(",", "\u202f") + "\u00a0€"


def _render_section(repartiteur: str, titre: str, css: str, statuses: list[LaboStatus],
                    scrape_errors: dict[str, str], data_dates: dict[str, date]) -> str:
    lignes = [s for s in statuses if s.repartiteur == repartiteur]
    if lignes:
        rows = "".join(
            f"""
          <tr class="niveau-{s.niveau}">
            <td>{s.labo}</td>
            <td>{"OK" if s.atteint else _euros(s.reste)}</td>
            <td>{_euros(s.montant)}<div class="barre"><span style="width:{min(100, s.montant / s.seuil * 100):.0f}%"></span></div></td>
          </tr>"""
            for s in lignes
        )
    else:
        rows = '\n          <tr><td colspan="3" class="indispo">Données indisponibles</td></tr>'

    if repartiteur in scrape_errors:
        note = '<p class="note alerte">Données indisponibles lors du dernier relevé</p>'
    elif repartiteur in data_dates:
        note = f'<p class="note">Données au {data_dates[repartiteur].strftime("%d/%m/%Y")}</p>'
    else:
        note = ""

    return f"""
  <section class="{css}">
    <h2>{titre}</h2>
    <table>
      <thead><tr><th>Labo</th><th>Reste à faire</th><th>Montant actuel</th></tr></thead>
      <tbody>{rows}
      </tbody>
    </table>
    {note}
  </section>"""


def render_html(
    statuses: list[LaboStatus],
    scrape_errors: dict[str, str],
    today: date | None = None,
    data_dates: dict[str, date] | None = None,
) -> str:
    today = today or date.today()
    # Pas d'échappement dans les expressions d'f-string (Python 3.11) : textes préparés ici.
    seuil = _euros(statuses[0].seuil if statuses else SEUIL_EUR)
    jours = jours_restants_dans_le_mois(today)
    echeance = "Dernier jour du mois" if jours == 0 else f"J-{jours} avant la fin du mois"
    echeance_css = "echeance proche" if jours <= JOURS_ALERTE else "echeance"
    sections = "".join(
        _render_section(repartiteur, titre, css, statuses, scrape_errors, data_dates or {})
        for repartiteur, titre, css in _SECTIONS
    )

    return f"""<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Suivi seuils génériques</title>
<style>
  :root {{
    color-scheme: light dark;
    --bg: #f6f5f8; --card: #ffffff; --text: #1d1b22; --muted: #6f6a78; --line: #e7e4ec;
    --ok: #17875a; --attention: #c77700; --urgent: #d12c2c;
    --cencora: #461e96; --cencora-tint: #ece6f7;
    --ocp: #00843d; --ocp-tint: #e3f3e8;
  }}
  @media (prefers-color-scheme: dark) {{
    :root {{
      --bg: #141218; --card: #1e1b24; --text: #ece9f1; --muted: #9a94a5; --line: #2f2b37;
      --ok: #3ccf8e; --attention: #f0a53a; --urgent: #ff6b6b;
      --cencora: #b597f0; --cencora-tint: #2b2240;
      --ocp: #4cc97c; --ocp-tint: #1b3326;
    }}
  }}
  * {{ box-sizing: border-box; }}
  body {{ margin: 0; background: var(--bg); color: var(--text);
         font-family: "Segoe UI", system-ui, -apple-system, sans-serif; }}
  main {{ max-width: 640px; margin: 0 auto; padding: 2rem 16px 3rem; }}
  h1 {{ font-size: 1.5rem; margin: 0 0 0.25rem; letter-spacing: -0.01em; }}
  .intro {{ color: var(--muted); margin: 0 0 1.75rem; }}
  section {{ background: var(--card); border-radius: 12px; margin-bottom: 1.5rem; overflow: hidden;
             box-shadow: 0 1px 3px #0000000f, 0 4px 16px #00000008; border-top: 5px solid var(--brand); }}
  section.cencora {{ --brand: var(--cencora); --tint: var(--cencora-tint); }}
  section.ocp {{ --brand: var(--ocp); --tint: var(--ocp-tint); }}
  h2 {{ margin: 0; padding: 1rem 1.25rem 0.75rem; text-align: center; color: var(--brand);
        font-size: 1.6rem; font-weight: 800; letter-spacing: 0.04em; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 1.05rem; }}
  th {{ background: var(--tint); color: var(--brand); text-align: left; font-weight: 700;
        padding: 0.6rem 1.25rem; font-size: 0.9rem; }}
  td {{ padding: 0.7rem 1.25rem; border-bottom: 1px solid var(--line); }}
  th:not(:first-child), td:not(:first-child) {{ text-align: right; font-variant-numeric: tabular-nums; }}
  tbody tr:last-child td {{ border-bottom: none; }}
  .niveau-ok {{ color: var(--ok); }}
  .niveau-attention {{ color: var(--attention); font-weight: 600; }}
  .niveau-urgent {{ color: var(--urgent); font-weight: 700; }}
  .indispo {{ color: var(--muted); font-style: italic; text-align: center !important; }}
  .note {{ margin: 0; padding: 0.6rem 1.25rem 0.9rem; color: var(--muted); font-size: 0.8rem; text-align: right; }}
  .note.alerte {{ color: var(--urgent); font-weight: 600; }}
  .echeance {{ display: inline-block; margin-top: 0.5rem; padding: 0.15rem 0.65rem; border-radius: 999px;
               background: var(--line); color: var(--text); font-size: 0.85rem; font-weight: 600; }}
  .echeance.proche {{ background: var(--urgent); color: #fff; }}
  .barre {{ height: 4px; margin: 0.35rem 0 0 auto; width: 7rem; max-width: 100%;
           background: var(--line); border-radius: 2px; overflow: hidden; }}
  .barre span {{ display: block; height: 100%; background: currentColor; }}
  .updated {{ color: var(--muted); font-size: 0.8rem; text-align: center; }}
</style>
</head>
<body>
<main>
  <h1>Suivi seuils remise génériques</h1>
  <p class="intro">Achats du mois en cours par laboratoire · seuil de remise {seuil}<br>
    <span class="{echeance_css}">{echeance}</span></p>
  {sections}
  <p class="updated">Dernier relevé : {datetime.now().strftime("%d/%m/%Y %H:%M")}</p>
</main>
</body>
</html>
"""


def _run_git(*args: str, extra_header: str | None = None) -> None:
    cmd = ["git", "-C", str(GITHUB_REPO_PATH)]
    if extra_header:
        cmd += ["-c", f"http.extraheader={extra_header}"]
    cmd += list(args)
    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as e:
        # La commande brute contient l'en-tête d'authentification (token en base64) :
        # on la ré-émet masquée, sans chaînage, pour qu'elle n'atterrisse jamais dans app.log.
        safe_cmd = ["http.extraheader=<masqué>" if c.startswith("http.extraheader=") else c for c in cmd]
        raise subprocess.CalledProcessError(e.returncode, safe_cmd, e.stdout, e.stderr) from None


def publish(
    statuses: list[LaboStatus],
    scrape_errors: dict[str, str],
    today: date | None = None,
    data_dates: dict[str, date] | None = None,
) -> None:
    if not GITHUB_REPO_PATH.exists():
        raise RuntimeError(
            f"{GITHUB_REPO_PATH} n'existe pas encore. Clonez le dépôt GitHub Pages dédié à cet "
            "emplacement une première fois (cf. README) avant d'activer la publication."
        )

    html = render_html(statuses, scrape_errors, today, data_dates)
    target_dir = GITHUB_REPO_PATH / SECRET_PAGE_SLUG if SECRET_PAGE_SLUG else GITHUB_REPO_PATH
    target_dir.mkdir(parents=True, exist_ok=True)
    (target_dir / "index.html").write_text(html, encoding="utf-8")
    relative_path = f"{SECRET_PAGE_SLUG}/index.html" if SECRET_PAGE_SLUG else "index.html"

    token = keyring.get_password(KEYRING_SERVICE, KEYRING_KEYS["github_token"])
    if not token:
        raise RuntimeError("Token GitHub introuvable dans le Gestionnaire d'identifiants. Lancez credentials_setup.py.")

    auth_value = base64.b64encode(f"{GITHUB_REMOTE_USER}:{token}".encode()).decode()
    extra_header = f"AUTHORIZATION: basic {auth_value}"

    _run_git("add", relative_path)
    # Rien à committer si les chiffres n'ont pas changé : on ignore l'erreur dans ce cas précis.
    try:
        _run_git("commit", "-m", f"Mise à jour {datetime.now().isoformat(timespec='minutes')}")
    except subprocess.CalledProcessError as e:
        if "nothing to commit" not in (e.stdout or "") + (e.stderr or ""):
            raise
        return
    _run_git("push", "origin", GITHUB_BRANCH, extra_header=extra_header)
