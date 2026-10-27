"""Campionamento riproducibile di tracce complete per il contesto LLM."""
import random


def smart_sample_dataframe(df, max_rows=20000, seed=42):
    if max_rows <= 0:
        raise ValueError("max_rows deve essere positivo")
    if len(df) <= max_rows:
        return df.copy()
    case_col = next((c for c in ["case:concept:name", "Case ID", "case_id"] if c in df), None)
    if case_col is None:
        raise ValueError("Manca la colonna Case ID: impossibile conservare le tracce")
    sizes = df.groupby(case_col, sort=False).size()
    cases = list(sizes.index)
    random.Random(seed).shuffle(cases)
    selected = []
    remaining = max_rows
    for case in cases:
        size = int(sizes[case])
        if size <= remaining:
            selected.append(case)
            remaining -= size
    if not selected:
        raise ValueError("Nessuna traccia completa rientra nel limite: aumentare max_rows")
    return df[df[case_col].isin(selected)].copy()


class AnalystActions:
    def ask_llm(self, question, context_text, data_ref=None):
        return self.complete(f"Contesto: {context_text}\nDomanda: {question}", data_ref)

    def generate_process_analysis(self, context_text, data_ref=None):
        return self.complete(f"Genera un report sul processo. Contesto: {context_text}", data_ref)

    def detect_anomalies_llm(self, context_text, data_ref=None):
        return self.complete(f"Individua possibili anomalie da verificare. DFG osservato (non modello ideale): {context_text}", data_ref)

    def predict_next_step(self, partial_trace, context_text, data_ref=None):
        return self.complete(f"Suggerisci la prossima zona dopo {partial_trace}. DFG: {context_text}. Non presentare probabilità come calibrate.", data_ref)


SYSTEM_ROLE = (
    "Sei un analista di Process Mining. Le etichette sono zone convenzionali associate "
    "ai sensori, non attività umane validate. Il contesto specifica se i dati sono "
    "statistiche aggregate sull’intero log oppure un campione di tracce complete. "
    "Non ricostruire sequenze individuali dai soli aggregati. "
    "Distingui osservazioni, ipotesi e limiti; non inventare dati, "
    "orari o probabilità. Il DFG descrive i flussi osservati, non una norma ideale."
)
