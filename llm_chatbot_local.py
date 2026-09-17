import json
import os

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

# --- VARIABILI GLOBALI ---
client = None
MODEL_NAME = None
TEMPERATURE = None


def init_llm_from_config(config_path="config.json"):
    """
    Inizializza la connessione a un server locale (es. Ollama) leggendo il config.
    """
    global client, MODEL_NAME, TEMPERATURE

    if not os.path.exists(config_path):
        return False

    try:
        with open(config_path, "r") as f:
            config = json.load(f)

            # Per i modelli locali, url è spesso http://localhost:11434/v1 (Ollama)
            base_url = config.get("local_base_url", "http://localhost:11434/v1")
            api_key = config.get("api_key", "local-mode")  # La key non serve in locale

            MODEL_NAME = config.get("local_model_name", "llama3.2")
            TEMPERATURE = config.get("temperature", 0.7)

        if OpenAI:
            client = OpenAI(base_url=base_url, api_key=api_key)
            return True

    except Exception as e:
        print(f"Errore caricamento config: {e}")
        return False


def prepare_csv_for_llm(df, max_rows=50):
    """
    Sostituisce l'upload di Gemini. I modelli locali hanno contesti più piccoli.
    Estrae un campione rappresentativo del DF convertito in testo CSV.
    """
    if df is None or df.empty:
        return ""

    # Prende un piccolo campione per dare all'AI la comprensione delle colonne
    # e del formato dati, senza far esplodere i token.
    sample_df = df.head(max_rows)
    return sample_df.to_csv(index=False)


def get_completion_local(prompt, csv_context="", system_role="Sei un analista esperto di Process Mining."):
    """
    Costruisce il messaggio e interroga il modello locale.
    """
    if not client:
        return "⚠️ API Client non inizializzato."

    try:
        # Costruiamo il prompt completo unendo i dati
        full_user_prompt = prompt
        if csv_context:
            full_user_prompt += f"\n\nEcco un campione dei log raw (CSV):\n{csv_context}"

        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": system_role},
                {"role": "user", "content": full_user_prompt}
            ],
            temperature=TEMPERATURE if TEMPERATURE is not None else 0.7
        )
        return response.choices[0].message.content

    except Exception as e:
        return f"Errore AI Locale: {str(e)}"


# --- FUNZIONI CHIAMATE DA STREAMLIT ---

def ask_llm(question, context_text, csv_context=""):
    prompt = f"Contesto Analitico Aggiuntivo:\n{context_text}\n\nDomanda: {question}"
    return get_completion_local(prompt, csv_context)


def generate_process_analysis(metrics_text, csv_context=""):
    prompt = (
        f"Analizza i dati del processo e genera un report dettagliato.\n"
        f"Usa queste metriche di conformità: {metrics_text}\n"
    )
    return get_completion_local(prompt, csv_context)


def detect_anomalies_llm(dfg_text, csv_context=""):
    prompt = (
        f"Cerca anomalie, deviazioni e colli di bottiglia.\n"
        f"Modello ideale (DFG):\n{dfg_text}"
    )
    return get_completion_local(prompt, csv_context, system_role="Sei un Esperto di Audit e Sicurezza dei Processi.")


def predict_next_step(partial_trace, dfg_text, csv_context=""):
    prompt = (
        f"OBIETTIVO: Prevedi la prossima attività.\n"
        f"Traccia attuale: {partial_trace}\n"
        f"Struttura Processo:\n{dfg_text}\n"
        f"Qual è il next-step logico?"
    )
    return get_completion_local(prompt, csv_context)