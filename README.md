# Orsay Gestion : rapprochement des positions et assistant gérants

Cas pratique SAIFY. Cadrage et décisions : `NOTES.md`. Schémas : `ARCHITECTURE.md`.

## Installation et lancement (PowerShell)
Prérequis : Python 3.11+ et [uv](https://docs.astral.sh/uv/).

```powershell
uv sync
uv run pytest
uv run streamlit run app.py
```

Pour l'onglet Questions : un fichier `.env` à la racine avec `ANTHROPIC_API_KEY` (non versionné).

## Structure
| Chemin | Rôle |
|---|---|
| `config.toml` | Paramètres (date d'arrêté, fichiers, règles, modèle) |
| `reco/` | Besoin 1 : rapprochement déterministe |
| `assistant/` | Besoin 2 : assistant LLM à outils en lecture seule |
| `app.py` | Interface Streamlit |
| `tests/` | Tests pytest |
| `donnees/` | Fichiers fournis par le client |
