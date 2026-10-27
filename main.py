import pickle
import json
import os
from preprocessing import load_and_transform_dataset
from discovery import discover_models
from evaluation import evaluate_models_safe

from project_paths import (DATA_DIR, DATASET_PATH, OUTPUT_CSV, OUTPUT_MODELS,
                           OUTPUT_METRICS, EVALUATION_METADATA)

def main():
    print("=== Process Mining Pipeline ===")
    
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    # 1. ETL
    print(f"\n[1/4] Preprocessing dataset da: {DATASET_PATH}")
    if not os.path.exists(DATASET_PATH):
        print(f"ERRORE: Dataset non trovato in {DATASET_PATH}")
        raise FileNotFoundError(DATASET_PATH)

    df = load_and_transform_dataset(DATASET_PATH)
    
    # Salva CSV delle attività
    df.to_csv(OUTPUT_CSV, index=False)
    print(f"      Dataset salvato in: {OUTPUT_CSV}")
    
    # 2. Mining (Alpha, Heuristic, Inductive)
    print("\n[2/4] Discovery dei modelli...")
    models = discover_models(df)

    # 3. Export Modelli
    print("\n[3/4] Salvataggio modelli...")
    # Filtriamo eventuali errori prima di salvare
    
    with open(OUTPUT_MODELS, "wb") as f:
        pickle.dump(models, f) # Salviamo anche gli errori per mostrarli nella dashboard
    print(f"      Modelli salvati in: {OUTPUT_MODELS}")

    # 4. Valutazione
    print("\n[4/4] Valutazione modelli...")
    scores = evaluate_models_safe(df, models, metadata_path=EVALUATION_METADATA)
    
    with open(OUTPUT_METRICS, "w") as f:
        json.dump(scores, f, indent=4)
    print(f"      Metriche salvate in: {OUTPUT_METRICS}")

    print("\nDONE! Pipeline completata con successo.")

if __name__ == "__main__":
    main()
