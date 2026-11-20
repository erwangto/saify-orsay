"""Interface Streamlit : onglet Rapprochement (besoin 1) et onglet Questions (besoin 2)."""
import tempfile
from collections import Counter
from datetime import datetime
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

from assistant.agent import ClaudeLLM, answer
from reco.config import ROOT, load_config
from reco.loaders import load_all
from reco.reconcile import enrich, reconcile
from reco.report import controle_rows, hors_rapprochement_rows, summary_text, suspens_rows, write_audit, write_excel

CFG = load_config()
DATA = ROOT / CFG["dossier_donnees"]
OUT = ROOT / CFG["dossier_sorties"]
SLOTS = {
    "interne": "Inventaire PMS (CSV)",
    "depositaire_A": "Relevé conservateur A (XLSX)",
    "depositaire_B": "Relevé conservateur B (TXT)",
    "depositaire_C": "Relevé conservateur C (XML)",
    "parametrage": "Paramétrage (XLSX)",
}

st.set_page_config(page_title="Orsay - Middle office", layout="wide")
st.title(f"Orsay Gestion : middle office, arrêté du {CFG['date_arrete']}")
tab_reco, tab_questions = st.tabs(["Rapprochement", "Questions"])


def run_reconciliation(folder: Path, source: str) -> None:
    param, results = load_all(folder, CFG)
    suspens = reconcile(results, param)
    enrich(suspens, DATA / CFG["fichiers"]["base"])
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    inputs = [folder / CFG["fichiers"][k] for k in SLOTS]
    audit = write_audit(OUT / f"audit_{stamp}.json", suspens, results, CFG, inputs)
    excel = write_excel(OUT / f"rapprochement_{stamp}.xlsx", suspens, results)
    st.session_state["reco"] = {"suspens": suspens, "results": results, "excel": excel, "audit": audit, "source": source}


# Au premier affichage, les fichiers du dossier donnees/ sont rapprochés directement
if "reco" not in st.session_state:
    run_reconciliation(DATA, "fichiers du dossier donnees/")

with tab_reco:
    with st.expander("Déposer d'autres fichiers"):
        uploads = {k: st.file_uploader(label, key=k) for k, label in SLOTS.items()}
        c1, c2 = st.columns(2)
        if c1.button("Lancer avec les fichiers déposés", disabled=not all(uploads.values())):
            tmp = Path(tempfile.mkdtemp())
            for k, f in uploads.items():
                (tmp / CFG["fichiers"][k]).write_bytes(f.getvalue())
            run_reconciliation(tmp, "fichiers déposés")
        if c2.button("Revenir aux fichiers d'exemple"):
            run_reconciliation(DATA, "fichiers du dossier donnees/")

    reco = st.session_state.get("reco")
    if reco:
        st.caption(f"Source : {reco['source']}")
    if reco:
        suspens, results = reco["suspens"], reco["results"]
        bloques = [r.fichier for r in results if r.bloque]
        if bloques:
            st.error(f"Fichiers bloqués, non rapprochés : {', '.join(bloques)}. Voir les contrôles ci-dessous.")
        counts = Counter(s.type for s in suspens)
        cols = st.columns(5)
        cols[0].metric("Suspens", len(suspens))
        for col, code in zip(cols[1:], ["QTE", "ABS_DEP", "ABS_INT", "DEP"]):
            col.metric(code, counts.get(code, 0))

        f1, f2 = st.columns(2)
        fonds = f1.multiselect("Fonds", sorted({s.fonds for s in suspens}))
        cons = f2.multiselect("Conservateur", ["A", "B", "C"])
        shown = [
            s for s in suspens
            if (not fonds or s.fonds in fonds)
            and (not cons or {s.conservateur_interne, s.conservateur_depositaire} & set(cons))
        ]
        st.dataframe(suspens_rows(shown), width="stretch", hide_index=True)

        with st.expander("Lignes hors rapprochement (écartées par règle ou rejetées)"):
            st.dataframe(hors_rapprochement_rows(results), width="stretch", hide_index=True)
        with st.expander("Contrôles des fichiers"):
            st.dataframe(controle_rows(results), width="stretch", hide_index=True)

        st.subheader("Point de situation (à copier dans votre mail)")
        st.text_area("Récapitulatif", summary_text(suspens, results, CFG), height=300)
        st.download_button("Télécharger l'export Excel", reco["excel"].read_bytes(), file_name=reco["excel"].name)
        st.caption(f"Journal d'audit enregistré : {reco['audit'].relative_to(ROOT)}")

with tab_questions:
    st.caption(
        "Questions couvertes : encours valorisé d'un fonds, échéances à venir, opérations non dénouées. "
        "Les chiffres viennent de requêtes SQL en lecture seule sur la base de gestion ; le LLM ne fait que choisir la requête et rédiger la phrase."
    )
    question = st.text_input("Votre question", placeholder="Combien vaut Orsay Obligations au cours de clôture ?")
    if st.button("Demander") and question:
        load_dotenv(ROOT / ".env")
        try:
            llm = ClaudeLLM(CFG["assistant"]["modele"])
            rep = answer(question, llm, DATA / CFG["fichiers"]["base"], CFG["date_arrete"])
        except Exception as exc:  # clé absente/expirée, réseau, refus de toute la chaîne : on l'affiche sans planter
            st.error(f"Assistant indisponible : {exc}")
        else:
            replis = sorted(set(llm.modeles_servis) - {llm.model})
            if replis:
                st.info(f"Le modèle principal a refusé ; réponse obtenue par repli sur : {', '.join(replis)}")
            if rep.phrase:
                st.success(rep.phrase)
            if rep.avertissement:
                st.warning(rep.avertissement)
            if rep.resultat:
                if "total" in rep.resultat:
                    st.metric("Total calculé", f"{rep.resultat['total']:,.2f}".replace(",", " "))
                st.dataframe(rep.resultat["lignes"], width="stretch", hide_index=True)
                source = f"Outil : {rep.resultat['outil']}\nParamètres : {rep.resultat['parametres']}\nRequête : {rep.resultat['requete']}"
                st.code(source, language="text")
