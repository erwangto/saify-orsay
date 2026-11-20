# Notes

## Métier
**Besoin du client (Orsay Gestion, middle office)**
1. Rapprocher chaque matin l'inventaire interne (PMS) avec les relevés des 3 conservateurs, lister les suspens avec l'action à mener, produire un point de situation sans ressaisie.
2. Permettre aux gérants / RCCI d'interroger la base de gestion en langage naturel, avec la source de chaque chiffre, sans aucune possibilité de modifier les données.

**Règles de gestion (reformulées)**
- Source : `positions_internes.csv` vs relevés A, B, C. `orsay.db` = information seulement, jamais référence.
- Clé de rapprochement : (fonds, ISIN, conservateur). Quantité = nb de titres (actions) ou nominal (obligations).
- Sous-comptes PMS d'un même fonds : on additionne avant de comparer (le conservateur ne voit qu'un compte par fonds).
- Exclus : sous-compte `P3G` (compte technique), ligne sans sous-compte (saisie incomplète), mouvement annulé chez le conservateur (`ACTION=S` dans C).
- Libellé conservateur côté PMS : CACEIS -> A, EUROCLEAR -> B, BNP / BP2S -> C.
- Tolérance zéro : 1 unité d'écart = suspens.
- Typologie (parametrage.xlsx) : QTE, ABS_DEP, ABS_INT, DEP. Titre attendu chez X mais trouvé chez Y = **un seul** suspens DEP (pas ABS_DEP + ABS_INT).

**Glossaire**
- FCP : fonds commun de placement (ici 3 : Patrimoine, Obligations, Actions Europe).
- PMS : Portfolio Management System, l'outil de gestion interne qui tient l'inventaire.
- Conservateur / dépositaire (teneur de compte-conservateur) : banque qui détient réellement les titres du fonds.
- Middle office : équipe qui contrôle et rapproche les positions entre front (gérants) et conservateurs.
- Rapprochement : comparer deux sources ligne à ligne pour trouver les écarts.
- Suspens : ligne qui ne tombe pas juste entre les deux sources.
- ISIN : identifiant unique d'un titre (12 caractères, ex. FR0000012965).
- Date de négociation vs dénouement : le PMS enregistre à la signature (J), le conservateur au règlement-livraison (J+2). Source naturelle d'écarts temporaires.
- CSDR : règlement européen qui pénalise les règlements-livraisons en retard.
- RCCI : responsable conformité et contrôle interne.
- Nominal : montant facial d'une obligation ; la quantité obligataire s'exprime en nominal.
- Cours en % du nominal, pied de coupon : valeur obligation = nominal x cours / 100, sans intérêts courus.
- Transco (transcodification) : table de correspondance code externe -> fonds.

**Anomalies observées dans les données (exploration, à confirmer par les tests)**
- CSV : ISIN avec espaces et minuscules (` fr0000014078 `), libellés conservateur hétérogènes, 1 ligne sans sous-compte (SANOFI 12345), 1 ligne P3G (BTF 999999).
- Relevé A : ligne titre + ligne vide avant l'en-tête, quantités en texte avec séparateur de milliers (`"225 000"`).
- Relevé B : largeur fixe, 2 décimales implicites, fins de ligne Windows, ligne de contrôle T000013 (13 lignes, cohérent).
- Relevé C : XML avec namespace, une annulation `S` (RTE lot 2), une position en 2 lots (HERMES 10000 + 15000). NbItems = 9, cohérent.
- Suspens attendus (8 lignes brutes -> 7 suspens) :
  - SCHNEIDER / Actions / A : 250 000 vs 225 000 -> QTE (achat 25 000 du 24/09 non dénoué, mouvement 19).
  - SAFRAN / Actions / B : 40 000 vs 41 000 -> QTE (vente 1 000 du 25/09 non dénouée, mouvement 20).
  - SFIL 3% 2033 / Obligations / C : 100 000 vs 50 000 -> QTE, sans opération explicative dans la base.
  - EDF 4% 2031 / Obligations / A : absent chez A -> ABS_DEP.
  - FR0000012966 "ISIN SAISI A LA MAIN" / Obligations / A : absent chez A et inconnu du référentiel -> ABS_DEP (probable faute de frappe).
  - AFD 3.5% 2035 / Obligations : attendu chez A (CACEIS), trouvé chez B -> **un** DEP.
  - LVMH 3.25% 2029 (FR0000999914) / Obligations / B : absent du PMS -> ABS_INT.
- Pièges qui doivent tomber juste : KERING (2 sous-comptes), TOTALENERGIES, HERMES (2 sous-comptes + 2 lots), OAT 2039 (PMS "BNP" et "BP2S"), RTE (annulation), SANOFI (ligne sans sous-compte exclue).
- Environnement : `.env` indique une expiration de la clé au 08/11/2026 (à vérifier). L'énoncé dit le dépôt git initialisé, mais aucun `.git` trouvé.

**Hypothèses (non tranchées en cadrage, prises par défaut)**
- H1 Normalisation ISIN : espaces retirés + majuscules. Pas de contrôle de clé ISIN (les ISIN fictifs pourraient échouer).
- H2 Conservateur côté PMS : reconnu par mot-clé dans le libellé (CACEIS -> A, EUROCLEAR -> B, BNP ou BP2S -> C), insensible à la casse. Libellé non reconnu = ligne rejetée.
- H3 Quantités comparées en `Decimal` (pas de float) pour respecter la tolérance zéro sans erreur d'arrondi.
- H4 Lots du conservateur C additionnés par (compte, ISIN) ; seules les lignes `ACTION=C` comptent, les `S` vont en « écartées ».
- H5 Contrôles fichiers : date d'arrêté = date attendue (config) pour A (titre), B (en-tête), C (DateArrete), CSV (colonne) ; trailer B = nb de lignes D ; NbItems C = nb d'Item (annulations comprises).
- H6 Paramètres (date d'arrêté, chemins, version des règles, taille max de boucle agent, modèle LLM) dans `config.toml`.
- H7 Lecture de `orsay.db` toujours en SQLite read-only (`mode=ro`), pour le rapprochement (info) comme pour l'assistant.
- H8 Opération candidate d'un QTE : mouvement `EN_ATTENTE` du même fonds et ISIN dans la base (info seulement).
- H9 Assistant : modèle Claude récent via l'API fournie (`ANTHROPIC_API_KEY` lu depuis `.env`), boucle bornée à 3 tours. Si la clé est invalide/expirée, l'onglet affiche l'erreur ; les outils restent testés sans LLM.
- H10 Python géré avec uv ; `requires-python >= 3.11` (le poste annonce 3.12).
- H11 Hébergement cible en production : datacenter du client ou SecNumCloud, LLM local ou hébergé SecNumCloud ; l'API Anthropic publique n'est utilisée que pour la démo sur données fictives.

## Décisions
| Étape | Choix | Raison | Alternative écartée |
|---|---|---|---|
| Cadrage | Besoin 1 d'abord, de bout en bout ; besoin 2 ensuite si le temps le permet, sinon décrit en architecture | Priorisation évaluée ; le besoin 1 est prouvable par tests | Faire les deux à moitié |
| Cadrage | Python + pandas + pytest + Streamlit | Un seul langage, lancement en une commande, démo simple | FastAPI + React (trop long en 1 h) |
| Cadrage | Terme unique **Fonds**, clé = libellé de la transco (`ORSAY PATRIMOINE`) | 3 noms pour un concept (fonds / entite / portefeuille) | Codes PAT/OBL/ACT de la base (source non de référence) |
| Cadrage | Écart expliqué par une opération en attente = suspens QTE conservé + opération candidate affichée pour info | Tolérance zéro, l'humain clôt ; la base sert à s'informer | Justifier automatiquement l'écart |
| Cadrage | DEP rapproché sur (Fonds, ISIN) ; un seul suspens même si la quantité diffère aussi (mention affichée) | Règle « un seul suspens » | DEP + QTE |
| Cadrage | Fichier incohérent (date, compteur) bloqué avec message ; ligne inconnue (compte, libellé) rejetée avec motif | Ne pas fabriquer de faux suspens, rien d'écarté en silence | Tout bloquer / tout ignorer |
| Cadrage | Lignes exclues par règle (P3G, sans sous-compte, annulation) affichées avec le motif | Traçabilité RCCI | Exclusion silencieuse |
| Cadrage | Export Excel (suspens, écartées/rejetées, contrôles) + texte récapitulatif à copier, pas d'envoi auto ; journal d'audit JSON par exécution | Point de situation sans ressaisie, envoi = acte humain, principe d'audit | Envoi d'email automatique |
| Cadrage | Ordre : besoin 1 testé et commité, puis besoin 2 ; sur « stop besoin 2 », il bascule en architecture | Sécuriser le livrable fiable | Paralléliser |
| Cadrage | Assistant = LLM qui choisit parmi des **outils prédéfinis** (fonctions Python testées, SQL lecture seule) ; hors outils -> « je ne sais pas » | Aucun chiffre calculé par le LLM, source connue, lecture seule par construction | Text-to-SQL libre |
| Cadrage | Réponse = tableau de l'outil + phrase LLM (pydantic) + source ; garde-fou : chaque nombre de la phrase doit figurer dans le résultat, sinon tableau seul + avertissement | « Un chiffre inventé = incident » | Afficher le texte LLM tel quel |
| Cadrage | Assistant basé sur `orsay.db` (positions, cours à la date de config) ; obligations/BTF = nominal x cours / 100, actions = quantité x cours | Le client veut des réponses « tirées de notre base » | Utiliser le CSV du rapprochement |
| Cadrage | ISIN inconnu du référentiel : ABS_DEP conservé + mention « ISIN absent du référentiel » | Info utile, typologie inchangée | Nouveau type de suspens |
| Cadrage | Streamlit 2 onglets (Rapprochement, Questions), bouton « fichiers d'exemple » | Démo directe | Plusieurs pages / CLI |
| Cadrage | Agent à outils plutôt que RAG pour le besoin 2 | Données structurées (SQL) et questions de calcul (sommes, valorisation) : un RAG ferait calculer le LLM sur des extraits partiels | RAG (pertinent plus tard pour des documents : prospectus, procédures) |
| Cadrage | Aucun statut « traité » ni modification : l'outil constate et exporte | Pas d'action engageante, périmètre minimal | Suivi des suspens (en « suite ») |

## Architecture
Légende : [D] code déterministe, [LLM] modèle de langage, [H] humain

```
BESOIN 1 - RAPPROCHEMENT
[H] dépose CSV PMS + A.xlsx + B.txt + C.xml + parametrage.xlsx
        |
[D] loaders : lecture + contrôles fichier (date, compteurs)
        |      -> lignes écartées (P3G, sans sous-compte, annulation) + rejetées (inconnues)
[D] normalisation : (Fonds, ISIN, Conservateur, Quantité Decimal), somme sous-comptes / lots
        |
[D] reconcile : comparaison exacte -> QTE / ABS_DEP / ABS_INT / DEP (+ action du paramétrage)
        |      <- orsay.db en lecture seule : opération en attente, ISIN inconnu (info)
[D] report : export Excel, texte récap, journal d'audit JSON
        |
[H] lit, traite les suspens, envoie le point de situation lui-même

BESOIN 2 - QUESTIONS DES GÉRANTS
[H] question en français
        |
[LLM] choisit un outil + paramètres (boucle bornée, sortie pydantic)
        |
[D] outil : requête SQL figée sur orsay.db (lecture seule) -> tableau + source
        |
[LLM] phrase de synthèse (pydantic)
        |
[D] garde-fou : nombres de la phrase présents dans le tableau ? sinon tableau seul + avertissement
        |
[H] lit réponse + tableau + source
```

| Fichier | Rôle | Test qui le vérifie |
|---|---|---|
| `config.toml` | Date d'arrêté, chemins, version des règles, modèle, max tours | utilisé par tous les tests |
| `reco/loaders.py` | Lecture et contrôle des 5 fichiers, lignes écartées/rejetées | `tests/test_loaders.py` |
| `reco/reconcile.py` | Agrégation, comparaison, typage des suspens, enrichissement info | `tests/test_reconcile.py` (les 7 suspens attendus + pièges) |
| `reco/report.py` | Excel, texte récap, journal d'audit | `tests/test_report.py` |
| `assistant/tools.py` | Outils SQL lecture seule (encours, échéances, concentration, non dénoués, mouvements d'un titre) | `tests/test_tools.py` |
| `assistant/agent.py` | Appel LLM, boucle bornée, schémas pydantic, garde-fou nombres | `tests/test_agent.py` (garde-fou et routage avec LLM simulé) |
| `app.py` | Interface Streamlit 2 onglets | vérif manuelle (lancement + démo) |

## Limites et suite
- Étape 2 (loaders) : contrôles de date et de compteurs testés sur B ; pas de test de fichier A/C corrompu (structure Excel/XML cassée = exception non gérée).
- Étape 3 (reconcile) : les 7 suspens attendus sont trouvés par test. Appariement DEP au premier venu si plusieurs conservateurs candidats (cas absent des données). Conservateur bloqué : ses titres ne sont pas rapprochés et ne créent pas de faux ABS_INT ailleurs.
- Étape 4 (report + onglet Rapprochement) : export Excel/audit/récap testés ; interface vérifiée en navigateur (7 suspens affichés, 0 erreur). Pas de test automatisé de l'interface. Le dépôt de fichiers personnalisés n'a pas été testé dans le navigateur.
- Étape 5 (outils) : 3 outils sur 5 (concentration émetteur et origine d'un suspens en suite). Montants en float SQL arrondis à 2 décimales (acceptable pour de l'information, pas pour de la comptabilité). Valorisation pied de coupon, sans intérêts courus.
- pandas retiré : listes + Decimal suffisent (décision d'implémentation).
- Passage en production : hébergement datacenter client / SecNumCloud, LLM local ; ordonnancement quotidien après réception des relevés ; double exécution (manuel + outil) pendant N jours, bascule quand 0 divergence.
