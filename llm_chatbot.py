"""Client Gemini isolato per sessione Streamlit (Google GenAI SDK)."""
import json
import math
import os
import re
from pathlib import Path
from llm_context import AnalystActions, SYSTEM_ROLE, smart_sample_dataframe
from project_paths import CONFIG_PATH

try:
    from google import genai
    from google.genai import types
except ImportError:
    genai = types = None


class GeminiEngine(AnalystActions):
    def __init__(self):
        self.client = None
        self.model_name = None
        self.temperature = 0.7
        self.last_error = ""

    def init_llm_from_config(self, config_path=CONFIG_PATH, api_key=None, model_name=None):
        self.client = None
        try:
            config = json.loads(Path(config_path).read_text(encoding="utf-8"))
            self.model_name = model_name or config.get("model_name", "gemini-3.6-flash")
            self.temperature = config.get("temperature", 0.7)
            key = api_key or os.getenv("GOOGLE_API_KEY") or config.get("google_api_key")
            if genai is None:
                raise RuntimeError("Installa google-genai tramite requirements.txt")
            if not key:
                raise ValueError("Inserisci una API key Gemini")
            self.client = genai.Client(api_key=key, http_options=types.HttpOptions(timeout=60000))
            self.last_error = ""
            return True
        except Exception as exc:
            self.last_error = str(exc)
            return False

    def upload_csv_to_gemini(self, df):
        # CSV testuale inline: evita file temporanei Windows, polling e upload persistenti.
        # Il nome del metodo resta compatibile con la dashboard.
        sample = smart_sample_dataframe(df, max_rows=1500)
        return (f"Campione di {len(sample)} eventi su {len(df)}, tracce complete.\n"
                + sample.to_csv(index=False))

    def complete(self, prompt, data_ref=None):
        self.last_error = ""
        if self.client is None:
            return "Client Gemini non configurato."
        try:
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt + (f"\nDati CSV:\n{data_ref}" if data_ref else ""),
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_ROLE, temperature=self.temperature),
            )
            return response.text or "Il modello non ha restituito testo."
        except Exception as exc:
            if getattr(exc, "code", None) == 429:
                self.last_error = "Gemini ha raggiunto la quota del progetto per questo modello."
                delay = re.search(r"retry in ([0-9]+(?:\.[0-9]+)?)s", str(exc), re.IGNORECASE)
                if delay:
                    self.last_error += f" Attendi almeno {math.ceil(float(delay[1]))} secondi prima di riprovare."
                self.last_error += " Puoi controllare il consumo in [Google AI Studio](https://ai.dev/rate-limit)."
            else:
                self.last_error = f"Errore API Gemini: {exc}"
            return self.last_error
