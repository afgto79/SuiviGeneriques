# Suivi Génériques — appli résidente

Appli en fond de tâche (barre système) qui vérifie chaque jour vos achats de
génériques Biogaran/Viatris/Sandoz chez OCP Pharmalia et Alliance
Healthcare/Cencora, envoie un email récap chaque lundi, et publie une page de
compteurs (anonymisée, URL secrète) mise à jour quotidiennement.

**Aucune tâche planifiée Windows** : c'est un seul processus qui reste ouvert
et gère lui-même son minutage. Aucun mot de passe des portails n'est jamais
saisi par le code — la session est établie une fois, manuellement, par vous.

## Installation (à faire une fois)

### 1. Dépendances Python

```bash
cd SuiviGeneriques
pip install -r requirements.txt
playwright install chromium
```

### 2. Dépôt GitHub pour la page (optionnel mais recommandé)

1. Créez un dépôt **privé** sur GitHub (ex. `remises-generiques-page`).
2. Activez GitHub Pages dessus (Settings → Pages → branche `main`, dossier racine).
3. Notez l'URL générée (ex. `https://votreuser.github.io/remises-generiques-page/`)
   — c'est votre "URL secrète", ne la partagez nulle part.
4. Clonez-le localement à l'emplacement attendu par l'appli :
   ```bash
   git clone https://github.com/<vous>/remises-generiques-page.git page_repo
   ```
   (dans le dossier `SuiviGeneriques`, à côté de `app.py`)
5. Générez un **Personal Access Token** GitHub (Settings → Developer settings →
   Personal access tokens → scope `repo` suffit).
6. Ouvrez [config.py](config.py) et renseignez `GITHUB_REMOTE_USER`,
   `GITHUB_REMOTE_REPO` et `PAGE_PUBLIC_URL` avec vos valeurs.

Si vous préférez ne pas avoir de page du tout, laissez `page_repo` absent —
l'appli continuera de fonctionner (email uniquement), `publish_page` échouera
proprement et sera juste ignorée dans les logs.

### 3. Mot de passe d'application Gmail

Compte Google → Sécurité → Validation en 2 étapes → Mots de passe des
applications → générez-en un pour "Suivi Génériques". **Ce n'est pas votre
mot de passe Gmail habituel.**

### 4. Enregistrer les secrets

```bash
python credentials_setup.py
```

Vous saisissez vous-même (saisie masquée) le mot de passe d'application Gmail
et le token GitHub. Tout est stocké dans le Gestionnaire d'identifiants
Windows, jamais dans un fichier.

### 5. Connexion initiale aux portails

```bash
python first_login.py
```

Une fenêtre Chromium s'ouvre. Connectez-vous vous-même sur OCP puis sur
Alliance (identifiants + code de vérification si demandé), exactement comme
d'habitude. La session est ensuite réutilisée automatiquement par l'appli.

> À relancer si l'icône passe au rouge (session expirée) — via le menu de
> l'appli ("Reconnexion manuelle") ou directement en ligne de commande.

### 6. Lancement automatique au démarrage de Windows

1. `Win + R` → tapez `shell:startup` → Entrée (ouvre le dossier Démarrage).
2. Créez un raccourci vers :
   ```
   pythonw.exe "C:\Users\operateur\CascadeProjects\SuiviGeneriques\app.py"
   ```
   (`pythonw.exe`, pas `python.exe`, pour éviter une fenêtre de console qui reste ouverte)
3. Redémarrez le PC, ou double-cliquez le raccourci pour tester tout de suite.

## Utilisation

Une icône colorée apparaît dans la barre système (zone en bas à droite, flèche
"^" si masquée) :
- 🟢 vert : tout va bien
- 🟠 orange : un labo est à surveiller ce mois-ci
- 🔴 rouge : reconnexion manuelle nécessaire (session expirée)

Clic droit dessus :
- **Vérifier maintenant** : lance un relevé immédiat (et envoie l'email si
  pas encore fait cette semaine).
- **Ouvrir la page** : ouvre la page de compteurs dans le navigateur.
- **Reconnexion manuelle** : relance `first_login.py`.
- **Quitter**.

## En cas de souci

L'appli tourne sans fenêtre (`pythonw.exe`) : tout ce qui ne remonte pas via
l'icône (erreurs inattendues, échec d'envoi d'email, token GitHub expiré...)
est écrit dans `app.log`, à côté de `app.py`. En cas de doute, ouvrez-le
avec un éditeur de texte.

## Fichiers

Voir le plan d'implémentation pour le détail de l'architecture et des méthodes
d'extraction validées par portail.
