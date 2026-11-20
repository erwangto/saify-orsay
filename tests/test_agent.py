from typing import Any

from assistant.agent import ChoixOutil, Synthese, answer, check_numbers, numbers_in
from reco.config import ROOT, load_config

CFG = load_config()
DB = ROOT / CFG["dossier_donnees"] / CFG["fichiers"]["base"]
DATE = CFG["date_arrete"]


class FakeLLM:
    """LLM simulé : réponses écrites à l'avance, pas de réseau."""

    def __init__(self, choix: ChoixOutil, phrase: str = "") -> None:
        self.choix, self.phrase = choix, phrase

    def route(self, question: str) -> ChoixOutil:
        return self.choix

    def synthesize(self, question: str, resultat: dict[str, Any]) -> Synthese:
        return Synthese(phrase=self.phrase.format(**resultat) if "{" in self.phrase else self.phrase)


def test_lecture_des_nombres():
    assert {int(n) for n in numbers_in("724 836 euros au 25/09")} == {724836, 25, 9}


def test_phrase_fidele_acceptee():
    llm = FakeLLM(ChoixOutil(outil="encours_valorise", fonds="OBL"), "Orsay Obligations vaut {total} euros.")
    rep = answer("Combien vaut Orsay Obligations ?", llm, DB, DATE)
    assert rep.avertissement is None and rep.phrase and rep.resultat["total"] > 0


def test_nombre_invente_rejete():
    llm = FakeLLM(ChoixOutil(outil="encours_valorise", fonds="OBL"), "Orsay Obligations vaut 999999 euros.")
    rep = answer("Combien vaut Orsay Obligations ?", llm, DB, DATE)
    assert rep.phrase is None and "999999" in rep.avertissement
    assert rep.resultat is not None  # le tableau reste affiché


def test_question_hors_perimetre():
    rep = answer("Quelle est la météo ?", FakeLLM(ChoixOutil(outil="aucun")), DB, DATE)
    assert rep.resultat is None and "Je ne sais pas" in rep.avertissement


def test_fonds_manquant():
    rep = answer("Combien vaut le fonds ?", FakeLLM(ChoixOutil(outil="encours_valorise")), DB, DATE)
    assert rep.resultat is None and "Précisez" in rep.avertissement


def test_echeances_avec_date_acceptee():
    llm = FakeLLM(ChoixOutil(outil="echeances", horizon_jours=90), "Le BTF 3M arrive à échéance le 2026-12-17.")
    rep = answer("Quelles échéances sous 90 jours ?", llm, DB, DATE)
    assert rep.avertissement is None
    assert check_numbers("le 2026-12-18", rep.resultat) == {18}
