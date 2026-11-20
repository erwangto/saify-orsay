# Architecture

Légende des couleurs : **bleu = code déterministe**, **orange = LLM**, **vert = humain**, **gris = données**.

## Vue d'ensemble

```mermaid
flowchart LR
    subgraph IN[Données du client]
        CSV[positions_internes.csv<br/>PMS]
        A[depositaire_A.xlsx]
        B[depositaire_B.txt]
        C[depositaire_C.xml]
        P[parametrage.xlsx]
        DB[(orsay.db<br/>lecture seule)]
    end

    subgraph B1[Besoin 1 - Rapprochement - reco/]
        L[loaders.py<br/>lecture + contrôles]
        R[reconcile.py<br/>comparaison + typage]
        REP[report.py<br/>Excel, récap, audit]
    end

    subgraph B2[Besoin 2 - Questions - assistant/]
        AG[agent.py<br/>choix d'outil + phrase]
        T[tools.py<br/>3 requêtes SQL figées]
        G[agent.py<br/>garde-fou nombres]
    end

    UI[app.py<br/>Streamlit, 2 onglets]
    OP([Opérateur middle office])
    GE([Gérant / RCCI])

    CSV & A & B & C & P --> L --> R --> REP --> UI --> OP
    DB -. info .-> R
    GE --> UI --> AG --> T --> G --> UI
    DB --> T

    classDef det fill:#dbeafe,stroke:#1e40af,color:#1e3a8a
    classDef llm fill:#ffedd5,stroke:#c2410c,color:#7c2d12
    classDef hum fill:#dcfce7,stroke:#15803d,color:#14532d
    classDef data fill:#f3f4f6,stroke:#6b7280,color:#111827
    class L,R,REP,T,G,UI det
    class AG llm
    class OP,GE hum
    class CSV,A,B,C,P,DB data
```

## Besoin 1 : le rapprochement, étape par étape

```mermaid
flowchart TD
    F[5 fichiers déposés] --> CTRL{Contrôles fichier<br/>date d'arrêté, trailer B, NbItems C}
    CTRL -- KO --> BLOQ[Fichier bloqué<br/>message clair]
    CTRL -- OK --> NORM[Normalisation<br/>ISIN nettoyé, quantité Decimal,<br/>compte -> Fonds, libellé -> Conservateur]
    NORM --> ECART[Lignes écartées<br/>P3G, sans sous-compte, annulation S]
    NORM --> REJ[Lignes rejetées<br/>compte ou libellé inconnu]
    NORM --> AGG[Agrégation<br/>somme sous-comptes et lots<br/>clé Fonds + ISIN + Conservateur]
    AGG --> CMP{Comparaison exacte}
    CMP -- égal --> OK[Rien à faire]
    CMP -- présent des 2 côtés, écart --> QTE[QTE]
    CMP -- interne seul --> PAIR{Même Fonds + ISIN<br/>chez un autre conservateur ?}
    CMP -- conservateur seul --> PAIR
    PAIR -- oui --> DEP[DEP, un seul suspens]
    PAIR -- non, interne seul --> ABSD[ABS_DEP]
    PAIR -- non, conservateur seul --> ABSI[ABS_INT]
    QTE & DEP & ABSD & ABSI --> INFO[Info depuis orsay.db<br/>opération en attente, ISIN inconnu]
    INFO --> OUT[Excel + récap + journal d'audit]
    OUT --> H([Opérateur : traite et envoie lui-même])

    classDef det fill:#dbeafe,stroke:#1e40af,color:#1e3a8a
    classDef hum fill:#dcfce7,stroke:#15803d,color:#14532d
    classDef bad fill:#fee2e2,stroke:#b91c1c,color:#7f1d1d
    class CTRL,NORM,AGG,CMP,PAIR,INFO,OUT,ECART,REJ det
    class H hum
    class BLOQ,QTE,DEP,ABSD,ABSI bad
```

## Besoin 2 : une question de gérant

```mermaid
sequenceDiagram
    actor G as Gérant
    participant UI as app.py
    participant LLM as Claude (agent.py)
    participant T as tools.py
    participant DB as orsay.db (lecture seule)
    participant GF as Garde-fou (agent.py)

    G->>UI: "Combien vaut Orsay Obligations ?"
    UI->>LLM: question + liste des 3 outils
    LLM-->>UI: outil = encours_valorise, fonds = OBL (validé pydantic)
    UI->>T: encours_valorise("OBL")
    T->>DB: SELECT figé (positions x cours)
    DB-->>T: lignes
    T-->>UI: tableau + total + source (requête, date du cours)
    UI->>LLM: tableau -> rédige une phrase
    LLM-->>UI: phrase (validée pydantic)
    UI->>GF: nombres de la phrase présents dans le tableau ?
    GF-->>UI: oui -> phrase + tableau / non -> tableau seul + avertissement
    UI-->>G: réponse, tableau, source
    Note over LLM,T: 2 appels fixes, aucun outil d'écriture,<br/>question hors outils -> "je ne sais pas"
```

## Rôle des fichiers

| Fichier | Type | Rôle |
|---|---|---|
| `config.toml` | paramètres | date d'arrêté, chemins, version des règles, modèle |
| `reco/loaders.py` | déterministe | lit les 5 fichiers, contrôles, lignes écartées et rejetées |
| `reco/reconcile.py` | déterministe | agrège, compare, classe QTE / ABS_DEP / ABS_INT / DEP |
| `reco/report.py` | déterministe | Excel, texte récapitulatif, journal d'audit JSON |
| `assistant/tools.py` | déterministe | 3 requêtes SQL figées en lecture seule, avec leur source |
| `assistant/agent.py` | LLM + garde-fou | choix d'outil, phrase de synthèse, contrôle des nombres |
| `app.py` | interface | Streamlit, onglets Rapprochement et Questions |
