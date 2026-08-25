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
    KEYRING_KEYS,
    KEYRING_SERVICE,
    SECRET_PAGE_SLUG,
)
from thresholds import LaboStatus

_NIVEAU_LABEL = {"ok": "OK", "attention": "à surveiller", "urgent": "urgent"}


def render_html(statuses: list[LaboStatus], scrape_errors: dict[str, str], today: date | None = None) -> str:
    today = today or date.today()

    rows = "\n".join(
        f"""
        <tr class="niveau-{s.niveau}">
          <td>{s.repartiteur}</td>
          <td>{s.labo}</td>
          <td>{s.montant:.0f}€</td>
          <td>{s.seuil:.0f}€</td>
          <td>{"—" if s.atteint else f"{s.reste:.0f}€"}</td>
          <td>{_NIVEAU_LABEL[s.niveau]}</td>
        </tr>"""
        for s in statuses
    )

    errors_html = ""
    if scrape_errors:
        items = "".join(f"<li>{repartiteur} : données indisponibles</li>" for repartiteur in scrape_errors)
        errors_html = f'<div class="warning"><strong>Attention :</strong><ul>{items}</ul></div>'

    return f"""<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<title>Suivi seuils génériques</title>
<style>
  :root {{ color-scheme: light dark; }}
  body {{ font-family: system-ui, sans-serif; max-width: 720px; margin: 2rem auto; padding: 0 1rem; }}
  table {{ width: 100%; border-collapse: collapse; margin-top: 1rem; }}
  th, td {{ text-align: left; padding: 0.5rem; border-bottom: 1px solid #8884; }}
  .niveau-ok {{ color: #2a7; }}
  .niveau-attention {{ color: #c80; }}
  .niveau-urgent {{ color: #d33; font-weight: bold; }}
  .warning {{ background: #fee; border: 1px solid #d33; padding: 0.75rem; border-radius: 6px; margin-top: 1rem; }}
  .updated {{ color: #888; font-size: 0.85rem; margin-top: 2rem; }}
</style>
</head>
<body>
  <h1>Suivi seuils remise génériques</h1>
  <p>Montant du mois en cours par laboratoire et par répartiteur, comparé au seuil de remise.</p>
  {errors_html}
  <table>
    <thead>
      <tr><th>Répartiteur</th><th>Labo</th><th>Montant</th><th>Seuil</th><th>Reste à faire</th><th>Statut</th></tr>
    </thead>
    <tbody>{rows}
    </tbody>
  </table>
  <p class="updated">Dernière mise à jour : {datetime.now().strftime("%d/%m/%Y %H:%M")}</p>
</body>
</html>
"""


def _run_git(*args: str, extra_header: str | None = None) -> None:
    cmd = ["git", "-C", str(GITHUB_REPO_PATH)]
    if extra_header:
        cmd += ["-c", f"http.extraheader={extra_header}"]
    cmd += list(args)
    subprocess.run(cmd, check=True, capture_output=True, text=True)


def publish(statuses: list[LaboStatus], scrape_errors: dict[str, str], today: date | None = None) -> None:
    if not GITHUB_REPO_PATH.exists():
        raise RuntimeError(
            f"{GITHUB_REPO_PATH} n'existe pas encore. Clonez le dépôt GitHub Pages dédié à cet "
            "emplacement une première fois (cf. README) avant d'activer la publication."
        )

    html = render_html(statuses, scrape_errors, today)
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
