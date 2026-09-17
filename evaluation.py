import numpy as np
import pm4py
from pm4py.algo.evaluation.replay_fitness import algorithm as fitness_evaluator
from pm4py.algo.evaluation.precision import algorithm as precision_evaluator
from pm4py.algo.evaluation.generalization import algorithm as generalization_evaluator
from pm4py.algo.evaluation.simplicity import algorithm as simplicity_evaluator

# Costanti PM4Py
CASE_ID_KEY = "case:concept:name"
ACTIVITY_KEY = "concept:name"
TIMESTAMP_KEY = "time:timestamp"
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

def evaluate_models_safe(df, models):
    print("\n3. Valutazione (Safe Mode)...")
    unique_cases = df[CASE_ID_KEY].unique()
    
    if len(unique_cases) > MAX_EVAL_CASES:
        sampled_cases = np.random.choice(unique_cases, MAX_EVAL_CASES, replace=False)
        eval_df = df[df[CASE_ID_KEY].isin(sampled_cases)].copy()
        print(f"   Valutazione su campione di {MAX_EVAL_CASES} periodi.")
    else:
        eval_df = df
        print(f"   Valutazione su tutti i {len(unique_cases)} periodi.")

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
            
    return scores

def choose_best(results: dict):
    """
    Seleziona il miglior modello basandosi sulla somma delle metriche (Fitness + Precision).
    """
    valid = {}
    for name, metrics in results.items():
        if not isinstance(metrics, dict):
            continue
        if "error" in metrics:
            continue
        
        # Verifica che fitness e precision siano presenti
        if "fitness" in metrics and "precision" in metrics:
            valid[name] = metrics

    if not valid:
        return None, None

    # Scegli il modello con il punteggio totale più alto (Fitness + Precision)
    best_name = max(
        valid,
        key=lambda k: valid[k]["fitness"] + valid[k]["precision"]
    )
    
    return best_name, valid[best_name]

def choose_best_model_internal(scores):
    """Sceglie il modello migliore basandosi sull'F1 Score."""
    best_name = None
    best_f1 = -1
    for name, metrics in scores.items():
        if isinstance(metrics, dict) and "error" not in metrics:
            fit = metrics.get("fitness", 0)
            prec = metrics.get("precision", 0)
            f1 = 2 * (fit * prec) / (fit + prec) if (fit + prec) > 0 else 0
            if f1 > best_f1:
                best_f1 = f1
                best_name = name
    return best_name
