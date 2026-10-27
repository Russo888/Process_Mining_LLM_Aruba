"""Catalogo dei risultati locali e contesto della configurazione selezionata."""
import hashlib
import json
import math
import pickle
from datetime import datetime
from pathlib import Path

import pandas as pd
from evaluation import f1_score
from project_paths import DATA_DIR


def available_results(data_dir=DATA_DIR):
    """Trova solo pacchetti completi; i vecchi artefatti restano indipendenti."""
    root = Path(data_dir)
    catalog = {}
    experiments = root / "experiments"
    for run in sorted(experiments.glob("*"), reverse=True):
        if not run.is_dir():
            continue
        folder = run / "data"
        if all((folder / f).is_file() for f in ("dataset_aruba_attivita.csv", "models.pkl", "metrics.json")):
            try:
                stamp = datetime.strptime(run.name, "comparison_%Y%m%dT%H%M%S%fZ")
                label = f"Confronto {stamp:%d/%m/%Y %H:%M:%S} UTC"
            except ValueError:
                label = f"Confronto Colab · {run.name}"
            # Conserva distinti anche due run avviati nello stesso secondo.
            if label in catalog:
                label += f" ({run.name})"
            catalog[label] = folder
    if all((root / f).is_file() for f in ("dataset_aruba_attivita.csv", "models.pkl")):
        catalog["Risultati locali · pipeline principale"] = root
    return catalog


def load_result_bundle(folder):
    folder = Path(folder)
    df = pd.read_csv(folder / "dataset_aruba_attivita.csv")
    required = ["case:concept:name", "concept:name", "time:timestamp"]
    if not set(required).issubset(df.columns) or df.empty or df[required].isna().any().any():
        raise ValueError("Event log vuoto o con colonne PM4Py mancanti/non valide")
    df[required[2]] = pd.to_datetime(df[required[2]], format="ISO8601", errors="raise")
    df = df.sort_values(required[2], kind="stable").reset_index(drop=True)
    scores = json.loads((folder / "metrics.json").read_text(encoding="utf-8")) if (folder / "metrics.json").exists() else {}
    metadata = json.loads((folder / "evaluation_metadata.json").read_text(encoding="utf-8")) if (folder / "evaluation_metadata.json").exists() else {}
    if metadata:
        fingerprint = df[required].copy()
        fingerprint[required[2]] = fingerprint[required[2]].astype(str)
        digest = hashlib.sha256(fingerprint.to_csv(index=False, lineterminator="\n").encode()).hexdigest()
        if metadata.get("dataset_sha256") and metadata["dataset_sha256"] != digest:
            raise ValueError("Il CSV non corrisponde ai metadati della valutazione")
        digest = hashlib.sha256(json.dumps(scores, sort_keys=True).encode()).hexdigest()
        if metadata.get("metrics_sha256") and metadata["metrics_sha256"] != digest:
            raise ValueError("Le metriche non corrispondono ai metadati della valutazione")
    # Solo pacchetti locali installati dall'utente; gli upload mantengono il proprio flusso.
    with (folder / "models.pkl").open("rb") as handle:
        models = pickle.load(handle)
    if not isinstance(models, dict) or not models or not isinstance(scores, dict):
        raise ValueError("Pacchetto modelli/metriche non valido")
    result_file = folder.parent / "comparison_results.json"
    records = json.loads(result_file.read_text(encoding="utf-8")) if result_file.exists() else []
    diagnostics = {record["label"]: record for record in records}
    if any(name not in models for name in scores):
        raise ValueError("Le metriche contengono modelli assenti dal pacchetto")
    for name, record in diagnostics.items():
        if record.get("status") == "ok" and (record.get("metrics") != scores.get(name)
                or (metadata and record.get("evaluated_cases") != metadata.get("evaluated_cases"))):
            raise ValueError("Il confronto contiene metriche o campioni non coerenti")
    return df, models, scores, metadata, diagnostics


def best_models(scores):
    valid = {name: f1_score(values) for name, values in scores.items() if f1_score(values) is not None}
    if not valid:
        return []
    best = max(valid.values())
    return [name for name, value in valid.items() if math.isclose(value, best, rel_tol=1e-12, abs_tol=1e-12)]


def comparison_details(diagnostics):
    rows = []
    for name, r in diagnostics.items():
        execution = r.get("execution", {})
        rows.append({"Modello": name, "Stato": r.get("status"),
                     "Fitness": r.get("metrics", {}).get("fitness"),
                     "Precision": r.get("metrics", {}).get("precision"), "F1": r.get("f1"),
                     "Tracce fitting %": r.get("fit_traces_percent"),
                     "Tracce mescolate fitting %": r.get("shuffled_fit_traces_percent"),
                     "Fitness mescolata": r.get("shuffled_fitness"),
                     "Differenza ordine": r.get("order_fitness_gap"),
                     "Durata (min)": execution.get("seconds", 0) / 60,
                     "Etichette omesse": ", ".join(r.get("missing_log_labels", [])) or "Nessuna",
                     "Errore": r.get("error") or "—"})
    return pd.DataFrame(rows)


def selected_model_context(name, model, scores, diagnostics, metadata, source):
    content = {"esperimento": source, "modello_selezionato": name,
               "metriche_selezionate": scores.get(name, {}), "confronto_metriche": scores,
               "diagnostica_selezionata": diagnostics.get(name, {}),
               "valutazione": {k: metadata[k] for k in ("scope", "max_eval_cases", "evaluated_events", "seed") if k in metadata}}
    if isinstance(model, tuple) and len(model) == 3:
        net = model[0]
        content["rete_selezionata"] = {"posti": len(net.places), "transizioni": len(net.transitions),
                                      "archi": len(net.arcs), "etichette": sorted({t.label for t in net.transitions if t.label is not None})}
    return json.dumps(content, ensure_ascii=False, indent=2)
