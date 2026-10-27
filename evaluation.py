import json
import math
from hashlib import sha256
import numpy as np
import pm4py
# Costanti PM4Py
CASE_ID_KEY = "case:concept:name"
ACTIVITY_KEY = "concept:name"
TIMESTAMP_KEY = "time:timestamp"
RANDOM_SEED = 42
MAX_EVAL_CASES = 50  # Numero di periodi da valutare (Safe Mode)

def evaluate(df, net, im, fm):
    """
    Valuta un singolo modello su un DataFrame (già convertito in log internamente da PM4Py se necessario).
    """
    try:
        # Replay token-based (Il migliore per performance)
        # Nota: PM4Py accetta DataFrame direttamente in molte funzioni recenti, 
        # ma assicuriamoci di passare le chiavi corrette.
        fitness = pm4py.fitness_token_based_replay(
            df, net, im, fm, 
            case_id_key=CASE_ID_KEY, 
            activity_key=ACTIVITY_KEY, 
            timestamp_key=TIMESTAMP_KEY
        )
        precision = pm4py.precision_token_based_replay(
            df, net, im, fm, 
            case_id_key=CASE_ID_KEY, 
            activity_key=ACTIVITY_KEY, 
            timestamp_key=TIMESTAMP_KEY
        )
        # Generalization e Simplicity potrebbero essere pesanti, li includiamo se richiesto o li omettiamo per velocità
        # Per ora manteniamo Fitness e Precision che sono i più critici.
        
        return {
            "fitness": fitness['log_fitness'], 
            "precision": precision
        }
    except Exception as e:
        return {"error": str(e)}

def evaluate_models_safe(df, models, metadata_path=None):
    print("\n3. Valutazione (Safe Mode)...")
    unique_cases = df[CASE_ID_KEY].unique()
    
    if len(unique_cases) > MAX_EVAL_CASES:
        sampled_cases = np.random.default_rng(RANDOM_SEED).choice(unique_cases, MAX_EVAL_CASES, replace=False)
        eval_df = df[df[CASE_ID_KEY].isin(sampled_cases)].copy()
        print(f"   Valutazione su campione di {MAX_EVAL_CASES} periodi.")
    else:
        eval_df = df
        print(f"   Valutazione su tutti i {len(unique_cases)} periodi.")

    if metadata_path is not None:
        import pandas as pd
        fingerprint_df = df[[CASE_ID_KEY, ACTIVITY_KEY, TIMESTAMP_KEY]].copy()
        fingerprint_df[TIMESTAMP_KEY] = pd.to_datetime(fingerprint_df[TIMESTAMP_KEY]).astype(str)
        metadata = {
            "seed": RANDOM_SEED,
            "max_eval_cases": MAX_EVAL_CASES,
            "total_cases": int(len(unique_cases)),
            "evaluated_cases": [str(c) for c in eval_df[CASE_ID_KEY].unique()],
            "evaluated_events": int(len(eval_df)),
            "dataset_sha256": sha256(fingerprint_df.to_csv(index=False).encode("utf-8")).hexdigest(),
            "pm4py_version": pm4py.__version__,
            "selection_criterion": "harmonic_mean_fitness_precision",
            "scope": "in_sample: modelli scoperti sull'intero log, valutati su un sottoinsieme"
        }

    scores = {}
    for name, model in models.items():
        if isinstance(model, dict) and "error" in model:
            scores[name] = model
            continue
        
        print(f"   Valutando {name}...", end=" ")
        try:
            net, im, fm = model
            res = evaluate(eval_df, net, im, fm)
            scores[name] = res
            
            if "error" not in res:
                print(f"-> OK (F: {res['fitness']:.2f}, P: {res['precision']:.2f})")
            else:
                print(f"-> FALLITO ({res['error']})")
                
        except Exception as e:
            print(f"-> FALLITO (Eccezione imprevista)")
            scores[name] = {"error": str(e)}
            
    if metadata_path is not None:
        metadata["metrics_sha256"] = sha256(json.dumps(scores, sort_keys=True).encode("utf-8")).hexdigest()
        with open(metadata_path, "w", encoding="utf-8") as handle:
            json.dump(metadata, handle, indent=2, ensure_ascii=False)
    return scores

def f1_score(metrics):
    """Media armonica di fitness e precision; rifiuta metriche incomplete/non valide."""
    if not isinstance(metrics, dict) or "error" in metrics:
        return None
    try:
        fitness = float(metrics["fitness"])
        precision = float(metrics["precision"])
    except (KeyError, TypeError, ValueError):
        return None
    if not all(math.isfinite(v) and 0 <= v <= 1 for v in (fitness, precision)):
        return None
    return 2 * fitness * precision / (fitness + precision) if fitness + precision else 0.0


def choose_best(results: dict):
    """Seleziona il modello con la maggiore media armonica fitness/precision."""
    valid = {name: m for name, m in results.items() if f1_score(m) is not None}
    if not valid:
        return None, None
    name = max(valid, key=lambda key: f1_score(valid[key]))
    return name, valid[name]


def choose_best_model_internal(scores):
    """Alias compatibile per la dashboard; stesso criterio di choose_best."""
    return choose_best(scores)[0]
