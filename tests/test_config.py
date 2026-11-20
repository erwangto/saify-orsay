from reco.config import load_config


def test_config_loads():
    cfg = load_config()
    assert cfg["date_arrete"] == "2026-09-25"
    assert cfg["regles"]["libelles_conservateur"]["BP2S"] == "C"
