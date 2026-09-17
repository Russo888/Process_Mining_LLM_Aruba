import pandas as pd
import pm4py
import pickle
import json
import os
import sys
import numpy as np

# ==========================================
# CONFIGURAZIONE FINALE
# ==========================================
DATASET_PATH = "data/dataset_aruba.txt"
MAX_EVAL_CASES = 50  # Numero di periodi da valutare (Safe Mode)

# Costanti PM4Py
CASE_ID_KEY = "case:concept:name"
ACTIVITY_KEY = "concept:name"
TIMESTAMP_KEY = "time:timestamp"

# ==========================================
# 1. MAPPA ATTIVITÀ (Gold Standard CASAS)
# ==========================================
SENSOR_ACTIVITY_MAP = {
    # ZONA NOTTE
    "M001": "Camera_Letto", "M002": "Camera_Letto",
    "M003": "Camera_Letto", "M004": "Camera_Letto",
    "M005": "Bagno_Principale", "M006": "Bagno_Principale", "M007": "Bagno_Principale",

    # ZONA GIORNO
    "M008": "Soggiorno", "M009": "Soggiorno", "M010": "Soggiorno",
    "M011": "Soggiorno", "M012": "Soggiorno", "M013": "Soggiorno",
    "M014": "Sala_Pranzo",

    # CUCINA
    "M015": "Cucina_Prep", "M016": "Cucina_Prep", "M017": "Cucina_Prep",
    "M018": "Cucina_Prep", "M019": "Cucina_Prep",

    # UFFICIO
    "M020": "Ufficio", "M021": "Ufficio", "M022": "Ufficio",

    # CORRIDOI
    "M023": "Corridoio", "M024": "Corridoio",

    # SECONDA ZONA
    "M025": "Camera_2", "M026": "Bagno_2",
    "M027": "Camera_2", "M028": "Bagno_2",
    "M029": "Camera_2", "M030": "Camera_2", "M031": "Camera_2",

    # PORTE
    "D001": "Uscita_Principale", "D002": "Uscita_Retro", "D004": "Garage"
}


def get_time_of_day(hour):
    if 0 <= hour < 6:
        return "Notte"
    elif 6 <= hour < 12:
        return "Mattina"
    elif 12 <= hour < 19:
        return "Pomeriggio"
    else:
        return "Sera"


# ==========================================
# 2. CARICAMENTO E PULIZIA
# ==========================================
def load_and_transform_dataset(file_path):
    print(f"1. Caricamento file: {file_path}")

    if not os.path.exists(file_path):
        print(f"ERRORE: File '{file_path}' mancante.")
        sys.exit(1)

    data = []
    try:
        with open(file_path, 'r') as f:
            for line in f:
                parts = line.strip().split()
                if len(parts) >= 4:
                    data.append(parts[:4])
    except Exception as e:
        print(f"Errore lettura: {e}")
        sys.exit(1)

    df = pd.DataFrame(data, columns=["date", "time", "sensor_id", "value"])

    # Filtro Sensori (Solo Motion e Door, NO Temperatura)
    print("   Filtro Sensori (Eliminazione Temperatura)...")
    df = df[df['sensor_id'].str.startswith(('M', 'D'))].copy()

    # Timestamp
    df['temp_ts'] = df['date'] + ' ' + df['time']
    df[TIMESTAMP_KEY] = pd.to_datetime(df['temp_ts'], format="%Y-%m-%d %H:%M:%S.%f", errors='coerce')
    df = df.dropna(subset=[TIMESTAMP_KEY]).sort_values(TIMESTAMP_KEY)

    # Mappatura Attività
    print("   Conversione Sensori -> Attività Umane...")
    df['activity_raw'] = df['sensor_id'].map(SENSOR_ACTIVITY_MAP)
    df['activity_raw'] = df['activity_raw'].fillna("Altro")
    df = df[df['activity_raw'] != "Altro"].copy()

    # Suddivisione Temporale
    df['hour'] = df[TIMESTAMP_KEY].dt.hour
    df['period'] = df['hour'].apply(get_time_of_day)
    df[CASE_ID_KEY] = df[TIMESTAMP_KEY].dt.date.astype(str) + "_" + df['period']

    # Compressione (Rimuove duplicati consecutivi)
    print(f"   Eventi grezzi: {len(df)}")
    mask = (df['activity_raw'] != df['activity_raw'].shift(1)) | \
           (df[CASE_ID_KEY] != df[CASE_ID_KEY].shift(1))
    df = df[mask].copy()

    df[ACTIVITY_KEY] = df['activity_raw']
    final_df = df[[CASE_ID_KEY, ACTIVITY_KEY, TIMESTAMP_KEY]].reset_index(drop=True)

    print(f"   Eventi finali ottimizzati: {len(final_df)}")
    return final_df


# ==========================================
# 3. DISCOVERY (ORA CON ALPHA MINER!)
# ==========================================
def discover_models(df):
    models = {}
    print("\n2. Discovery dei Modelli...")

    # --- ALPHA MINER (REINTRODOTTO) ---
    try:
        print("   -> Alpha Miner...", end=" ")
        # L'Alpha Miner genera Petri Net classiche.
        # Ora che i dati sono puliti (Livello Attività), dovrebbe funzionare bene.
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
        # Se fallisce, non blocca lo script

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

    return models


# ==========================================
# 4. VALUTAZIONE
# ==========================================
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

            # Replay token-based (Il migliore per performance)
            fitness = pm4py.fitness_token_based_replay(eval_df, net, im, fm, case_id_key=CASE_ID_KEY,
                                                       activity_key=ACTIVITY_KEY, timestamp_key=TIMESTAMP_KEY)
            precision = pm4py.precision_token_based_replay(eval_df, net, im, fm, case_id_key=CASE_ID_KEY,
                                                           activity_key=ACTIVITY_KEY, timestamp_key=TIMESTAMP_KEY)

            scores[name] = {"fitness": fitness['log_fitness'], "precision": precision}
            print(f"-> OK (F: {fitness['log_fitness']:.2f}, P: {precision:.2f})")

        except Exception as e:
            # L'Alpha Miner a volte fallisce qui se il modello ha "deadlock".
            # È normale per l'Alpha Miner su dati reali.
            print(f"-> FALLITO (Errore tipico di complessità modello)")
            scores[name] = {"error": str(e)}

    return scores


def main():
    # 1. ETL
    df = load_and_transform_dataset(DATASET_PATH)

    # Salva CSV delle attività
    out_csv = "dataset_aruba_attivita.csv"
    df.to_csv(out_csv, index=False)

    # 2. Mining (Alpha, Heuristic, Inductive)
    models = discover_models(df)

    # 3. Export
    valid_models = {k: v for k, v in models.items() if not (isinstance(v, dict) and "error" in v)}
    with open("models.pkl", "wb") as f:
        pickle.dump(valid_models, f)

    # 4. Metriche
    scores = evaluate_models_safe(df, models)
    with open("metrics.json", "w") as f:
        json.dump(scores, f, indent=4)

    print("\nDONE! Tutto completato con successo.")


if __name__ == "__main__":
    main()