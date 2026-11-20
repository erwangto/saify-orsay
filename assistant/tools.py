"""Outils de l'assistant : requêtes SQL figées sur orsay.db, en lecture seule.

Ce sont les seules fonctions qui produisent des chiffres. Chacune renvoie ses lignes
et sa source (requête et paramètres) pour que le gérant sache d'où vient chaque nombre.
"""
import sqlite3
from datetime import date, timedelta
from pathlib import Path
from typing import Any

FONDS = ("PAT", "OBL", "ACT")


def connect_ro(db_path: Path) -> sqlite3.Connection:
    # mode=ro : toute écriture lève une erreur, même en cas de bug
    return sqlite3.connect(f"file:{db_path.as_posix()}?mode=ro", uri=True)


def _run(db_path: Path, outil: str, sql: str, params: dict[str, Any]) -> dict[str, Any]:
    con = connect_ro(db_path)
    try:
        cur = con.execute(sql, params)
        cols = [d[0] for d in cur.description]
        rows = [dict(zip(cols, r)) for r in cur.fetchall()]
    finally:
        con.close()
    return {"outil": outil, "parametres": params, "requete": " ".join(sql.split()), "lignes": rows}


def encours_valorise(db_path: Path, date_arrete: str, fonds: str) -> dict[str, Any]:
    """Encours d'un fonds au cours de clôture. Obligations/BTF : nominal x cours / 100."""
    if fonds not in FONDS:
        raise ValueError(f"Fonds inconnu : {fonds}")
    sql = """
        SELECT p.isin, t.libelle, t.type_titre, p.quantite, c.cours, c.date_cours,
               ROUND(CASE WHEN t.mode_cotation = 'POURCENTAGE' THEN p.quantite * c.cours / 100
                          ELSE p.quantite * c.cours END, 2) AS valeur
        FROM positions p
        JOIN titres t ON t.isin = p.isin
        JOIN cours c ON c.isin = p.isin AND c.date_cours = :date
        WHERE p.portefeuille = :fonds AND p.date_arrete = :date
        ORDER BY valeur DESC
    """
    res = _run(db_path, "encours_valorise", sql, {"fonds": fonds, "date": date_arrete})
    res["total"] = round(sum(r["valeur"] for r in res["lignes"]), 2)
    return res


def echeances(db_path: Path, date_arrete: str, horizon_jours: int) -> dict[str, Any]:
    """Titres détenus arrivant à échéance dans l'horizon donné."""
    fin = (date.fromisoformat(date_arrete) + timedelta(days=horizon_jours)).isoformat()
    sql = """
        SELECT p.portefeuille, p.isin, t.libelle, t.date_echeance, p.quantite AS nominal
        FROM positions p
        JOIN titres t ON t.isin = p.isin
        WHERE p.date_arrete = :date AND t.date_echeance > :date AND t.date_echeance <= :fin
        ORDER BY t.date_echeance
    """
    return _run(db_path, "echeances", sql, {"date": date_arrete, "fin": fin})


def operations_non_denouees(db_path: Path) -> dict[str, Any]:
    """Opérations négociées mais pas encore réglées-livrées."""
    sql = """
        SELECT m.id, m.portefeuille, m.isin, t.libelle, m.sens, m.quantite, m.prix,
               m.date_operation, m.date_denouement, m.statut
        FROM mouvements m
        LEFT JOIN titres t ON t.isin = m.isin
        WHERE m.statut <> 'DENOUE'
        ORDER BY m.date_denouement
    """
    return _run(db_path, "operations_non_denouees", sql, {})
