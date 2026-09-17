import pm4py
from pm4py.algo.discovery.alpha import algorithm as alpha_miner
from pm4py.algo.discovery.heuristics import algorithm as heuristic_miner
from pm4py.algo.discovery.inductive import algorithm as inductive_miner
from pm4py.objects.conversion.process_tree import converter as pt_converter

# Costanti PM4Py (devono corrispondere a quelle usate in preprocessing)
CASE_ID_KEY = "case:concept:name"
ACTIVITY_KEY = "concept:name"
TIMESTAMP_KEY = "time:timestamp"

def discover_models(df):
    """
    Applica tre algoritmi di discovery sul DataFrame formattato:
    - Alpha Miner
    - Heuristic Miner
    - Inductive Miner
    
    Ritorna un dizionario: { "Nome Modello": (net, im, fm) }
    """
    models = {}
    print("\n2. Discovery dei Modelli...")

    # --- ALPHA MINER ---
    try:
        print("   -> Alpha Miner...", end=" ")
        # L'Alpha Miner genera Petri Net classiche.
        net, im, fm = pm4py.discover_petri_net_alpha(
            df, 
            case_id_key=CASE_ID_KEY, 
            activity_key=ACTIVITY_KEY, 
            timestamp_key=TIMESTAMP_KEY
        )
        models["Alpha Miner"] = (net, im, fm)
        print("OK")
    except Exception as e:
        print(f"Errore: {e}")
        models["Alpha Miner"] = {"error": str(e)}

    # --- HEURISTIC MINER ---
    try:
        print("   -> Heuristic Miner...", end=" ")
        net, im, fm = pm4py.discover_petri_net_heuristics(
            df, dependency_threshold=0.5, 
            case_id_key=CASE_ID_KEY, activity_key=ACTIVITY_KEY, timestamp_key=TIMESTAMP_KEY
        )
        models["Heuristic Miner"] = (net, im, fm)
        print("OK")
    except Exception as e:
        print(f"Errore: {e}")
        models["Heuristic Miner"] = {"error": str(e)}

    # --- INDUCTIVE MINER ---
    try:
        print("   -> Inductive Miner...", end=" ")
        net, im, fm = pm4py.discover_petri_net_inductive(
            df, noise_threshold=0.2, 
            case_id_key=CASE_ID_KEY, activity_key=ACTIVITY_KEY, timestamp_key=TIMESTAMP_KEY
        )
        models["Inductive Miner"] = (net, im, fm)
        print("OK")
    except Exception as e:
        print(f"Errore: {e}")
        models["Inductive Miner"] = {"error": str(e)}

    return models
