import streamlit as st
import pandas as pd
import pickle
import os
import json
import pm4py
from pm4py.visualization.petri_net import visualizer as pn_visualizer
from evaluation import choose_best_model_internal
from preprocessing import extract_process_structure

# Importa il modulo LLM
try:
    import llm_chatbot
except ImportError:
    st.error("Il file 'llm_chatbot.py' non è stato trovato.")

# --- CONFIGURAZIONE PAGINA ---
st.set_page_config(page_title="CASAS Process Mining AI", layout="wide", page_icon="🏠")

# --- PATH FILE LOCALI ---
LOCAL_CSV = "data/dataset_aruba_attivita.csv"
LOCAL_MODELS = "data/models.pkl"
LOCAL_METRICS = "data/metrics.json"

st.title("🏠 CASAS Aruba – Process Mining con assistente AI")

# --- SIDEBAR: CONFIGURAZIONE ---
st.sidebar.header("⚙️ Configurazione AI")

# 1. Init LLM
if "llm_ready" not in st.session_state:
    st.session_state["llm_ready"] = llm_chatbot.init_llm_from_config("config.json")

if st.session_state["llm_ready"]:
    st.sidebar.success(f"✅ Assistente AI Attivo")
else:
    st.sidebar.warning("⚠️ Configurazione non trovata.")
    key = st.sidebar.text_input("API Key Manuale:", type="password")
    if key:
        import google.generativeai as genai

        try:
            genai.configure(api_key=key)
            llm_chatbot.client = genai.GenerativeModel("gemini-3.6-flash")
            llm_chatbot.TEMPERATURE = 0.7
            st.session_state["llm_ready"] = True
            st.rerun()
        except Exception as e:
            st.sidebar.error(f"Errore chiave: {e}")

# 2. Caricamento Dati
st.sidebar.subheader("Sorgente Dati")
load_btn = st.sidebar.button("📂 Carica Dati Locali")

# Gestione Caricamento e Upload a Gemini
if "data_loaded" not in st.session_state:
    st.session_state["data_loaded"] = False


# Funzione per gestire il caricamento del DF e l'upload all'AI
def load_data_routine(dataframe, models_pkl, metrics_json):
    st.session_state["df"] = dataframe
    st.session_state["models"] = models_pkl
    st.session_state["scores"] = metrics_json
    st.session_state["data_loaded"] = True

    # Upload su Gemini (File API)
    if st.session_state["llm_ready"]:
        with st.sidebar.status("Caricamento dati su Gemini 2.0...") as status:
            st.session_state["gemini_file"] = llm_chatbot.upload_csv_to_gemini(dataframe)
            if st.session_state["gemini_file"]:
                status.update(label="✅ Dati caricati su AI!", state="complete")
            else:
                status.update(label="❌ Errore upload AI", state="error")


if load_btn:
    if os.path.exists(LOCAL_CSV) and os.path.exists(LOCAL_MODELS):
        try:
            df = pd.read_csv(LOCAL_CSV)
            if "time:timestamp" in df.columns:
                df["time:timestamp"] = pd.to_datetime(df["time:timestamp"])

            with open(LOCAL_MODELS, "rb") as f:
                mods = pickle.load(f)

            sc = {}
            if os.path.exists(LOCAL_METRICS):
                with open(LOCAL_METRICS, "r") as f:
                    sc = json.load(f)

            load_data_routine(df, mods, sc)
            st.success("Dati caricati.")
        except Exception as e:
            st.error(f"Errore: {e}")

# Fallback Upload Manuale
if not st.session_state["data_loaded"]:
    up_csv = st.sidebar.file_uploader("Upload CSV", type="csv")
    up_pkl = st.sidebar.file_uploader("Upload Models (.pkl)", type="pkl")
    up_json = st.sidebar.file_uploader("Upload Metrics (.json)", type="json")

    if up_csv and up_pkl:
        df = pd.read_csv(up_csv)
        if "time:timestamp" in df.columns:
            df["time:timestamp"] = pd.to_datetime(df["time:timestamp"])
        mods = pickle.load(up_pkl)
        sc = json.load(up_json) if up_json else {}
        load_data_routine(df, mods, sc)
        st.rerun()

# --- INTERFACCIA PRINCIPALE ---

if st.session_state["data_loaded"]:
    df = st.session_state["df"]
    models = st.session_state["models"]
    scores = st.session_state.get("scores", {})
    gemini_file = st.session_state.get("gemini_file", None)

    # Preparazione Contesto Testuale (DFG) come aiuto
    if "process_structure" not in st.session_state:
        st.session_state["process_structure"] = extract_process_structure(df)
    process_structure_text = st.session_state["process_structure"]
    metrics_context = json.dumps(scores, indent=2)

    # TABS
    tab1, tab2, tab3 = st.tabs(["📊 Dati", "🕸️ Modello", "🤖 Analista AI"])

    with tab1:
        st.dataframe(df.head(10), use_container_width=True)
        if scores:
            clean = {k: v for k, v in scores.items() if isinstance(v, dict) and "error" not in v}
            st.json(clean)

    with tab2:
        best_name = choose_best_model_internal(scores) if scores else (list(models.keys())[0] if models else None)
        model_names = list(models.keys())
        idx = model_names.index(best_name) if best_name in model_names else 0
        selected = st.selectbox("Modello:", model_names, index=idx)

        if selected:
            data = models[selected]
            if isinstance(data, tuple) and len(data) == 3:
                net, im, fm = data
                try:
                    gviz = pn_visualizer.apply(net, im, fm)
                    st.graphviz_chart(gviz)
                    if scores and selected in scores:
                        m = scores[selected]
                        if "error" not in m:
                            c1, c2 = st.columns(2)
                            c1.metric("Fitness", f"{m.get('fitness', 0):.3f}")
                            c2.metric("Precision", f"{m.get('precision', 0):.3f}")
                except Exception as e:
                    st.error(f"Errore visualizzazione: {e}")

    with tab3:
        st.header("🤖 AI Process Analyst")

        if not gemini_file:
            st.warning("⚠️ File non caricato su Gemini. L'AI risponderà senza vedere i dati raw.")

        # Inizializza lo storico chat PRIMA di definire le colonne
        if "messages" not in st.session_state:
            st.session_state.messages = [
                {"role": "assistant",
                 "content": "Ciao! Sono il tuo analista di Process Mining. Usa le azioni rapide a sinistra o chiedimi direttamente qui qualsiasi cosa sui tuoi dati. 🚀"}
            ]

        c_act, c_chat = st.columns([1, 2.5])

        with c_act:
            st.subheader("🛠️ Azioni Rapide")
            st.markdown("Usa questi comandi per analisi veloci sui dati caricati.")

            # --- PULSANTE REPORT (Invia il risultato nella chat) ---
            if st.button("📄 Genera Report Completo", use_container_width=True):
                # 1. Aggiungiamo la "finta" domanda dell'utente alla chat
                st.session_state.messages.append({"role": "user",
                                                  "content": "Genera un report esecutivo completo del processo analizzando il file."})

                # 2. Chiamiamo l'LLM
                with st.spinner("Analisi dell'intero CSV in corso..."):
                    rep = llm_chatbot.generate_process_analysis(metrics_context, gemini_file)
                    # 3. Salviamo la risposta nello storico della chat
                    st.session_state.messages.append({"role": "assistant", "content": rep})
                # Streamlit aggiornerà automaticamente il contenitore della chat alla riga successiva

            # --- PULSANTE ANOMALIE (Invia il risultato nella chat) ---
            if st.button("⚠️ Trova Anomalie", use_container_width=True):
                st.session_state.messages.append({"role": "user",
                                                  "content": "Esegui un audit del processo e trova le principali anomalie o colli di bottiglia."})

                with st.spinner("Audit del processo in corso..."):
                    anom = llm_chatbot.detect_anomalies_llm(process_structure_text, gemini_file)
                    st.session_state.messages.append(
                        {"role": "assistant", "content": f"**Risultati Audit:**\n\n{anom}"})

            st.divider()

            # --- PREDITTORE ---
            st.subheader("🔮 Predittore")
            trace_in = st.text_input("Traccia parziale", placeholder="es. Start -> A...")
            if st.button("Prevedi Prossimo Step", use_container_width=True):
                if trace_in:
                    with st.spinner("Calcolo probabilità..."):
                        pred = llm_chatbot.predict_next_step(trace_in, process_structure_text, gemini_file)
                        st.info(pred)

        with c_chat:
            st.subheader("💬 Chat con l'analista AI")

            # Crea un contenitore con altezza fissa e scrollabile per i messaggi
            chat_container = st.container(height=600, border=True)

            with chat_container:
                # Disegna lo storico
                for msg in st.session_state.messages:
                    with st.chat_message(msg["role"]):
                        st.markdown(msg["content"])

            # L'input testuale resta ancorato al fondo
            if prompt := st.chat_input("Chiedi all'AI (es. 'Qual è il collo di bottiglia principale?')..."):
                # Aggiunge e mostra subito il messaggio testuale dell'utente
                st.session_state.messages.append({"role": "user", "content": prompt})
                with chat_container:
                    with st.chat_message("user"):
                        st.markdown(prompt)

                    # Mostra lo spinner e la risposta dell'AI all'interno del container
                    with st.chat_message("assistant"):
                        with st.spinner("Gemini sta elaborando..."):
                            resp = llm_chatbot.ask_llm(
                                prompt,
                                f"Modello selezionato: {selected}. DFG: {process_structure_text}",
                                gemini_file
                            )
                            st.markdown(resp)

                # Salva la risposta dell'AI
                st.session_state.messages.append({"role": "assistant", "content": resp})

else:
    st.info("👈 Carica i dati per iniziare.")