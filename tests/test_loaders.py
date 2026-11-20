from decimal import Decimal
from pathlib import Path

import pytest

from reco.config import ROOT, load_config
from reco.loaders import (
    load_all,
    load_depositaire_b,
    load_parametrage,
    normalize_isin,
    parse_quantity,
)

CFG = load_config()
DATA = ROOT / CFG["dossier_donnees"]


@pytest.fixture(scope="module")
def loaded():
    param, results = load_all(DATA, CFG)
    return param, {r.fichier: r for r in results}


def test_normalisations():
    assert normalize_isin(" fr0000014078 ") == "FR0000014078"
    assert parse_quantity("225 000") == Decimal("225000")
    assert parse_quantity("10000,00") == Decimal("10000")
    assert parse_quantity("abc") is None


def test_tous_les_controles_passent(loaded):
    _, res = loaded
    for r in res.values():
        assert not r.bloque, [c for c in r.controles if not c.ok]
        assert r.rejetees == []


def test_interne_exclusions_et_conservateurs(loaded):
    _, res = loaded
    interne = res["interne"]
    motifs = {(l.isin, l.motif.split(" ")[0]) for l in interne.ecartees}
    assert motifs == {("FR0000011850", "Sans"), ("FR0000011116", "Sous-compte")}
    assert len(interne.positions) == 37 - 2
    oat_2039 = {p.conservateur for p in interne.positions if p.isin == "FR0000050411"}
    assert oat_2039 == {"C"}  # "Bnp Paribas SS" et "BP2S"


def test_depositaires(loaded):
    _, res = loaded
    assert len(res["A"].positions) == 9
    assert res["A"].positions[3].quantite == Decimal("225000")
    assert len(res["B"].positions) == 13
    lvmh = [p for p in res["B"].positions if p.isin == "FR0000999914"][0]
    assert (lvmh.fonds, lvmh.quantite) == ("ORSAY OBLIGATIONS", Decimal("30000"))
    assert len(res["C"].positions) == 8
    assert [l.motif for l in res["C"].ecartees] == ["Annulation (ACTION=S)"]


def test_trailer_faux_bloque_le_fichier(tmp_path: Path):
    content = (DATA / CFG["fichiers"]["depositaire_B"]).read_text().replace("T000013", "T000012")
    bad = tmp_path / "b.txt"
    bad.write_text(content)
    param = load_parametrage(DATA / CFG["fichiers"]["parametrage"])
    res = load_depositaire_b(bad, param, CFG)
    assert res.bloque and res.positions == []


def test_date_fausse_bloque_le_fichier(tmp_path: Path):
    content = (DATA / CFG["fichiers"]["depositaire_B"]).read_text().replace("H20260925", "H20260924")
    bad = tmp_path / "b.txt"
    bad.write_text(content)
    param = load_parametrage(DATA / CFG["fichiers"]["parametrage"])
    assert load_depositaire_b(bad, param, CFG).bloque
