"""Comparaison exacte interne / conservateurs et typage des suspens."""
import sqlite3
from collections import defaultdict
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path

from reco.loaders import LoadResult, Parametrage

Key = tuple[str, str, str]  # (fonds, isin, conservateur)
DEPOSITAIRES = ("A", "B", "C")


@dataclass
class Suspens:
    type: str
    libelle: str
    action: str
    fonds: str
    isin: str
    conservateur_interne: str | None
    conservateur_depositaire: str | None
    quantite_interne: Decimal | None
    quantite_depositaire: Decimal | None
    infos: list[str] = field(default_factory=list)

    @property
    def ecart(self) -> Decimal:
        return (self.quantite_depositaire or Decimal(0)) - (self.quantite_interne or Decimal(0))


def aggregate(results: list[LoadResult]) -> dict[Key, Decimal]:
    # Somme des sous-comptes (interne) ou des lots (C) sur la clé de rapprochement
    totals: dict[Key, Decimal] = defaultdict(Decimal)
    for r in results:
        for p in r.positions:
            totals[(p.fonds, p.isin, p.conservateur)] += p.quantite
    return dict(totals)


def reconcile(results: list[LoadResult], param: Parametrage) -> list[Suspens]:
    by_file = {r.fichier: r for r in results}
    if by_file["interne"].bloque:
        return []
    bloques = {c for c in DEPOSITAIRES if by_file[c].bloque}
    interne_complet = aggregate([by_file["interne"]])
    interne = {k: q for k, q in interne_complet.items() if k[2] not in bloques}
    # Titres attendus chez un conservateur bloqué : impossible de conclure à un ABS_INT ailleurs
    attendus_chez_bloque = {(k[0], k[1]) for k in interne_complet if k[2] in bloques}
    depot = aggregate([by_file[c] for c in DEPOSITAIRES if c not in bloques])

    def make(code: str, fonds: str, isin: str, ci, cd, qi, qd) -> Suspens:
        lib, action = param.types[code]
        return Suspens(code, lib, action, fonds, isin, ci, cd, qi, qd)

    suspens: list[Suspens] = []
    only_int: dict[tuple[str, str], list[Key]] = defaultdict(list)
    only_dep: dict[tuple[str, str], list[Key]] = defaultdict(list)
    for key in sorted(set(interne) | set(depot)):
        fonds, isin, cons = key
        qi, qd = interne.get(key), depot.get(key)
        if qi is not None and qd is not None:
            if qi != qd:  # aucune tolérance
                suspens.append(make("QTE", fonds, isin, cons, cons, qi, qd))
        elif qi is not None:
            only_int[(fonds, isin)].append(key)
        else:
            only_dep[(fonds, isin)].append(key)

    for fi in sorted(set(only_int) | set(only_dep)):
        ints, deps = only_int.get(fi, []), only_dep.get(fi, [])
        # Attendu chez un conservateur, trouvé chez un autre : un seul suspens DEP
        while ints and deps:
            ki, kd = ints.pop(0), deps.pop(0)
            s = make("DEP", fi[0], fi[1], ki[2], kd[2], interne[ki], depot[kd])
            if interne[ki] != depot[kd]:
                s.infos.append("Quantité également différente")
            suspens.append(s)
        for k in ints:
            suspens.append(make("ABS_DEP", k[0], k[1], k[2], None, interne[k], None))
        for k in deps if fi not in attendus_chez_bloque else []:
            suspens.append(make("ABS_INT", k[0], k[1], None, k[2], None, depot[k]))
    return suspens


def enrich(suspens: list[Suspens], db_path: Path) -> None:
    """Ajoute des informations tirées de la base de gestion (lecture seule, sans effet sur le type)."""
    con = sqlite3.connect(f"file:{db_path.as_posix()}?mode=ro", uri=True)
    try:
        codes = dict(con.execute("SELECT nom, code FROM portefeuilles"))
        known = {row[0] for row in con.execute("SELECT isin FROM titres")}
        for s in suspens:
            if s.isin not in known:
                s.infos.append("ISIN absent du référentiel valeurs : saisie probablement erronée")
            rows = con.execute(
                "SELECT id, sens, quantite, date_operation, date_denouement FROM mouvements "
                "WHERE portefeuille = ? AND isin = ? AND statut <> 'DENOUE'",
                (codes.get(s.fonds), s.isin),
            ).fetchall()
            for mid, sens, qty, d_op, d_den in rows:
                s.infos.append(
                    f"Opération non dénouée : mouvement {mid}, {sens} {qty} négocié le {d_op}, dénouement prévu le {d_den}"
                )
    finally:
        con.close()
