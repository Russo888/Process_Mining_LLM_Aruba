import streamlit as st
import pandas as pd
import pickle
import json
import pm4py
from pm4py.visualization.petri_net import visualizer as pn_visualizer

from evaluation import f1_score
from project_paths import CONFIG_PATH
from dashboard_results import (available_results, load_result_bundle, best_models,
                               comparison_details, selected_model_context)
from preprocessing import extract_process_structure
from dashboard_data import period_summary, zone_summary
from dashboard_charts import (metric_comparison_chart, zone_distribution_chart,
                              period_distribution_chart, simplified_dfg)

from llm_chatbot import GeminiEngine

# --- CONFIGURAZIONE PAGINA ---
st.set_page_config(
    page_title="CASAS Aruba – Process Mining AI",
    layout="wide",
    initial_sidebar_state="expanded",
    page_icon="🏠"
)

# --- CSS PERSONALIZZATO ---
st.markdown("""
<style>
    /* Sfondo scuro */
    .stApp { background-color: #0f172a; }
    
    /* Metriche */
    [data-testid="stMetric"] {
        background: linear-gradient(135deg, #ffffff, #f0fdf4);
        border-radius: 12px;
        padding: 16px;
        border: 1px solid #bbf7d0;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
    }
    [data-testid="stMetricValue"] { color: #166534; font-size: 2rem !important; }
    [data-testid="stMetricLabel"] { color: #475569; font-weight: 600; }

    /* Tabs */
    .stTabs [data-baseweb="tab-list"] { gap: 8px; border-bottom: 2px solid #e2e8f0; }
    .stTabs [data-baseweb="tab"] {
        background-color: #ffffff;
        border: 1px solid #e2e8f0;
        border-bottom: none;
        border-radius: 8px 8px 0 0;
        color: #64748b;
        padding: 8px 20px;
    }
    .stTabs [aria-selected="true"] {
        background: linear-gradient(135deg, #22c55e, #16a34a);
        color: white;
        border-color: #16a34a;
    }

    /* Titolo */
    h1 { 
        background: linear-gradient(90deg, #15803d, #22c55e);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-size: 2.2rem !important;
        font-weight: 800 !important;
    }

    /* Sidebar */
    [data-testid="stSidebar"] { background-color: #0f172a; border-right: 1px solid #e2e8f0; }
    
    /* Card info */
    .info-card {
        background: linear-gradient(135deg, #ffffff, #f0fdf4);
        border-radius: 12px;
        padding: 16px 20px;
        border: 1px solid #bbf7d0;
        margin-bottom: 12px;
        color: #1e293b;
    }
    .badge-best {
        display: inline-block;
        background: linear-gradient(90deg, #22c55e, #15803d);
        color: white;
        padding: 2px 10px;
        border-radius: 20px;
        font-size: 0.75rem;
        font-weight: 700;
        margin-left: 8px;
    }
    
    /* Pulsanti principali (sidebar e azioni repide) */
    .stButton button {
        background-color: #22c55e !important;
        color: white !important;
        border: none !important;
        border-radius: 8px !important;
        font-weight: 600 !important;
        transition: all 0.3s ease !important;
    }
    .stButton button:hover {
        background-color: #16a34a !important;
        box-shadow: 0 4px 12px rgba(34, 197, 94, 0.4) !important;
    }
</style>
""", unsafe_allow_html=True)

st.title("🏠 CASAS Aruba – Process Mining + AI")

# =========================================================
# SIDEBAR: CONFIGURAZIONE AI
# =========================================================
st.sidebar.header("⚙️ Configurazione AI")

st.sidebar.caption("Google Gemini · accesso tramite API key")
ai_engine = None
data_ref = None
if "ai_engine" not in st.session_state:
    st.session_state["ai_engine"] = GeminiEngine()
    st.session_state["llm_ready"] = st.session_state["ai_engine"].init_llm_from_config()
ai_engine = st.session_state["ai_engine"]
try:
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
except (OSError, ValueError) as exc:
    st.error(f"Configurazione non leggibile: {exc}")
    st.stop()
with st.sidebar.expander("Impostazioni connessione", expanded=not st.session_state.get("llm_ready")):
    key = st.text_input("API Key Gemini:", type="password")
    model = st.text_input("Modello Gemini:", value=config.get("model_name", "gemini-3.6-flash"))
    if st.button("Configura Gemini"):
        st.session_state["llm_ready"] = ai_engine.init_llm_from_config(api_key=key, model_name=model)
        for state_key in ("gemini_file", "messages", "last_report"):
            st.session_state.pop(state_key, None)
if st.session_state.get("llm_ready"):
    st.sidebar.success(f"Configurato: {ai_engine.model_name}")
    st.sidebar.caption("La connessione viene verificata alla prima richiesta.")
elif ai_engine.last_error:
    st.sidebar.info(ai_engine.last_error)

st.sidebar.divider()

# =========================================================
# CARICAMENTO DATI
# =========================================================
st.sidebar.subheader("📂 Sorgente Dati")
result_catalog = available_results()
source_choice = st.sidebar.selectbox(
    "Esperimento da caricare", list(result_catalog) + ["Upload manuale"], key="results_source")
load_btn = st.sidebar.button("Ricarica risultati", width="stretch", disabled=source_choice == "Upload manuale")

if "data_loaded" not in st.session_state:
    st.session_state["data_loaded"] = False


def load_data_routine(dataframe, models_pkl, metrics_json, metadata=None, diagnostics=None):
    required = ["case:concept:name", "concept:name", "time:timestamp"]
    if not set(required).issubset(dataframe.columns) or dataframe.empty:
        raise ValueError("CSV vuoto o privo delle colonne PM4Py richieste")
    if dataframe[required].isna().any().any():
        raise ValueError("Il CSV contiene valori mancanti nelle colonne PM4Py")
    dataframe = dataframe.copy()
    dataframe["time:timestamp"] = pd.to_datetime(dataframe["time:timestamp"], errors="raise")
    dataframe = dataframe.sort_values("time:timestamp", kind="stable").reset_index(drop=True)
    if not isinstance(models_pkl, dict) or not models_pkl:
        raise ValueError("Il file modelli deve contenere un dizionario non vuoto")
    if not isinstance(metrics_json, dict):
        raise ValueError("Le metriche devono essere un dizionario JSON")
    st.session_state["df"] = dataframe
    st.session_state["models"] = models_pkl
    st.session_state["scores"] = {k: v for k, v in metrics_json.items() if k in models_pkl}
    st.session_state["evaluation_metadata"] = metadata or {}
    st.session_state["comparison_diagnostics"] = diagnostics or {}
    st.session_state["data_loaded"] = True
    for key in ("process_structure", "gemini_file", "messages", "last_report",
                "selected_process_model", "active_process_model"):
        st.session_state.pop(key, None)


if source_choice != st.session_state.get("loaded_source") or load_btn:
    st.session_state["data_loaded"] = False
    if source_choice in result_catalog:
        try:
            with st.spinner("Caricamento del dataset e dei modelli dell'esperimento..."):
                load_data_routine(*load_result_bundle(result_catalog[source_choice]))
            st.session_state["loaded_source"] = source_choice
        except Exception as e:
            st.error(f"Errore caricamento dell'esperimento: {e}")
    else:
        st.session_state["loaded_source"] = source_choice

if not st.session_state["data_loaded"]:
    st.sidebar.markdown("**Oppure carica manualmente:**")
    up_csv  = st.sidebar.file_uploader("Upload CSV", type="csv")
    up_pkl  = st.sidebar.file_uploader("Upload Models (.pkl)", type="pkl")
    up_json = st.sidebar.file_uploader("Upload Metrics (.json)", type="json")
    st.sidebar.caption("Carica file PKL solo da fonti fidate.")
    if up_csv and up_pkl:
        try:
            df = pd.read_csv(up_csv)
            mods = pickle.load(up_pkl)
            sc = json.load(up_json) if up_json else {}
            load_data_routine(df, mods, sc)
            st.session_state["loaded_source"] = source_choice
        except Exception as exc:
            st.error(f"Errore caricamento: {exc}")
        else:
            st.rerun()

# =========================================================
# INTERFACCIA PRINCIPALE
# =========================================================
if st.session_state["data_loaded"]:
    df     = st.session_state["df"]
    models = st.session_state["models"]
    scores = st.session_state.get("scores", {})
    metadata = st.session_state.get("evaluation_metadata", {})
    diagnostics = st.session_state.get("comparison_diagnostics", {})
    leaders = best_models(scores)
    best_name = leaders[0] if leaders else None
    model_names = list(models)
    selected = st.sidebar.selectbox(
        "Modello di processo", model_names,
        index=model_names.index(best_name) if best_name in model_names else 0,
        key="selected_process_model")
    if st.session_state.get("active_process_model") != selected:
        st.session_state["active_process_model"] = selected
        for key in ("messages", "last_report"):
            st.session_state.pop(key, None)
    st.sidebar.caption("La scelta aggiorna rete, metriche e contesto dell'analista AI.")
    st.subheader(selected)
    st.caption(f"Esperimento: {source_choice}. Periodo: {df['time:timestamp'].min():%d/%m/%Y} – {df['time:timestamp'].max():%d/%m/%Y}.")
    selected_scores = scores.get(selected, {})
    if f1_score(selected_scores) is not None:
        selected_cols = st.columns(3)
        for col, label, value in zip(selected_cols, ["Fitness", "Precision", "F1"],
                                     [selected_scores["fitness"], selected_scores["precision"], f1_score(selected_scores)]):
            col.metric(label, f"{value:.4f}")
    elif "error" in selected_scores:
        st.warning(f"Valutazione non completata: {selected_scores['error']}")
    else:
        st.info("Metriche non disponibili per questa configurazione.")
    if metadata:
        st.caption(f"Valutazione in-sample: {len(metadata.get('evaluated_cases', []))} casi completi, "
                   f"{metadata.get('evaluated_events', '—')} eventi. Seed {metadata.get('seed', '—')}. "
                   "I modelli sono stati costruiti sullo stesso log usato per la valutazione.")

    # Il campione viene rigenerato alla configurazione e al caricamento.
    if st.session_state.get("llm_ready") and "gemini_file" not in st.session_state:
        try:
            with st.spinner("Preparazione campione per Gemini..."):
                st.session_state["gemini_file"] = ai_engine.upload_csv_to_gemini(df)
        except Exception as exc:
            st.warning(f"Contesto CSV non disponibile: {exc}")
    data_ref = st.session_state.get("gemini_file")

    # Struttura processo (DFG)
    if "process_structure" not in st.session_state:
        with st.spinner("Estrazione struttura processo..."):
            st.session_state["process_structure"] = extract_process_structure(df)
    metrics_context = selected_model_context(selected, models[selected], scores, diagnostics, metadata, source_choice)
    process_structure_text = (f"CONFIGURAZIONE ATTIVA:\n{metrics_context}\n\n"
                              f"DFG DEL LOG (indipendente dal modello):\n{st.session_state['process_structure']}")

    # ----- KPI rapidi -----
    n_cases      = df["case:concept:name"].nunique() if "case:concept:name" in df.columns else 0
    n_events     = len(df)
    n_activities = df["concept:name"].nunique() if "concept:name" in df.columns else 0
    valid_scores = {k: v for k, v in scores.items() if f1_score(v) is not None}

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("📋 Casi (periodi)", f"{n_cases:,}")
    col2.metric("⚡ Eventi totali",  f"{n_events:,}")
    col3.metric("🎯 Zone uniche", f"{n_activities}")
    col4.metric("Primi per F1 (pari merito)" if len(leaders) > 1 else "Primo per F1",
                str(len(leaders)) if len(leaders) > 1 else best_name or "—")
    if len(leaders) > 1:
        st.caption("Primi a pari merito: " + "; ".join(leaders))

    st.caption("Miglior modello: massima media armonica di fitness e precision. Metriche in-sample su un campione di casi; non misurano prestazioni su dati nuovi.")
    st.divider()

    tab1, tab2, tab3, tab4 = st.tabs([
        "📊 Dati & Statistiche",
        "🕸️ Modelli Petri Net",
        "📈 Confronto Metriche",
        "🤖 Analista AI"
    ])

    # ============================================================
    # TAB 1: DATI & STATISTICHE
    # ============================================================
    with tab1:
        st.subheader("📋 Campione Event Log")
        st.caption("Le etichette identificano zone convenzionali associate ai sensori; non sono attività umane validate. Sono inclusi entrambi gli stati ON/OFF e OPEN/CLOSE.")
        st.dataframe(df.head(50), width="stretch")

        st.divider()
        c1, c2 = st.columns(2)

        with c1:
            st.subheader("🔢 Eventi per zona")
            st.altair_chart(zone_distribution_chart(zone_summary(df)), width="stretch")
            st.caption("Conteggi di eventi compressi, inclusi ON/OFF e OPEN/CLOSE. Non misurano il tempo trascorso nelle zone né il numero di attività umane.")

        with c2:
            st.subheader("📅 Eventi per fascia oraria")
            period_stats = period_summary(df)
            period_view = st.radio(
                "Misura per fascia", ["Eventi per ora di calendario", "Eventi totali"],
                key="period_view", horizontal=True)
            st.altair_chart(period_distribution_chart(
                period_stats, normalized=period_view == "Eventi per ora di calendario"), width="stretch")
            st.caption("Ordine temporale: Notte, Mattina, Pomeriggio, Sera. Fasce di 6, 6, 7 e 5 ore. Il rapporto per ora corregge le diverse durate e i giorni di bordo parziali.")

        with st.expander("Come sono normalizzati i conteggi per fascia"):
            st.dataframe(period_stats, hide_index=True, width="stretch", column_config={
                "Ore di calendario": st.column_config.NumberColumn(format="%.2f"),
                "Eventi per ora": st.column_config.NumberColumn(format="%.2f"),
            })
            st.caption("Il denominatore conta le ore di ogni fascia comprese tra il primo e l'ultimo timestamp del log. Non misura la presenza nelle stanze o l'uptime dei sensori; eventuali buchi interni di acquisizione non sono rilevati. Con una finestra di durata zero il rapporto non è calcolabile.")

        if valid_scores:
            st.divider()
            st.subheader("📊 Metriche di conformità (riepilogo)")
            st.json(valid_scores)

    # ============================================================
    # TAB 2: MODELLI PETRI NET
    # ============================================================
    with tab2:
        st.subheader("Flussi osservati — DFG semplificato")
        dfg_graph, n_flows, shown_transitions, total_transitions = simplified_dfg(df)
        if total_transitions:
            st.graphviz_chart(dfg_graph.source, width="stretch", height=480)
            coverage = shown_transitions / total_transitions
            st.caption(f"Primi {min(12, n_flows)} flussi su {n_flows}: {shown_transitions:,} di {total_transitions:,} transizioni ({coverage:.1%}). I numeri sugli archi sono frequenze; i passaggi tra casi diversi sono esclusi. Vista del log, indipendente dal modello selezionato; i flussi e le zone meno frequenti possono essere omessi.")
        else:
            st.info("Nessuna transizione all'interno dei casi disponibile per il DFG.")
        st.divider()
        st.subheader("Rete di Petri completa")
        st.caption("Per leggere la rete completa usa il pulsante a schermo intero nell'angolo del grafico. Il DFG sopra offre una vista sintetica dei passaggi osservati.")
        st.write(f"**Modello selezionato:** {selected}")

        if selected:
            data = models[selected]

            # Badge "Miglior Modello"
            if selected in leaders:
                st.markdown(
                    "<span class='badge-best'>Primo per F1 nel confronto caricato</span>",
                    unsafe_allow_html=True
                )

            if isinstance(data, dict) and "error" in data:
                st.error(f"❌ Errore durante la discovery: {data['error']}")
            elif isinstance(data, tuple) and len(data) == 3:
                net, im, fm = data
                try:
                    # FIX: pn_visualizer.apply() restituisce un oggetto Graphviz.
                    # Usiamo il formato DOT per st.graphviz_chart()
                    gviz    = pn_visualizer.apply(net, im, fm)
                    dot_src = gviz.source  # stringa DOT
                    st.graphviz_chart(dot_src, width="stretch")

                    # Metriche del modello
                    if scores and selected in scores:
                        m = scores[selected]
                        if "error" not in m:
                            mc1, mc2, mc3 = st.columns(3)
                            fitness   = m.get("fitness", 0)
                            precision = m.get("precision", 0)
                            f1 = 2 * fitness * precision / (fitness + precision) if (fitness + precision) > 0 else 0
                            mc1.metric("🎯 Fitness",   f"{fitness:.3f}")
                            mc2.metric("🔬 Precision", f"{precision:.3f}")
                            mc3.metric("⚖️ F1 Score",  f"{f1:.3f}")
                        else:
                            st.error(f"Errore valutazione: {m['error']}")
                except Exception as e:
                    st.error(f"Errore visualizzazione Petri Net: {e}")
            else:
                st.warning("Modello non in formato valido.")

        # Dettaglio rete
        if selected and isinstance(data, tuple) and len(data) == 3:
            with st.expander("🔍 Dettaglio Petri Net"):
                net_obj = data[0]
                st.write(f"**Luoghi (Places):** {len(net_obj.places)}")
                st.write(f"**Transizioni (Transitions):** {len(net_obj.transitions)}")
                st.write(f"**Archi (Arcs):** {len(net_obj.arcs)}")

    # ============================================================
    # TAB 3: CONFRONTO METRICHE
    # ============================================================
    with tab3:
        st.subheader("📈 Confronto Fitness & Precision — tutti i Miner")
        st.caption(f"Configurazione attiva: {selected}. Il confronto mostra tutti i modelli dell'esperimento caricato.")
        if diagnostics:
            st.dataframe(comparison_details(diagnostics).sort_values("F1", ascending=False, na_position="last"),
                         hide_index=True, width="stretch")
            st.caption("Fitness mescolata: replay dopo permutazione delle zone negli stessi casi. "
                       "Una differenza vicina a zero indica scarsa sensibilità dell'indicatore all'ordine. "
                       "Le tracce fitting sono casi interamente riprodotti; la fitness aggregata è una misura diversa.")
            st.download_button("Scarica tabella del confronto", comparison_details(diagnostics).to_csv(index=False),
                               file_name="confronto_modelli.csv", mime="text/csv")

        if valid_scores:
            # Prepara DataFrame confronto
            rows = []
            for name, m in valid_scores.items():
                fitness   = m.get("fitness", 0)
                precision = m.get("precision", 0)
                f1 = 2 * fitness * precision / (fitness + precision) if (fitness + precision) > 0 else 0
                rows.append({
                    "Modello":   name,
                    "Fitness":   round(fitness, 4),
                    "Precision": round(precision, 4),
                    "F1 Score":  round(f1, 4)
                })
            compare_df = pd.DataFrame(rows).set_index("Modello")

            # Metriche indipendenti: barre affiancate e scala comune 0–1.
            st.altair_chart(metric_comparison_chart(compare_df), width="stretch")
            st.caption("Ogni barra rappresenta una metrica separata su scala 0–1; le metriche non vengono sommate.")

            st.divider()

            # Tabella dettagliata
            st.subheader("📋 Tabella Riepilogativa")

            for _, row in compare_df.reset_index().iterrows():
                badge = " 🏆" if row["Modello"] in leaders else ""
                with st.expander(f"**{row['Modello']}{badge}**"):
                    cc1, cc2, cc3 = st.columns(3)
                    cc1.metric("Fitness",   f"{row['Fitness']:.4f}")
                    cc2.metric("Precision", f"{row['Precision']:.4f}")
                    cc3.metric("F1 Score",  f"{row['F1 Score']:.4f}")

                    # Interpretazione automatica
                    fitness = row["Fitness"]
                    prec    = row["Precision"]
                    if fitness > 0.9 and prec > 0.7:
                        interp = "✅ **Ottimo** — Alta fitness e precision. Modello bilanciato."
                    elif fitness > 0.9:
                        interp = "🔵 **Alta Fitness** — Replay quasi perfetto, ma bassa precision (sovrageneralizzazione)."
                    elif prec > 0.7:
                        interp = "🟡 **Alta Precision** — Comportamento preciso ma bassa copertura dei log."
                    else:
                        interp = "🔴 **Basse metriche** — Modello non rappresentativo del processo."
                    st.markdown(interp)

            st.divider()
            st.subheader("ℹ️ Come interpretare le metriche")
            st.markdown("""
| Metrica | Significato |
|---|---|
| **Fitness** | Capacità di riprodurre il log, stimata dal replay dei token (0→1; non percentuale di tracce perfette) |
| **Precision** | Quanto è "stretto" il modello (evita comportamenti non presenti nel log) |
| **F1 Score** | Media armonica di Fitness e Precision — bilancia i due estremi |

> Le interpretazioni dipendono dai dati e dai parametri del mining. Alta fitness e bassa precision indicano un modello permissivo.
""")
        else:
            st.info("Nessuna metrica disponibile. Assicurati di aver eseguito `main.py` o caricato `metrics.json`.")

    # ============================================================
    # TAB 4: ANALISTA AI
    # ============================================================
    with tab4:
        st.header(f"🤖 AI Process Analyst — Google Gemini")

        llm_ready = st.session_state.get("llm_ready", False)

        if not llm_ready:
            st.warning("⚠️ Configura prima il motore AI nella sidebar.")
        elif not data_ref:
            st.warning("Contesto CSV non disponibile: verranno usati soltanto DFG e metriche.")

        # Storico chat
        if "messages" not in st.session_state or not st.session_state.messages:
            st.session_state.messages = [
                {"role": "assistant",
                 "content": (
                     "Questo spazio usa **Google Gemini** dopo la configurazione di una API key valida.\n\n"
                     f"Sono disponibili i dati della smart home CASAS Aruba. "
                     f"Le funzioni disponibili dopo la configurazione consentono di:\n"
                     f"- 📄 Generare un report esecutivo\n"
                     f"- ⚠️ Discutere possibili anomalie\n"
                     f"- 🔮 Suggerire una possibile prossima zona\n"
                     f"- 💬 Discutere domande sul processo\n\n"
                     f"**Modello selezionato:** {selected}. "
                     f"Le analisi sono esplorative e devono essere verificate."
                 )}
            ]

        c_act, c_chat = st.columns([1, 2.5])

        with c_act:
            st.subheader("🛠️ Azioni Rapide")

            if st.button("📄 Genera Report Completo", width="stretch", disabled=not llm_ready):
                st.session_state.messages.append(
                    {"role": "user", "content": "Genera un report esecutivo completo del processo analizzando i dati."})
                with st.spinner(f"Analisi in corso con Google Gemini..."):
                    rep = ai_engine.generate_process_analysis(f"Metriche: {metrics_context}. DFG: {process_structure_text}", data_ref)
                    st.session_state.messages.append({"role": "assistant", "content": rep})
                    st.session_state["last_report"] = rep
                st.rerun()

            if st.button("⚠️ Trova Anomalie", width="stretch", disabled=not llm_ready):
                st.session_state.messages.append(
                    {"role": "user", "content": "Esegui un audit del processo e trova le principali anomalie."})
                with st.spinner(f"Audit del processo in corso con Google Gemini..."):
                    anom = ai_engine.detect_anomalies_llm(process_structure_text, data_ref)
                    st.session_state.messages.append(
                        {"role": "assistant", "content": f"**Risultati Audit:**\n\n{anom}"})
                st.rerun()

            st.divider()
            st.subheader("🔮 Predittore Attività")
            trace_in = st.text_input(
                "Traccia parziale:",
                placeholder="es. Camera_Letto → Bagno_Principale → ..."
            )
            if st.button("Prevedi Prossimo Step", width="stretch", disabled=not llm_ready):
                if trace_in:
                    with st.spinner("Calcolo probabilità..."):
                        pred = ai_engine.predict_next_step(trace_in, process_structure_text, data_ref)
                        st.session_state.messages.append({"role": "user",  "content": f"Prevedi il prossimo step dopo: {trace_in}"})
                        st.session_state.messages.append({"role": "assistant", "content": pred})
                    st.rerun()
                else:
                    st.warning("Inserisci una traccia parziale prima di procedere.")

            # Download ultimo report
            st.divider()
            if "last_report" in st.session_state:
                st.download_button(
                    label="⬇️ Scarica Report (TXT)",
                    data=st.session_state["last_report"],
                    file_name="process_mining_report.txt",
                    mime="text/plain",
                    width="stretch"
                )

        with c_chat:
            st.subheader("💬 Chat con l'Analista AI")
            chat_container = st.container(height=550, border=True)

            with chat_container:
                for msg in st.session_state.messages:
                    with st.chat_message(msg["role"]):
                        st.markdown(msg["content"])

            if prompt := st.chat_input("Chiedi all'AI... (es. 'Quale stanza è più frequentata la mattina?')"):
                if not llm_ready:
                    st.warning("Configura prima il motore AI.")
                else:
                    st.session_state.messages.append({"role": "user", "content": prompt})
                    with chat_container:
                        with st.chat_message("user"):
                            st.markdown(prompt)
                        with st.chat_message("assistant"):
                            with st.spinner(f"Elaborazione via Google Gemini..."):
                                resp = ai_engine.ask_llm(
                                    prompt,
                                    f"Modello selezionato: {selected if 'selected' in locals() else best_name}. "
                                    f"Metriche: {metrics_context}. DFG: {process_structure_text}",
                                    data_ref
                                )
                                st.markdown(resp)
                    st.session_state.messages.append({"role": "assistant", "content": resp})

else:
    # Pagina di benvenuto
    st.markdown("""
    <div style="text-align:center; padding: 60px 20px;">
        <h2 style="color:#15803d;">👈 Carica i dati per iniziare</h2>
        <p style="color:#475569; font-size:1.1rem;">
            Seleziona un esperimento nella sidebar,<br>
            oppure scegli Upload manuale e carica CSV, PKL e JSON.
        </p>
        <br>
        <p style="color:#64748b;">
            Pipeline: <strong>CASAS Aruba Sensors</strong> → Event Log → 
            Alpha/Heuristic/Inductive Miner → Petri Net → 
            Google Gemini AI Analysis
        </p>
    </div>
    """, unsafe_allow_html=True)
