import streamlit as st
import pandas as pd
import pickle
import os
import json
import pm4py
from pm4py.visualization.petri_net import visualizer as pn_visualizer

from evaluation import choose_best_model_internal
from preprocessing import extract_process_structure

# Importa ENTRAMBI i moduli LLM
try:
    import llm_chatbot
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False

try:
    import llm_chatbot_local
    LOCAL_AVAILABLE = True
except ImportError:
    LOCAL_AVAILABLE = False

# --- CONFIGURAZIONE PAGINA ---
st.set_page_config(
    page_title="CASAS Aruba – Process Mining AI",
    layout="wide",
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

# --- PATH FILE LOCALI ---
LOCAL_CSV     = "data/dataset_aruba_attivita.csv"
LOCAL_MODELS  = "data/models.pkl"
LOCAL_METRICS = "data/metrics.json"

st.title("🏠 CASAS Aruba – Process Mining + AI")

# =========================================================
# SIDEBAR: CONFIGURAZIONE AI
# =========================================================
st.sidebar.header("⚙️ Configurazione AI")

ai_mode = st.sidebar.radio(
    "Scegli il Motore AI:",
    ["Google Gemini (Cloud)", "Modello Locale (Ollama)"]
)

# Reset stato se cambia il motore
if st.session_state.get("ai_mode") != ai_mode:
    st.session_state["ai_mode"]    = ai_mode
    st.session_state["llm_ready"]  = False
    st.session_state["messages"]   = []
    st.session_state.pop("gemini_file", None)
    st.session_state.pop("csv_context", None)

ai_engine = None
data_ref  = None

if ai_mode == "Google Gemini (Cloud)":
    if not GEMINI_AVAILABLE:
        st.sidebar.error("Modulo llm_chatbot.py mancante.")
    else:
        ai_engine = llm_chatbot
        if not st.session_state.get("llm_ready"):
            st.session_state["llm_ready"] = ai_engine.init_llm_from_config("config.json")

        if st.session_state.get("llm_ready"):
            st.sidebar.success("✅ Gemini 2.0 Attivo")
        else:
            key = st.sidebar.text_input("API Key Gemini:", type="password")
            if key:
                import google.generativeai as genai
                try:
                    genai.configure(api_key=key)
                    ai_engine.client      = genai.GenerativeModel("gemini-3.6-flash")
                    ai_engine.TEMPERATURE = 0.7
                    st.session_state["llm_ready"] = True
                    st.rerun()
                except Exception as e:
                    st.sidebar.error(f"Errore: {e}")

elif ai_mode == "Modello Locale (Ollama)":
    if not LOCAL_AVAILABLE:
        st.sidebar.error("Modulo llm_chatbot_local.py mancante.")
    else:
        ai_engine = llm_chatbot_local
        if not st.session_state.get("llm_ready"):
            st.session_state["llm_ready"] = ai_engine.init_llm_from_config("config.json")

        if st.session_state.get("llm_ready"):
            st.sidebar.success("✅ AI Locale Attiva")
        else:
            local_url   = st.sidebar.text_input("Base URL:", value="http://localhost:11434/v1")
            local_model = st.sidebar.text_input("Nome Modello:", value="llama3.2")
            if st.sidebar.button("Connetti Locale"):
                from openai import OpenAI
                try:
                    ai_engine.client      = OpenAI(base_url=local_url, api_key="local-mode")
                    ai_engine.MODEL_NAME  = local_model
                    ai_engine.TEMPERATURE = 0.7
                    st.session_state["llm_ready"] = True
                    st.rerun()
                except Exception as e:
                    st.sidebar.error(f"Errore: {e}")

st.sidebar.divider()

# =========================================================
# CARICAMENTO DATI
# =========================================================
st.sidebar.subheader("📂 Sorgente Dati")
load_btn = st.sidebar.button("📂 Carica Dati Locali", use_container_width=True)

if "data_loaded" not in st.session_state:
    st.session_state["data_loaded"] = False


def load_data_routine(dataframe, models_pkl, metrics_json):
    st.session_state["df"]      = dataframe
    st.session_state["models"]  = models_pkl
    st.session_state["scores"]  = metrics_json
    st.session_state["data_loaded"] = True
    # Reset struttura processo ad ogni caricamento
    st.session_state.pop("process_structure", None)

    if st.session_state.get("llm_ready") and ai_engine:
        with st.sidebar.status("Preparazione dati per AI...") as status:
            if ai_mode == "Google Gemini (Cloud)":
                st.session_state["gemini_file"] = ai_engine.upload_csv_to_gemini(dataframe)
            else:
                st.session_state["csv_context"] = ai_engine.prepare_csv_for_llm(dataframe)
            status.update(label="✅ Dati pronti per l'AI!", state="complete")


if load_btn:
    if os.path.exists(LOCAL_CSV) and os.path.exists(LOCAL_MODELS):
        try:
            df = pd.read_csv(LOCAL_CSV)
            if "time:timestamp" in df.columns:
                df["time:timestamp"] = pd.to_datetime(df["time:timestamp"])
            with open(LOCAL_MODELS, "rb") as f:
                mods = pickle.load(f)
            sc = json.load(open(LOCAL_METRICS)) if os.path.exists(LOCAL_METRICS) else {}
            load_data_routine(df, mods, sc)
            st.success("✅ Dati caricati con successo!")
        except Exception as e:
            st.error(f"Errore caricamento: {e}")
    else:
        st.sidebar.error("File locali non trovati. Usa l'upload manuale.")

if not st.session_state["data_loaded"]:
    st.sidebar.markdown("**Oppure carica manualmente:**")
    up_csv  = st.sidebar.file_uploader("Upload CSV", type="csv")
    up_pkl  = st.sidebar.file_uploader("Upload Models (.pkl)", type="pkl")
    up_json = st.sidebar.file_uploader("Upload Metrics (.json)", type="json")
    if up_csv and up_pkl:
        df   = pd.read_csv(up_csv)
        if "time:timestamp" in df.columns:
            df["time:timestamp"] = pd.to_datetime(df["time:timestamp"])
        mods = pickle.load(up_pkl)
        sc   = json.load(up_json) if up_json else {}
        load_data_routine(df, mods, sc)
        st.rerun()

# =========================================================
# INTERFACCIA PRINCIPALE
# =========================================================
if st.session_state["data_loaded"]:
    df     = st.session_state["df"]
    models = st.session_state["models"]
    scores = st.session_state.get("scores", {})

    # Riferimento dati per AI
    if ai_mode == "Google Gemini (Cloud)":
        data_ref = st.session_state.get("gemini_file", None)
    else:
        data_ref = st.session_state.get("csv_context", "")

    # Struttura processo (DFG)
    if "process_structure" not in st.session_state:
        with st.spinner("Estrazione struttura processo..."):
            st.session_state["process_structure"] = extract_process_structure(df)
    process_structure_text = st.session_state["process_structure"]
    metrics_context        = json.dumps(scores, indent=2)

    # ----- KPI rapidi -----
    n_cases      = df["case:concept:name"].nunique() if "case:concept:name" in df.columns else 0
    n_events     = len(df)
    n_activities = df["concept:name"].nunique() if "concept:name" in df.columns else 0
    valid_scores = {k: v for k, v in scores.items() if isinstance(v, dict) and "error" not in v}
    best_name    = choose_best_model_internal(scores) if scores else None

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("📋 Casi (periodi)", f"{n_cases:,}")
    col2.metric("⚡ Eventi totali",  f"{n_events:,}")
    col3.metric("🎯 Attività uniche", f"{n_activities}")
    col4.metric("🏆 Miglior Modello", best_name or "—")

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
        st.dataframe(df.head(50), use_container_width=True)

        st.divider()
        c1, c2 = st.columns(2)

        with c1:
            st.subheader("🔢 Distribuzione Attività")
            if "concept:name" in df.columns:
                act_counts = df["concept:name"].value_counts().reset_index()
                act_counts.columns = ["Attività", "N. Eventi"]
                st.bar_chart(act_counts.set_index("Attività"))

        with c2:
            st.subheader("📅 Distribuzione per Periodo")
            if "case:concept:name" in df.columns:
                df["_period"] = df["case:concept:name"].str.split("_").str[-1]
                period_counts = df["_period"].value_counts().reset_index()
                period_counts.columns = ["Periodo", "N. Attivazioni"]
                st.bar_chart(period_counts.set_index("Periodo"))

        if valid_scores:
            st.divider()
            st.subheader("📊 Metriche di conformità (riepilogo)")
            st.json(valid_scores)

    # ============================================================
    # TAB 2: MODELLI PETRI NET
    # ============================================================
    with tab2:
        model_names = list(models.keys())
        idx         = model_names.index(best_name) if best_name and best_name in model_names else 0
        selected    = st.selectbox("Seleziona Modello:", model_names, index=idx)

        if selected:
            data = models[selected]

            # Badge "Miglior Modello"
            if selected == best_name:
                st.markdown(
                    f"<span class='badge-best'>🏆 Miglior Modello</span>",
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
                    st.graphviz_chart(dot_src, use_container_width=True)

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
        if isinstance(data, tuple) and len(data) == 3:
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

            # Grafico a barre
            st.bar_chart(compare_df[["Fitness", "Precision", "F1 Score"]])

            st.divider()

            # Tabella dettagliata
            st.subheader("📋 Tabella Riepilogativa")

            for _, row in compare_df.reset_index().iterrows():
                badge = " 🏆" if row["Modello"] == best_name else ""
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
                        interp = "🔵 **Alta Fitness** — Replay quasi perfetto, ma bassa precision (overfitting)."
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
| **Fitness** | Quante tracce del log sono riproducibili dal modello (0→1) |
| **Precision** | Quanto è "stretto" il modello (evita comportamenti non presenti nel log) |
| **F1 Score** | Media armonica di Fitness e Precision — bilancia i due estremi |

> **Inductive Miner** ha fitness quasi perfetta (~1.0) ma bassa precision: il modello permette troppe varianti.  
> **Alpha Miner** ha buona precision ma non sa gestire loop → fitness bassa.  
> **Heuristic Miner** è intermedio ma in questo dataset non eccelle.
""")
        else:
            st.info("Nessuna metrica disponibile. Assicurati di aver eseguito `main.py` o caricato `metrics.json`.")

    # ============================================================
    # TAB 4: ANALISTA AI
    # ============================================================
    with tab4:
        st.header(f"🤖 AI Process Analyst — {ai_mode}")

        llm_ready = st.session_state.get("llm_ready", False)

        if not llm_ready:
            st.warning("⚠️ Configura prima il motore AI nella sidebar.")
        elif not data_ref and ai_mode == "Google Gemini (Cloud)":
            st.warning("⚠️ Dati non ancora inviati a Gemini. Ricarica i dati dalla sidebar.")

        # Storico chat
        if "messages" not in st.session_state or not st.session_state.messages:
            st.session_state.messages = [
                {"role": "assistant",
                 "content": (
                     f"Ciao! Sono il tuo analista AI connesso tramite **{ai_mode}**. 🚀\n\n"
                     f"Ho analizzato il processo della smart home CASAS Aruba. "
                     f"Sono pronto a:\n"
                     f"- 📄 Generare un report esecutivo\n"
                     f"- ⚠️ Rilevare anomalie comportamentali\n"
                     f"- 🔮 Predire il prossimo step\n"
                     f"- 💬 Rispondere a qualsiasi domanda sul processo!\n\n"
                     f"**Miglior modello rilevato:** {best_name or '—'}"
                 )}
            ]

        c_act, c_chat = st.columns([1, 2.5])

        with c_act:
            st.subheader("🛠️ Azioni Rapide")

            if st.button("📄 Genera Report Completo", use_container_width=True, disabled=not llm_ready):
                st.session_state.messages.append(
                    {"role": "user", "content": "Genera un report esecutivo completo del processo analizzando i dati."})
                with st.spinner(f"Analisi in corso con {ai_mode}..."):
                    rep = ai_engine.generate_process_analysis(metrics_context, data_ref)
                    st.session_state.messages.append({"role": "assistant", "content": rep})
                    st.session_state["last_report"] = rep
                st.rerun()

            if st.button("⚠️ Trova Anomalie", use_container_width=True, disabled=not llm_ready):
                st.session_state.messages.append(
                    {"role": "user", "content": "Esegui un audit del processo e trova le principali anomalie."})
                with st.spinner(f"Audit del processo in corso con {ai_mode}..."):
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
            if st.button("Prevedi Prossimo Step", use_container_width=True, disabled=not llm_ready):
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
                    use_container_width=True
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
                            with st.spinner(f"Elaborazione via {ai_mode}..."):
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
            Clicca <strong>📂 Carica Dati Locali</strong> nella sidebar,<br>
            oppure carica manualmente CSV, PKL e JSON.
        </p>
        <br>
        <p style="color:#64748b;">
            Pipeline: <strong>CASAS Aruba Sensors</strong> → Event Log → 
            Alpha/Heuristic/Inductive Miner → Petri Net → 
            Gemini AI Analysis
        </p>
    </div>
    """, unsafe_allow_html=True)
