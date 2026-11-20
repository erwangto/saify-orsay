"""Assistant gérants : le LLM choisit un outil puis rédige une phrase ; le code calcule et contrôle.

Workflow en 2 appels fixes (pas de boucle libre) :
1. routage : question -> ChoixOutil (validé pydantic) ;
2. exécution déterministe de l'outil (SQL en lecture seule) ;
3. synthèse : résultat -> Synthese (validé pydantic) ;
4. garde-fou : chaque nombre de la phrase doit figurer dans le résultat, sinon la phrase est écartée.
"""
import json
import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Literal, Protocol

from pydantic import BaseModel

from assistant import tools


class ChoixOutil(BaseModel):
    outil: Literal["encours_valorise", "echeances", "operations_non_denouees", "aucun"]
    fonds: Literal["PAT", "OBL", "ACT"] | None = None
    horizon_jours: int | None = None


class Synthese(BaseModel):
    phrase: str


class LLM(Protocol):
    def route(self, question: str) -> ChoixOutil: ...
    def synthesize(self, question: str, resultat: dict[str, Any]) -> Synthese: ...


@dataclass
class Reponse:
    phrase: str | None
    resultat: dict[str, Any] | None
    avertissement: str | None = None


PROMPT_ROUTAGE = """Tu aides les gérants d'Orsay Gestion. Choisis l'outil qui répond à la question.
- encours_valorise : valeur d'un fonds au cours de clôture (fonds obligatoire : PAT = Orsay Patrimoine, OBL = Orsay Obligations, ACT = Orsay Actions Europe).
- echeances : titres arrivant à échéance dans les N prochains jours (horizon_jours obligatoire, 90 par défaut).
- operations_non_denouees : opérations négociées pas encore réglées-livrées.
- aucun : si aucun outil ne répond exactement à la question. Ne devine jamais."""

PROMPT_SYNTHESE = """Rédige une seule phrase en français qui répond à la question à partir du résultat JSON fourni.
Règles : n'utilise que des nombres présents dans le résultat, recopiés à l'identique (chiffres sans séparateur de milliers, point décimal).
Ne fais aucun calcul. Si le résultat est vide, dis-le."""


class ClaudeLLM:
    def __init__(self, model: str) -> None:
        import anthropic  # import local : les tests n'en ont pas besoin

        self.client = anthropic.Anthropic()  # lit ANTHROPIC_API_KEY dans l'environnement
        self.model = model
        self.modeles_servis: list[str] = []  # trace des modèles ayant réellement répondu

    def _parse(self, system: str, content: str, schema: type[BaseModel]) -> Any:
        # Repli côté serveur : si le modèle refuse, l'API relance la même requête sur le modèle
        # recommandé par Anthropic pour cette catégorie de refus, dans le même appel
        response = self.client.beta.messages.parse(
            model=self.model,
            max_tokens=2000,
            output_config={"effort": "low"},
            system=system,
            messages=[{"role": "user", "content": content}],
            output_format=schema,
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
        )
        self.modeles_servis.append(response.model)
        # Un refus en fin de chaîne signifie que le repli a lui aussi refusé
        if response.stop_reason == "refusal" or response.parsed_output is None:
            raise RuntimeError(f"Réponse LLM inexploitable ({response.stop_reason})")
        return response.parsed_output

    def route(self, question: str) -> ChoixOutil:
        return self._parse(PROMPT_ROUTAGE, question, ChoixOutil)

    def synthesize(self, question: str, resultat: dict[str, Any]) -> Synthese:
        data = {k: resultat[k] for k in ("lignes", "total") if k in resultat}
        content = f"Question : {question}\nRésultat : {json.dumps(data, ensure_ascii=False)}"
        return self._parse(PROMPT_SYNTHESE, content, Synthese)


NUMBER = re.compile(r"\d+(?:[.,]\d+)?")


def numbers_in(text: str) -> set[Decimal]:
    out = set()
    # Espaces entre chiffres = séparateurs de milliers ("724 836" -> 724836)
    for raw in NUMBER.findall(re.sub(r"(?<=\d)[\s  ](?=\d{3}\b)", "", text)):
        try:
            out.add(Decimal(raw.replace(",", ".")))
        except InvalidOperation:
            pass
    return out


def numbers_allowed(resultat: dict[str, Any]) -> set[Decimal]:
    # Tous les nombres présents dans le résultat de l'outil (valeurs, dates, paramètres)
    return numbers_in(json.dumps({k: resultat[k] for k in ("lignes", "total", "parametres") if k in resultat}))


def check_numbers(phrase: str, resultat: dict[str, Any]) -> set[Decimal]:
    """Renvoie les nombres de la phrase absents du résultat (vide = phrase acceptée)."""
    return numbers_in(phrase) - numbers_allowed(resultat)


def answer(question: str, llm: LLM, db_path: Path, date_arrete: str) -> Reponse:
    choix = llm.route(question)
    if choix.outil == "aucun":
        return Reponse(None, None, "Je ne sais pas répondre à cette question avec les outils disponibles.")
    if choix.outil == "encours_valorise":
        if choix.fonds is None:
            return Reponse(None, None, "Précisez le fonds (Patrimoine, Obligations ou Actions Europe).")
        resultat = tools.encours_valorise(db_path, date_arrete, choix.fonds)
    elif choix.outil == "echeances":
        resultat = tools.echeances(db_path, date_arrete, choix.horizon_jours or 90)
    else:
        resultat = tools.operations_non_denouees(db_path)

    phrase = llm.synthesize(question, resultat).phrase
    inconnus = check_numbers(phrase, resultat)
    if inconnus:
        return Reponse(None, resultat, f"Phrase du LLM écartée : nombres absents des données ({', '.join(map(str, sorted(inconnus)))}). Seul le tableau fait foi.")
    return Reponse(phrase, resultat)
