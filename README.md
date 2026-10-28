# Hackathon Watch

Veille de hackathons : l'outil interroge 9 sources (Devpost, CTFtime, Luma, Agorize, lablab, MLH, Devfolio, Unstop, dev.events), note chaque hackathon selon `profile.json` et t'envoie par email les nouveaux plus pertinents (en ligne ou à Paris / Île-de-France). Un hackathon déjà envoyé n'est jamais renvoyé.

## Lancer en local

```powershell
$env:PIP_CACHE_DIR="D:\Tools\pip-cache"; python -m venv .venv; .venv\Scripts\pip install -e .[dev]
.venv\Scripts\python -m pytest              # tests
.venv\Scripts\python -m hackwatch --dry-run # aperçu sans email
.venv\Scripts\python -m hackwatch           # envoi réel (identifiants Gmail dans .env, voir .env.example)
```

## Automatisation (GitHub Actions)

Le workflow `.github/workflows/hackwatch.yml` tourne tout seul le dimanche et le jeudi vers 8 h (Paris), PC éteint. Il garde l'historique des envois dans `state/hackwatch.db` (commité automatiquement). Si toutes les sources échouent, le workflow est en erreur et GitHub t'envoie un email.

À faire une seule fois :

1. Sur GitHub, ouvre le dépôt → **Settings → Secrets and variables → Actions → New repository secret**.
2. Crée 3 secrets : `GMAIL_ADDRESS` (ton adresse Gmail), `GMAIL_APP_PASSWORD` (mot de passe d'application Gmail), `EMAIL_TO` (adresse qui reçoit l'email).
3. Lance un premier run : onglet **Actions → Hackathon Watch → Run workflow**.
