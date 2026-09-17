import pandas as pd
import os
import sys
import pm4py

# ==========================================
# CONFIGURAZIONE COSTANTI
# ==========================================
CASE_ID_KEY = "case:concept:name"
ACTIVITY_KEY = "concept:name"
TIMESTAMP_KEY = "time:timestamp"

# ==========================================
# 1. MAPPA ATTIVITÀ
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
    if 0 <= hour < 6: return "Notte"
    elif 6 <= hour < 12: return "Mattina"
    elif 12 <= hour < 19: return "Pomeriggio"
    else: return "Sera"

# ==========================================
# 2. CARICAMENTO E PULIZIA
# ==========================================
def load_and_transform_dataset(file_path):
    print(f"1. Caricamento file: {file_path}")
    
    if not os.path.exists(file_path):
        print(f"ERRORE: File '{file_path}' mancante.")
        # Invece di sys.exit, solleviamo un'eccezione per essere più pythonic in un modulo
        raise FileNotFoundError(f"File '{file_path}' mancante.")

    data = []
    try:
        with open(file_path, 'r') as f:
            for line in f:
                parts = line.strip().split()
                if len(parts) >= 4:
                    data.append(parts[:4])
    except Exception as e:
        print(f"Errore lettura: {e}")
        raise e

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
    # Mantieni colonne utili
    final_df = df[[CASE_ID_KEY, ACTIVITY_KEY, TIMESTAMP_KEY]].reset_index(drop=True)
    
    print(f"   Eventi finali ottimizzati: {len(final_df)}")
    return final_df

def extract_process_structure(df):
    """
    Estrae il DFG e le varianti.
    """
    if df is None or df.empty:
        return "Nessun dato disponibile."
    try:
        # 1. DFG
        dfg, start_activities, end_activities = pm4py.discover_dfg(df)
        sorted_dfg = sorted(dfg.items(), key=lambda x: x[1], reverse=True)

        structure_str = "--- STRUTTURA DEL PROCESSO (DFG) ---\n"
        structure_str += f"Start: {list(start_activities.keys())}\nEnd: {list(end_activities.keys())}\n"
        structure_str += "FLUSSI PRINCIPALI (A -> B [Freq]):\n"
        for (act_from, act_to), count in sorted_dfg[:30]:
            structure_str += f"- {act_from} -> {act_to} [{count}]\n"

        # 2. Varianti (con fix robustezza)
        variants = pm4py.get_variants_as_tuples(df)

        def get_count(val):
            return val if isinstance(val, int) else len(val)

        sorted_variants = sorted(variants.items(), key=lambda x: get_count(x[1]), reverse=True)

        structure_str += "\n--- VARIANTI TOP 5 ---\n"
        for path, val in sorted_variants[:5]:
            count = get_count(val)
            path_str = " -> ".join(path)
            structure_str += f"- ({count} casi): {path_str}\n"

        return structure_str
    except Exception as e:
        return f"Errore estrazione struttura: {str(e)}"
