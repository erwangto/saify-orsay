import json

import openpyxl

from reco.config import ROOT, load_config
from reco.loaders import load_all
from reco.reconcile import enrich, reconcile
from reco.report import summary_text, write_audit, write_excel

CFG = load_config()
DATA = ROOT / CFG["dossier_donnees"]


def _run():
    param, results = load_all(DATA, CFG)
    suspens = reconcile(results, param)
    enrich(suspens, DATA / CFG["fichiers"]["base"])
    return suspens, results


def test_excel_trois_onglets(tmp_path):
    suspens, results = _run()
    wb = openpyxl.load_workbook(write_excel(tmp_path / "r.xlsx", suspens, results))
    assert wb.sheetnames == ["Suspens", "Hors rapprochement", "Contrôles fichiers"]
    assert wb["Suspens"].max_row == 1 + 7
    assert wb["Hors rapprochement"].max_row == 1 + 3  # SANOFI, P3G, annulation RTE


def test_audit_contient_valeurs_comparees(tmp_path):
    suspens, results = _run()
    inputs = [DATA / f for f in CFG["fichiers"].values()]
    record = json.loads(write_audit(tmp_path / "a.json", suspens, results, CFG, inputs).read_text(encoding="utf-8"))
    assert record["version_regles"] == CFG["version_regles"]
    assert len(record["fichiers"]) == 6
    schneider = next(s for s in record["suspens"] if s["ISIN"] == "FR0000012965")
    assert (schneider["Qté interne"], schneider["Qté conservateur"]) == ("250000", "225000")


def test_recap_texte():
    suspens, results = _run()
    text = summary_text(suspens, results, CFG)
    assert "7 suspens au total." in text and "- DEP : 1" in text and "- QTE : 3" in text


def test_format_quantites():
    from decimal import Decimal

    from reco.report import fmt

    assert fmt(Decimal("50000.00")) == "50000"
    assert fmt(Decimal("-0.50")) == "-0.5"
    assert fmt(None) == ""
