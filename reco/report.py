"""Sorties du rapprochement : tableaux, export Excel, texte récapitulatif, journal d'audit."""
import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

import openpyxl

from reco.loaders import LoadResult
from reco.reconcile import Suspens


def fmt(q: Decimal | None) -> str:
    # Affichage sans zéros décimaux superflus ("50000.00" -> "50000")
    return "" if q is None else format(q.normalize(), "f")


def suspens_rows(suspens: list[Suspens]) -> list[dict]:
    return [
        {
            "Type": s.type,
            "Fonds": s.fonds,
            "ISIN": s.isin,
            "Conservateur PMS": s.conservateur_interne or "",
            "Conservateur relevé": s.conservateur_depositaire or "",
            "Qté interne": fmt(s.quantite_interne),
            "Qté conservateur": fmt(s.quantite_depositaire),
            "Écart": fmt(s.ecart),
            "Action attendue": s.action,
            "Informations": " | ".join(s.infos),
        }
        for s in suspens
    ]


def hors_rapprochement_rows(results: list[LoadResult]) -> list[dict]:
    rows = []
    for r in results:
        for statut, lignes in (("Écartée", r.ecartees), ("Rejetée", r.rejetees)):
            rows += [{"Statut": statut, "Source": l.source, "ISIN": l.isin, "Quantité": l.quantite, "Motif": l.motif} for l in lignes]
    return rows


def controle_rows(results: list[LoadResult]) -> list[dict]:
    return [
        {"Fichier": c.fichier, "Contrôle": c.controle, "Attendu": c.attendu, "Obtenu": c.obtenu, "Résultat": "OK" if c.ok else "BLOQUANT"}
        for r in results
        for c in r.controles
    ]


def write_excel(path: Path, suspens: list[Suspens], results: list[LoadResult]) -> Path:
    wb = openpyxl.Workbook()
    wb.remove(wb.active)
    for title, rows in (
        ("Suspens", suspens_rows(suspens)),
        ("Hors rapprochement", hors_rapprochement_rows(results)),
        ("Contrôles fichiers", controle_rows(results)),
    ):
        ws = wb.create_sheet(title)
        if rows:
            ws.append(list(rows[0]))
            for row in rows:
                ws.append(list(row.values()))
    path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(path)
    return path


def summary_text(suspens: list[Suspens], results: list[LoadResult], cfg: dict) -> str:
    bloques = [r.fichier for r in results if r.bloque]
    lines = [
        f"Point de situation du rapprochement des positions, arrêté du {cfg['date_arrete']}",
        "",
        f"{len(suspens)} suspens au total.",
    ]
    for code, n in sorted(Counter(s.type for s in suspens).items()):
        lines.append(f"- {code} : {n}")
    if bloques:
        lines.append(f"Fichiers bloqués (non rapprochés) : {', '.join(bloques)}.")
    lines.append("")
    for fonds in sorted({s.fonds for s in suspens}):
        lines.append(f"{fonds} :")
        for s in (x for x in suspens if x.fonds == fonds):
            cons = s.conservateur_depositaire or s.conservateur_interne
            lines.append(f"- {s.type} {s.isin} chez {cons} : interne {fmt(s.quantite_interne) or 'absent'}, conservateur {fmt(s.quantite_depositaire) or 'absent'}. Action : {s.action}.")
    return "\n".join(lines)


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_audit(path: Path, suspens: list[Suspens], results: list[LoadResult], cfg: dict, inputs: list[Path]) -> Path:
    record = {
        "horodatage": datetime.now(timezone.utc).isoformat(),
        "version_regles": cfg["version_regles"],
        "date_arrete": cfg["date_arrete"],
        "fichiers": {p.name: file_hash(p) for p in inputs},
        "controles": controle_rows(results),
        "hors_rapprochement": hors_rapprochement_rows(results),
        "suspens": suspens_rows(suspens),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    return path
