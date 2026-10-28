# Hackathon Watch — plan de travail

Objectif : chaque jour, un email avec les hackathons les plus pertinents pour mon profil (`profile.json`), sans doublons.

Légende : 🧑 = à faire par toi · 🤖 = Claude Code · modèle conseillé entre crochets.

---

## Principes de travail (Claude Code + IA agentique)

1. **Tranche verticale d'abord.** On fait marcher la chaîne complète (1 source → base → email) avant d'ajouter des sources ou du scoring malin. Un produit qui marche tôt vaut mieux qu'un produit parfait jamais terminé.
2. **Une session = une phase.** Lance une nouvelle session (ou `/clear`) à chaque phase. Le contexte reste petit, donc moins de tokens et moins d'erreurs.
3. **Le bon modèle pour chaque tâche.** Opus pour l'architecture et les décisions difficiles, Sonnet pour coder, Haiku pour les petites corrections. Effort bas par défaut, plus élevé seulement pour le design.
4. **Plan puis code.** Pour chaque phase non triviale : mode plan (Shift+Tab) → tu valides → Claude code.
5. **Les tests comme garde-fou.** Chaque source a un test sur une page sauvegardée (`tests/fixtures/`). Les tests tournent sans internet, sont rapides et ne coûtent aucun token pour relire une page web.
6. **Ne jamais coller une page web entière dans la conversation.** Les pages MLH (~600 Ko) ou Agorize (~1,4 Mo) coûteraient très cher en tokens. Claude doit extraire les bouts utiles par script (grep, sélecteurs).
7. **Un `CLAUDE.md` court dans le repo.** Il contient les commandes, l'architecture et les conventions. Claude le relit à chaque session, donc pas besoin de réexpliquer le projet.
8. **Commits petits et fréquents**, un par étape qui marche. Tu peux revenir en arrière facilement.
9. **Secrets hors du code.** Ils vont dans `.env` (jamais commité) en local et dans les GitHub Secrets en production. Tu les saisis toi-même.

---

## Phase 0 — Préparation 🧑 (≈ 20 min)

- [ ] 🧑 Me donner l'URL du repo privé GitHub.
- [ ] 🧑 Au premier `git push`, une fenêtre de connexion GitHub s'ouvre. C'est toi qui te connectes.
- [ ] 🧑 Créer le mot de passe d'application Gmail (myaccount.google.com/apppasswords).
- [ ] 🧑 Décider du scoring : règles seules (gratuit) ou règles + Claude API (plus pertinent, quelques centimes par jour). Si Claude API : créer une clé sur console.anthropic.com et définir une limite de dépense.
- [ ] 🧑 Plus tard, si besoin : clé API Kaggle.

## Phase 1 — Squelette du projet 🤖 [Sonnet]

- Structure `src/hackwatch/`, `tests/`, `pyproject.toml`, venv dans le projet.
- `CLAUDE.md`, `.env.example`, `.gitignore`.
- Modèle de données `Hackathon` (titre, url, dates, lieu, format, prize, tags, source, description).
- ✅ Terminé quand : `pytest` passe et le premier commit est poussé.

## Phase 2 — Tranche verticale 🤖 [Sonnet]

- Sources API JSON (les plus simples) : **Devpost** et **CTFtime**.
- `store.py` : SQLite, dédoublonnage par URL, mémorise ce qui a déjà été envoyé.
- `notify.py` : email HTML via SMTP Gmail.
- `main.py` : collecte → filtre simple (inscriptions ouvertes) → email des nouveautés.
- 🧑 Remplir `.env` et lancer `python -m hackwatch` une fois.
- ✅ Terminé quand : tu reçois un vrai email, et un 2ᵉ lancement n'envoie pas de doublons.

## Phase 3 — Scoring 🤖 [Opus pour le design, puis Sonnet]

- Étape 1, règles (gratuit) : mots-clés et poids de `profile.json`, filtres lieu/format/éligibilité, bonus prize.
- Étape 2, LLM (si choisi en phase 0) : uniquement sur les candidats qui passent les règles, avec Claude Haiku en lot. Retour : score + axe + une phrase « pourquoi ». C'est peu coûteux.
- Email trié par score, groupé par axe (IA technique, pro, entrepreneurial, deeptech).
- ✅ Terminé quand : sur 1 semaine de données, le top 5 te semble juste.

## Phase 4 — Autres sources 🤖 [Sonnet, une source = une petite tâche]

Ordre : lablab.ai → Agorize → MLH → Devfolio → Unstop (API interne) → dev.events.
Pour chacune : sauvegarder une page en fixture → écrire le parser → test → commit.
- ✅ Terminé quand : toutes les sources passent leurs tests.

## Phase 5 — Automatisation 🤖 + 🧑 [Sonnet]

- 🤖 Workflow GitHub Actions planifié (ex. chaque jour à 8 h). Il tourne même PC éteint et c'est gratuit pour cet usage.
- 🧑 Ajouter les secrets dans GitHub → Settings → Secrets (mot de passe Gmail, clé API).
- 🤖 Gestion d'erreurs : si une source casse, l'email le signale au lieu de planter.
- ✅ Terminé quand : 3 jours d'emails reçus sans intervention.

## Phase 6 — Amélioration continue 🧑 + 🤖

- 🧑 Noter les hackathons reçus (intéressant / pas intéressant), par exemple avec un lien dans l'email.
- 🤖 Ajuster les poids du profil à partir de tes retours.
- Idées : ajouter les newsletters ESSEC, Kaggle, un rappel avant les deadlines d'inscription.

---

## Récap de ce que toi seul peux faire

| Quand | Action |
|---|---|
| Phase 0 | URL du repo, connexion GitHub au premier push, mot de passe d'application Gmail, choix et création de la clé Claude API |
| Phase 2 | Remplir `.env`, vérifier l'email reçu |
| Phase 3 | Juger la pertinence du top 5 |
| Phase 5 | Ajouter les GitHub Secrets |
| Ensuite | Donner ton avis sur les emails |
