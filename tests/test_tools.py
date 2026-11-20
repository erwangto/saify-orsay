import sqlite3

import pytest

from assistant.tools import connect_ro, echeances, encours_valorise, operations_non_denouees
from reco.config import ROOT, load_config

CFG = load_config()
DB = ROOT / CFG["dossier_donnees"] / CFG["fichiers"]["base"]
DATE = CFG["date_arrete"]


def test_encours_valorise_recalcule_a_la_main():
    res = encours_valorise(DB, DATE, "OBL")
    con = connect_ro(DB)
    expected = 0.0
    for qty, cours, mode in con.execute(
        "SELECT p.quantite, c.cours, t.mode_cotation FROM positions p JOIN titres t USING(isin) "
        "JOIN cours c ON c.isin = p.isin AND c.date_cours = ? WHERE p.portefeuille = 'OBL'", (DATE,)
    ):
        assert mode == "POURCENTAGE"
        expected += qty * cours / 100
    con.close()
    assert res["total"] == round(expected, 2)
    assert len(res["lignes"]) == 10
    assert "positions" in res["requete"]


def test_encours_action_a_l_unite():
    res = encours_valorise(DB, DATE, "ACT")
    schneider = next(r for r in res["lignes"] if r["isin"] == "FR0000012965")
    assert schneider["valeur"] == round(schneider["quantite"] * schneider["cours"], 2)


def test_fonds_inconnu_refuse():
    with pytest.raises(ValueError):
        encours_valorise(DB, DATE, "XXX")


def test_echeances_btf_sous_90_jours():
    res = echeances(DB, DATE, 90)
    assert [(r["isin"], r["date_echeance"]) for r in res["lignes"]] == [("FR0000011116", "2026-12-17")]


def test_operations_non_denouees():
    res = operations_non_denouees(DB)
    assert {r["id"] for r in res["lignes"]} == {19, 20}


def test_ecriture_impossible():
    con = connect_ro(DB)
    with pytest.raises(sqlite3.OperationalError):
        con.execute("DELETE FROM positions")
    con.close()
