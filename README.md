# Orsay Gestion : rapprochement des positions et assistant gérants

Cas pratique SAIFY. Cadrage, décisions et limites : `NOTES.md`. Schémas : `ARCHITECTURE.md`.

## Installation et lancement (PowerShell)
Prérequis : Python 3.11+ et [uv](https://docs.astral.sh/uv/).

```powershell
uv sync
uv run pytest
uv run streamlit run app.py
```

Puis ouvrir http://localhost:8501.
- Onglet **Rapprochement** : les fichiers du dossier `donnees/` sont rapprochés dès l'ouverture. Pour d'autres fichiers : section « Déposer d'autres fichiers ».
- Onglet **Questions** : nécessite un fichier `.env` à la racine avec `ANTHROPIC_API_KEY` (non versionné). Sans clé valide, l'onglet affiche l'erreur ; le rapprochement n'en dépend pas.

Sorties (Excel et journal d'audit JSON) : dossier `sorties/` (non versionné).

## Choix principaux
- **Besoin 1 en premier, 100 % déterministe** : lecture des 4 formats, contrôles de fichier (date, compteurs), comparaison exacte en `Decimal` par (fonds, ISIN, conservateur), typage QTE / ABS_DEP / ABS_INT / DEP selon le paramétrage. Aucune correction automatique : l'outil constate et exporte.
- **Besoin 2 sans calcul par le LLM** : le LLM choisit une requête SQL figée (lecture seule) puis rédige une phrase ; un garde-fou rejette la phrase si elle cite un nombre absent du résultat. Le tableau et la requête source sont toujours affichés.
- **Repli automatique si le modèle refuse** : paramètre `fallbacks="default"` (beta `server-side-fallback-2026-07-01`). En cas de refus, l'API relance la même requête sur le modèle recommandé par Anthropic pour ce type de refus ; l'interface indique alors quel modèle a répondu. Si toute la chaîne refuse, l'erreur est affichée.
- Paramètres dans `config.toml`. Détail et alternatives écartées : `NOTES.md`, section Décisions.

## Structure
| Chemin | Rôle |
|---|---|
| `config.toml` | Paramètres (date d'arrêté, fichiers, règles, modèle) |
| `reco/loaders.py` | Lecture et contrôle des fichiers, lignes écartées/rejetées |
| `reco/reconcile.py` | Comparaison, typage des suspens, informations issues de la base |
| `reco/report.py` | Export Excel, texte récapitulatif, journal d'audit |
| `assistant/tools.py` | 3 requêtes SQL en lecture seule (encours, échéances, non dénoués) |
| `assistant/agent.py` | Routage LLM, synthèse, repli sur refus, garde-fou sur les nombres |
| `app.py` | Interface Streamlit |
| `tests/` | 30 tests pytest |

## Ce qui marche
- Rapprochement : les 7 suspens attendus sur les données du 25/09/2026, pièges compris (sous-comptes, lots, annulation, P3G, ligne sans sous-compte, libellés BNP/BP2S).
- Export Excel 3 onglets, récapitulatif à copier, journal d'audit horodaté avec empreinte des fichiers.
- Assistant : encours valorisé d'un fonds, échéances à N jours, opérations non dénouées, avec repli automatique si le modèle refuse.

## Ce qui manque
- Outils assistant : concentration par émetteur, origine d'un suspens.
- Suivi des suspens (statut traité, historique), envoi du point de situation (volontairement manuel).
- Contrôle de fichier A/C structurellement corrompu (exception non gérée), test automatisé de l'interface.
- Hébergement de production (datacenter client / SecNumCloud, LLM local) : décrit dans `NOTES.md`, non réalisé.

## Vérifié par qui
**Exécuté par l'assistant de code pendant la session** (résultats réels) :
- `uv run pytest` : 30 tests passent.
- Interface lancée dans un navigateur : 7 suspens affichés dès l'ouverture (3 QTE, 2 ABS_DEP, 1 ABS_INT, 1 DEP), aucune erreur serveur.
- Appels réels à l'API : « Combien vaut Orsay Obligations au cours de clôture ? » -> total 724836.0, phrase acceptée par le garde-fou ; « Quelles opérations ne sont pas encore dénouées ? » (avec le repli activé) -> 2 opérations, requête acceptée par l'API.
- Non vérifié en réel : le déclenchement du repli (aucun refus n'a pu être provoqué) ; ce chemin est couvert uniquement par un test avec client simulé.

Après toute modification du code, redémarrer Streamlit : il ne recharge pas les modules importés (`reco/`, `assistant/`).

**À vérifier par moi avant la restitution** :
- [ ] Relancer `uv run pytest` et `uv run streamlit run app.py` sur le poste.
- [ ] Contrôler à la main 2 suspens dans les fichiers bruts (SCHNEIDER, AFD).
- [ ] Recalculer un encours obligataire (nominal x cours / 100).
- [ ] Poser une question hors périmètre et vérifier la réponse « je ne sais pas ».
