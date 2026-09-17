import json
import os
import time
import tempfile
import pandas as pd
import random

try:
    import google.generativeai as genai
except ImportError:
    genai = None

# --- VARIABILI GLOBALI ---
client = None
MODEL_NAME = None
TEMPERATURE = None


def init_llm_from_config(config_path="config.json"):
    """
    Inizializza il client Gemini 2.0 leggendo dal config.
    """
    global client, MODEL_NAME, TEMPERATURE

    if not os.path.exists(config_path):
        return False

    try:
        with open(config_path, "r") as f:
            config = json.load(f)
            api_key = config.get("google_api_key") or config.get("openai_api_key")
            MODEL_NAME = config.get("model_name", "gemini-3.6-flash")
            TEMPERATURE = config.get("temperature", 0.7)

        if genai and api_key:
            genai.configure(api_key=api_key)
            client = genai.GenerativeModel(MODEL_NAME)
            return True

    except Exception as e:
        print(f"Errore caricamento config: {e}")
        return False


def smart_sample_dataframe(df, max_rows=15000):
    """
    Riduce il DataFrame mantenendo l'integrità dei casi (tracce).
    Se tagliamo righe a caso, rompiamo il processo. Dobbiamo filtrare per Case ID.
    Target: ~15.000 righe sono circa 200k-300k token, ben dentro il limite di 1M.
    """
    if len(df) <= max_rows:
        return df

    print(f"⚠️ Dataset troppo grande ({len(df)} righe). Avvio campionamento intelligente...")

    # Cerchiamo la colonna del Case ID (standard PM4PY o comuni)
    case_col = None
    candidates = ["case:concept:name", "Case ID", "case_id", "CASE_ID", "CaseId", "ID"]

    for col in candidates:
        if col in df.columns:
            case_col = col
            break

    if case_col:
        # Calcoliamo quanti casi possiamo tenere
        unique_cases = df[case_col].unique()
        avg_len = len(df) / len(unique_cases)
        n_cases_keep = int(max_rows / avg_len)

        # Prendiamo un campione casuale di casi per avere rappresentatività statistica
        # (Oppure i primi N se preferisci l'ordine cronologico, qui usiamo random per varietà)
        selected_cases = random.sample(list(unique_cases), min(n_cases_keep, len(unique_cases)))

        # Filtriamo il DF originale
        sampled_df = df[df[case_col].isin(selected_cases)].copy()
        print(f"✅ Ridotto a {len(sampled_df)} righe (Casi selezionati: {len(selected_cases)})")
        return sampled_df
    else:
        # Fallback: Se non troviamo il Case ID, tagliamo brutalmente le prime N righe
        print("⚠️ Colonna Case ID non trovata. Taglio sequenziale.")
        return df.head(max_rows)


def upload_csv_to_gemini(df):
    """
    Salva il DF (eventualmente campionato) e lo carica su Gemini.
    """
    if df is None or df.empty:
        return None

    try:
        # 1. Applicazione SMART SAMPLING per evitare errore 400 (Token Limit)
        # Limitiamo a 20.000 righe per stare sicuri sotto il milione di token.
        df_to_upload = smart_sample_dataframe(df, max_rows=20000)

        # 2. Creazione file temporaneo
        with tempfile.NamedTemporaryFile(delete=False, suffix='.csv', mode='w', encoding='utf-8') as tmp:
            df_to_upload.to_csv(tmp.name, index=False)
            tmp_path = tmp.name

        # 3. Upload su Google
        print(f"Caricamento su Gemini: {tmp_path}...")

        # FIX MIME TYPE: Forziamo 'text/csv' per Windows
        uploaded_file = genai.upload_file(
            path=tmp_path,
            display_name="Sampled_Process_Log",
            mime_type="text/csv"
        )

        os.remove(tmp_path)

        # 4. Attesa processing
        while uploaded_file.state.name == "PROCESSING":
            time.sleep(1)
            uploaded_file = genai.get_file(uploaded_file.name)

        if uploaded_file.state.name == "FAILED":
            raise ValueError("Google File API Failed.")

        print(f"File pronto: {uploaded_file.uri}")
        return uploaded_file

    except Exception as e:
        print(f"Errore upload file: {e}")
        return None


def get_completion_with_file(prompt, file_object=None, system_role="Sei un analista esperto di Process Mining."):
    if not client:
        return "⚠️ API Client non inizializzato."

    try:
        generation_config = genai.types.GenerationConfig(
            temperature=TEMPERATURE if TEMPERATURE is not None else 0.7
        )

        content_parts = [f"System Instruction: {system_role}\n"]

        if file_object:
            content_parts.append("Dati di riferimento (Campione rappresentativo del CSV):")
            content_parts.append(file_object)

        content_parts.append(f"\nUser Request: {prompt}")

        response = client.generate_content(
            content_parts,
            generation_config=generation_config
        )
        return response.text

    except Exception as e:
        return f"Errore API Gemini: {str(e)}"


# --- FUNZIONI CHIAMATE DA STREAMLIT ---

def ask_llm(question, context_text, file_object=None):
    prompt = f"Contesto Analitico: {context_text}\n\nDomanda: {question}"
    return get_completion_with_file(prompt, file_object)


def generate_process_analysis(context_text, file_object=None):
    prompt = (
        f"Analizza i log del processo allegati e genera un report.\n"
        f"Usa queste metriche: {context_text}\n"
        f"Nota: Il file CSV è un campione rappresentativo. Estrai trend generali."
    )
    return get_completion_with_file(prompt, file_object)


def detect_anomalies_llm(context_text, file_object=None):
    prompt = (
        f"Cerca anomalie e colli di bottiglia nel file CSV.\n"
        f"Modello ideale (DFG): {context_text}"
    )
    return get_completion_with_file(prompt, file_object, system_role="Esperto Audit.")


def predict_next_step(partial_trace, context_text, file_object=None):
    prompt = (
        f"Prevedi la prossima attività.\nTrace: {partial_trace}\nContext: {context_text}\n"
        f"Usa lo storico nel file per dedurre la probabilità."
    )
    return get_completion_with_file(prompt, file_object)