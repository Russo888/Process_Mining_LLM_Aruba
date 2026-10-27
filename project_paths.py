"""Percorsi indipendenti dalla directory di avvio."""
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent
DATA_DIR = PROJECT_DIR / "data"
CONFIG_PATH = PROJECT_DIR / "config.json"
DATASET_PATH = DATA_DIR / "aruba.20111101-20111128_20260218.180945.txt"
OUTPUT_CSV = DATA_DIR / "dataset_aruba_attivita.csv"
OUTPUT_MODELS = DATA_DIR / "models.pkl"
OUTPUT_METRICS = DATA_DIR / "metrics.json"
EVALUATION_METADATA = DATA_DIR / "evaluation_metadata.json"
