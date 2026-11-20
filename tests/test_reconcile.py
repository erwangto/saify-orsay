from dataclasses import replace
from decimal import Decimal

import pytest

from reco.config import ROOT, load_config
from reco.loaders import load_all
from reco.reconcile import enrich, reconcile

CFG = load_config()
DATA = ROOT / CFG["dossier_donnees"]

EXPECTED = {
    ("QTE", "ORSAY ACTIONS EUROPE", "FR0000012965"),  # SCHNEIDER
    ("QTE", "ORSAY ACTIONS EUROPE", "FR0000016297"),  # SAFRAN
    ("QTE", "ORSAY OBLIGATIONS", "FR0000051641"),  # SFIL
    ("ABS_DEP", "ORSAY OBLIGATIONS", "FR0000011488"),  # EDF
    ("ABS_DEP", "ORSAY OBLIGATIONS", "FR0000012966"),  # ISIN saisi à la main
    ("DEP", "ORSAY OBLIGATIONS", "FR0000015927"),  # AFD
    ("ABS_INT", "ORSAY OBLIGATIONS", "FR0000999914"),  # LVMH
}


@pytest.fixture(scope="module")
def run():
    param, results = load_all(DATA, CFG)
    suspens = reconcile(results, param)
    enrich(suspens, DATA / CFG["fichiers"]["base"])
    return param, results, {s.isin: s for s in suspens}, suspens


def test_exactement_les_7_suspens_attendus(run):
    _, _, _, suspens = run
    assert {(s.type, s.fonds, s.isin) for s in suspens} == EXPECTED
    assert len(suspens) == 7


def test_pieges_tombent_juste(run):
    _, _, by_isin, _ = run
    for isin in ["FR0000016669", "FR0000010746", "FR0000052052", "FR0000050411", "FR0000051237", "FR0000011850"]:
        assert isin not in by_isin  # KERING, TOTAL, HERMES, OAT 2039, RTE, SANOFI


def test_details_et_infos(run):
    _, _, by_isin, _ = run
    schneider = by_isin["FR0000012965"]
    assert (schneider.quantite_interne, schneider.quantite_depositaire) == (Decimal(250000), Decimal(225000))
    assert schneider.action == "Vérifier les opérations de la veille non dénouées"
    assert any("mouvement 19" in i for i in schneider.infos)
    afd = by_isin["FR0000015927"]
    assert (afd.conservateur_interne, afd.conservateur_depositaire) == ("A", "B")
    assert afd.infos == []
    assert any("absent du référentiel" in i for i in by_isin["FR0000012966"].infos)
    assert by_isin["FR0000051641"].infos == []  # SFIL : écart inexpliqué


def test_une_unite_d_ecart_est_un_suspens(run):
    param, results, _, _ = run
    interne = results[0]
    pos = interne.positions
    i = next(k for k, p in enumerate(pos) if p.isin == "FR0000014441")  # LEGRAND, à l'équilibre
    interne.positions = pos[:i] + [replace(pos[i], quantite=pos[i].quantite + 1)] + pos[i + 1:]
    try:
        types = {s.isin: s.type for s in reconcile(results, param)}
        assert types["FR0000014441"] == "QTE"
    finally:
        interne.positions = pos


def test_conservateur_bloque_ne_cree_pas_de_faux_suspens(run):
    param, results, _, _ = run
    a = results[1]
    saved = a.controles
    a.controles = saved + [type(saved[0])("A", "test", "x", "y")]
    try:
        suspens = reconcile(results, param)
        assert all("A" not in (s.conservateur_interne, s.conservateur_depositaire) for s in suspens)
        assert "FR0000015927" not in {s.isin for s in suspens}  # AFD : pas de faux ABS_INT chez B
    finally:
        a.controles = saved
