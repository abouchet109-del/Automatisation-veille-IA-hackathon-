# Hackathon Watch

Envoie chaque jour par email les hackathons pertinents pour le profil de `profile.json`.
Plan de travail par phases : `PLAN.md`. Une session = une phase.

## Commandes (Windows, venv dans le projet)
- Setup : `$env:PIP_CACHE_DIR="D:\Tools\pip-cache"; python -m venv .venv; .venv\Scripts\pip install -e .[dev]`
- Tests : `.venv\Scripts\python -m pytest`
- Aperçu sans envoi : `.venv\Scripts\python -m hackwatch --dry-run`
- Envoi réel : `.venv\Scripts\python -m hackwatch`

## Architecture (`src/hackwatch/`)
- `models.py` : dataclass `Hackathon` (modèle commun à toutes les sources).
- `sources/<nom>.py` : une source = `fetch() -> list[Hackathon]` + `parse(data)` pur et testable.
- `scoring.py` : `score(h, profile)` (axes, bonus, malus) et `select` (seuil, 15 max, 3 CTFtime max).
  - Par axe : somme des mots-clés trouvés, × 1 si dans le titre, 0,6 dans les tags, 0,5 dans la description ; un mot de `mots_generiques` vaut 0,4 d'un mot de `mots_cles`. Axe = poids × (1 − e^(−somme/1,2)) : progressif, jamais saturé.
  - Score = meilleur axe + 0,05 par autre axe ≥ 0,2 (max 0,1) + lieu France 0,15 + prize ≥ 1 k 0,05 / ≥ 10 k 0,1 + débutant 0,05 ; − 0,5 éligibilité incompatible, − 0,3 qualification hors de France.
  - Casse : mot en minuscules = insensible + pluriel ; acronyme ou marque (« AI », « Meta ») = casse exacte ou TOUT MAJUSCULES.
- `llm.py` : re-scoring optionnel Claude Haiku, actif seulement si `ANTHROPIC_API_KEY` (extra `[llm]`).
- `filters.py` : filtre simple (inscriptions ouvertes, en ligne / Paris / France).
- `store.py` : SQLite `hackwatch.db`, dédoublonnage par URL, trace des envois.
- `notify.py` : email HTML via SMTP Gmail (SSL 465).
- `main.py` : collecte → filtre → nouveautés → email (`--dry-run` pour afficher ; `--all` ajoute les éléments sous le seuil ou déjà envoyés, pour calibrer).

## Conventions
- Tests sur fixtures dans `tests/fixtures/` (réponses réelles tronquées), jamais d'appel réseau.
- Nouvelle source : sauvegarder une fixture, écrire `parse`, tester, committer.
- Ne jamais coller de grosses réponses web dans la conversation : extraire par script.
- Tout sur D:, rien sur C: (cache pip sur `D:\Tools\pip-cache`).
- Commits en français, petits et fréquents.
- **Ne jamais lire ni afficher `.env`** (secrets Gmail) ; ne jamais le commiter. Modèle : `.env.example`.
