"""Lecture des 5 fichiers du matin vers un format commun.

Chaque lecteur renvoie un LoadResult : positions normalisées, lignes écartées
(exclues par une règle métier), lignes rejetées (inconnues) et contrôles du fichier.
Si un contrôle échoue, le fichier est bloqué : ses positions ne sont pas rapprochées.
"""
import csv
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from pathlib import Path

import openpyxl


@dataclass(frozen=True)
class Position:
    fonds: str
    isin: str
    conservateur: str
    quantite: Decimal
    source: str


@dataclass(frozen=True)
class LigneHorsRapprochement:
    source: str
    isin: str
    quantite: str
    motif: str


@dataclass(frozen=True)
class Controle:
    fichier: str
    controle: str
    attendu: str
    obtenu: str

    @property
    def ok(self) -> bool:
        return self.attendu == self.obtenu


@dataclass
class LoadResult:
    fichier: str
    positions: list[Position] = field(default_factory=list)
    ecartees: list[LigneHorsRapprochement] = field(default_factory=list)
    rejetees: list[LigneHorsRapprochement] = field(default_factory=list)
    controles: list[Controle] = field(default_factory=list)

    @property
    def bloque(self) -> bool:
        return any(not c.ok for c in self.controles)

    def finalize(self) -> "LoadResult":
        # Un fichier bloqué ne fournit aucune position, pour ne pas fabriquer de faux suspens
        if self.bloque:
            self.positions = []
        return self


@dataclass
class Parametrage:
    sous_comptes: dict[str, str]
    comptes: dict[str, dict[str, str]]  # conservateur -> compte -> fonds
    types: dict[str, tuple[str, str]]  # code -> (libellé, action attendue)


def normalize_isin(raw: str) -> str:
    return re.sub(r"\s", "", raw or "").upper()


def parse_quantity(raw: str) -> Decimal | None:
    # Espaces (y compris insécables) = séparateurs de milliers ; virgule = décimale
    cleaned = re.sub(r"\s", "", str(raw)).replace(",", ".")
    try:
        return Decimal(cleaned)
    except InvalidOperation:
        return None


def load_parametrage(path: Path) -> Parametrage:
    wb = openpyxl.load_workbook(path, read_only=True)

    def table(sheet: str) -> list[tuple]:
        rows = list(wb[sheet].iter_rows(values_only=True))
        return [r for r in rows[1:] if r[0] is not None]

    comptes = {
        cons: {str(k).strip(): v for k, v, *_ in table(f"TRANSCO_DEPOSITAIRE_{cons}")}
        for cons in ("A", "B", "C")
    }
    return Parametrage(
        sous_comptes={str(k).strip(): v for k, v, *_ in table("TRANSCO_SOUS_COMPTES")},
        comptes=comptes,
        types={code: (lib, action) for code, lib, action, *_ in table("TYPES_ECARTS")},
    )


def conservateur_from_label(label: str, keywords: dict[str, str]) -> str | None:
    upper = (label or "").upper()
    found = {cons for kw, cons in keywords.items() if kw in upper}
    return found.pop() if len(found) == 1 else None


def load_interne(path: Path, param: Parametrage, cfg: dict) -> LoadResult:
    res = LoadResult("interne")
    expected = cfg["date_arrete"]
    exclus = set(cfg["regles"]["sous_comptes_exclus"])
    keywords = cfg["regles"]["libelles_conservateur"]
    dates: set[str] = set()
    with open(path, encoding="utf-8-sig", newline="") as f:
        for n, row in enumerate(csv.DictReader(f, delimiter=";"), start=2):
            src = f"interne:ligne {n}"
            isin = normalize_isin(row["isin"])
            sc = (row["sous_compte"] or "").strip()
            dates.add(row["date_arrete"].strip())
            if not sc:
                res.ecartees.append(LigneHorsRapprochement(src, isin, row["quantite"], "Sans sous-compte : saisie incomplète"))
                continue
            if sc in exclus:
                res.ecartees.append(LigneHorsRapprochement(src, isin, row["quantite"], f"Sous-compte {sc} : compte technique"))
                continue
            fonds = param.sous_comptes.get(sc)
            cons = conservateur_from_label(row["depositaire"], keywords)
            qty = parse_quantity(row["quantite"])
            if fonds is None or cons is None or qty is None:
                motif = ("Sous-compte inconnu" if fonds is None
                         else "Libellé conservateur non reconnu" if cons is None
                         else "Quantité illisible")
                res.rejetees.append(LigneHorsRapprochement(src, isin, row["quantite"], motif))
                continue
            res.positions.append(Position(fonds, isin, cons, qty, src))
    res.controles.append(Controle("interne", "Date d'arrêté", expected, ",".join(sorted(dates))))
    return res.finalize()


def load_depositaire_a(path: Path, param: Parametrage, cfg: dict) -> LoadResult:
    res = LoadResult("A")
    rows = list(openpyxl.load_workbook(path, read_only=True).active.iter_rows(values_only=True))
    title = str(rows[0][0] or "")
    m = re.search(r"(\d{2})/(\d{2})/(\d{4})", title)
    found = f"{m.group(3)}-{m.group(2)}-{m.group(1)}" if m else "absente"
    res.controles.append(Controle("A", "Date d'arrêté", cfg["date_arrete"], found))
    header = next(i for i, r in enumerate(rows) if r and r[0] == "Compte")
    for n, r in enumerate(rows[header + 1:], start=header + 2):
        if not r or r[0] is None:
            continue
        src = f"A:ligne {n}"
        compte, isin, _, raw_qty = (str(r[0]).strip(), normalize_isin(str(r[1])), r[2], r[3])
        fonds = param.comptes["A"].get(compte)
        qty = parse_quantity(raw_qty)
        if fonds is None or qty is None:
            motif = "Compte inconnu" if fonds is None else "Quantité illisible"
            res.rejetees.append(LigneHorsRapprochement(src, isin, str(raw_qty), motif))
            continue
        res.positions.append(Position(fonds, isin, "A", qty, src))
    return res.finalize()


def load_depositaire_b(path: Path, param: Parametrage, cfg: dict) -> LoadResult:
    res = LoadResult("B")
    lines = Path(path).read_text(encoding="utf-8").splitlines()
    header = next((l for l in lines if l.startswith("H")), "")
    found = header[1:9]
    found = f"{found[:4]}-{found[4:6]}-{found[6:8]}" if len(found) == 8 else "absente"
    res.controles.append(Controle("B", "Date d'arrêté", cfg["date_arrete"], found))
    nb_detail = 0
    trailer = "absent"
    for n, line in enumerate(lines, start=1):
        if line.startswith("D"):
            nb_detail += 1
            src = f"B:ligne {n}"
            desk, isin = line[1:4], normalize_isin(line[4:16])
            digits = line[16:31]
            fonds = param.comptes["B"].get(desk)
            # 15 chiffres dont 2 décimales implicites
            qty = Decimal(digits) / 100 if digits.isdigit() and len(digits) == 15 else None
            if fonds is None or qty is None:
                motif = "Code desk inconnu" if fonds is None else "Quantité illisible"
                res.rejetees.append(LigneHorsRapprochement(src, isin, digits, motif))
                continue
            res.positions.append(Position(fonds, isin, "B", qty, src))
        elif line.startswith("T"):
            trailer = str(int(line[1:7])) if line[1:7].isdigit() else "illisible"
    res.controles.append(Controle("B", "Nombre de lignes (trailer)", trailer, str(nb_detail)))
    return res.finalize()


NS_C = {"c": "urn:orsay:depositaire-c:positions:2026"}


def load_depositaire_c(path: Path, param: Parametrage, cfg: dict) -> LoadResult:
    res = LoadResult("C")
    root = ET.parse(path).getroot()
    raw_date = root.findtext("c:Entete/c:DateArrete", default="", namespaces=NS_C)
    found = f"{raw_date[4:8]}-{raw_date[2:4]}-{raw_date[0:2]}" if len(raw_date) == 8 else "absente"
    res.controles.append(Controle("C", "Date d'arrêté", cfg["date_arrete"], found))
    items = root.findall("c:Positions/c:Item", NS_C)
    nb = root.findtext("c:Entete/c:NbItems", default="absent", namespaces=NS_C)
    res.controles.append(Controle("C", "Nombre d'items (NbItems)", nb.strip(), str(len(items))))
    for n, item in enumerate(items, start=1):
        d = {dim.get("prop"): (dim.text or "").strip() for dim in item.findall("c:Dim", NS_C)}
        src = f"C:item {n} (lot {d.get('LOT', '?')})"
        isin = normalize_isin(d.get("CODE_ISIN", ""))
        action = d.get("ACTION")
        if action == "S":
            res.ecartees.append(LigneHorsRapprochement(src, isin, d.get("QUANTITE", ""), "Annulation (ACTION=S)"))
            continue
        fonds = param.comptes["C"].get(d.get("COMPTE", ""))
        qty = parse_quantity(d.get("QUANTITE", ""))
        if action != "C" or fonds is None or qty is None:
            motif = ("Action inconnue" if action != "C"
                     else "Compte inconnu" if fonds is None else "Quantité illisible")
            res.rejetees.append(LigneHorsRapprochement(src, isin, d.get("QUANTITE", ""), motif))
            continue
        res.positions.append(Position(fonds, isin, "C", qty, src))
    return res.finalize()


def load_all(folder: Path, cfg: dict) -> tuple[Parametrage, list[LoadResult]]:
    files = cfg["fichiers"]
    param = load_parametrage(folder / files["parametrage"])
    results = [
        load_interne(folder / files["interne"], param, cfg),
        load_depositaire_a(folder / files["depositaire_A"], param, cfg),
        load_depositaire_b(folder / files["depositaire_B"], param, cfg),
        load_depositaire_c(folder / files["depositaire_C"], param, cfg),
    ]
    return param, results
