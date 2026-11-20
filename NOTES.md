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

**Hypothèses / questions ouvertes**
- (à compléter après la ronde 1)

## Décisions
| Étape | Choix | Raison | Alternative écartée |
|---|---|---|---|

## Architecture
(à compléter)

| Fichier | Rôle | Test qui le vérifie |
|---|---|---|

## Limites et suite
(à compléter)
