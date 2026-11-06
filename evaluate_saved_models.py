"""Completa le dimensioni di qualità senza riscoprire o modificare i modelli."""
import argparse
import hashlib
import json
import math
import pickle
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import pm4py
from colab_pipeline import load_event_log, CASE, ACTIVITY, TIME, sha256_file
from evaluation import evaluate_additional_dimensions
from project_paths import DATA_DIR


def complete_saved_evaluation(experiment):
    root = Path(experiment)
    data = root / "data"
    metadata = json.loads((data / "evaluation_metadata.json").read_text(encoding="utf-8"))
    original = json.loads((data / "metrics.json").read_text(encoding="utf-8"))
    df = load_event_log(data / "dataset_aruba_attivita.csv")
    fingerprint = df[[CASE, ACTIVITY, TIME]].copy()
    fingerprint[TIME] = fingerprint[TIME].astype(str)
    digest = hashlib.sha256(fingerprint.to_csv(index=False, lineterminator="\n").encode()).hexdigest()
    if digest != metadata["dataset_sha256"]:
        raise ValueError("Il dataset non corrisponde alla valutazione originale")
    cases = metadata["evaluated_cases"]
    sample = df[df[CASE].isin(cases)].copy()
    if set(sample[CASE]) != set(cases) or len(sample) != metadata["evaluated_events"]:
        raise ValueError("Campione diverso dalla valutazione originale")
    # Solo artefatti locali fidati prodotti e verificati dal progetto.
    with (data / "models.pkl").open("rb") as handle:
        models = pickle.load(handle)
    rows = []
    for name, model in models.items():
        if name not in original or "error" in original[name]:
            raise ValueError(f"Metriche originali mancanti: {name}")
        extra = evaluate_additional_dimensions(sample, *model)
        if not all(math.isfinite(v) and 0 <= v <= 1 for v in extra.values()):
            raise ValueError(f"Metriche non valide: {name}")
        rows.append({"model": name, **original[name], **extra})
        print(name, extra, flush=True)
    result = {
        "computed_at_utc": datetime.now(timezone.utc).isoformat(),
        "pm4py_version": pm4py.__version__, "pandas_version": pd.__version__,
        "models_sha256": sha256_file(data / "models.pkl"),
        "original_metrics_sha256": sha256_file(data / "metrics.json"),
        "dataset_sha256": digest, "evaluated_cases": cases,
        "evaluated_events": len(sample),
        "methods": {"simplicity": "PM4Py SIMPLICITY_ARC_DEGREE (default k=2)",
                    "generalization": "PM4Py GENERALIZATION_TOKEN"},
        "scope": "Original in-sample cases. Fitness/precision copied unchanged; no discovery. Generalization is not held-out predictive performance.",
        "results": rows,
    }
    (root / "quality_metrics.json").write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    pd.DataFrame(rows).to_csv(root / "quality_metrics.csv", index=False)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--experiment", type=Path, default=DATA_DIR / "experiments/comparison_20261023T213310299553Z")
    complete_saved_evaluation(parser.parse_args().experiment)
