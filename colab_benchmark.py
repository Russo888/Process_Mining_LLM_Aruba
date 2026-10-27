"""Confronti PM4Py isolati, sullo stesso log e sugli stessi casi in-sample."""
import gc
import hashlib
import importlib.metadata
import json
import os
import pickle
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
import pm4py
from colab_pipeline import CASE, ACTIVITY, TIME, load_event_log, discover_one, sha256_file
from evaluation import f1_score

DEFAULT_CONFIGS = [
    {"id": "inductive_020", "label": "Inductive noise=0.20 (riferimento)", "miner": "Inductive Miner", "parameters": {"noise_threshold": .2}},
    {"id": "inductive_000", "label": "Inductive noise=0.00", "miner": "Inductive Miner", "parameters": {"noise_threshold": .0}},
    {"id": "inductive_010", "label": "Inductive noise=0.10", "miner": "Inductive Miner", "parameters": {"noise_threshold": .1}},
    {"id": "heuristic_030", "label": "Heuristic dependency=0.30", "miner": "Heuristic Miner", "parameters": {"dependency_threshold": .3}},
    {"id": "heuristic_050", "label": "Heuristic dependency=0.50", "miner": "Heuristic Miner", "parameters": {"dependency_threshold": .5}},
    {"id": "heuristic_010", "label": "Heuristic dependency=0.10", "miner": "Heuristic Miner", "parameters": {"dependency_threshold": .1}},
    {"id": "alpha", "label": "Alpha Miner", "miner": "Alpha Miner", "parameters": {}},
]


def write_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2, ensure_ascii=False), encoding="utf-8")


def prepare_evaluation(csv_path, output_path, max_cases=20, seed=42):
    if max_cases < 1:
        raise ValueError("max_cases deve essere positivo")
    df = load_event_log(csv_path)
    cases = df[CASE].unique()
    selected = np.random.default_rng(seed).choice(cases, max_cases, replace=False) if len(cases) > max_cases else cases
    sample = df[df[CASE].isin(selected)].copy()
    sample.to_csv(output_path, index=False, lineterminator="\n")
    fingerprint = df[[CASE, ACTIVITY, TIME]].copy()
    fingerprint[TIME] = fingerprint[TIME].astype(str)
    digest = hashlib.sha256(fingerprint.to_csv(index=False, lineterminator="\n").encode()).hexdigest()
    metadata = {
        "seed": seed, "max_eval_cases": max_cases, "total_cases": int(len(cases)),
        "evaluated_cases": sample[CASE].unique().tolist(), "evaluated_events": len(sample),
        "dataset_sha256": digest, "pm4py_version": pm4py.__version__,
        "selection_criterion": "harmonic_mean_fitness_precision",
        "scope": "in_sample: stesso log di discovery, stessi casi e seed per tutti i candidati",
    }
    del fingerprint, sample, df
    gc.collect()
    return metadata


def worker(spec_path):
    spec = json.loads(Path(spec_path).read_text(encoding="utf-8"))
    directory = Path(spec["directory"])
    config = spec["config"]
    started = time.monotonic()
    try:
        df = load_event_log(spec["full_csv"])
        log_labels = set(df[ACTIVITY])
        model = discover_one(df, miner=config["miner"], **config["parameters"])[config["miner"]]
        # Salva prima della valutazione: resta recuperabile se precision esaurisce le risorse.
        with (directory / "models.pkl").open("wb") as handle:
            pickle.dump({config["label"]: model}, handle, protocol=pickle.HIGHEST_PROTOCOL)
        pm4py.write_pnml(*model, str(directory / "model.pnml"))
        if spec.get("checkpoint_dir"):
            checkpoint = Path(spec["checkpoint_dir"])
            checkpoint.mkdir(parents=True, exist_ok=True)
            shutil.copy2(directory / "models.pkl", checkpoint / "models.pkl")
            shutil.copy2(directory / "model.pnml", checkpoint / "model.pnml")
            write_json(checkpoint / "discovery.json", {"stage": "discovery_completed", "config": config})
        del df
        gc.collect()
        sample = load_event_log(spec["evaluation_csv"])
        fitness = pm4py.fitness_token_based_replay(sample, *model)
        precision = pm4py.precision_token_based_replay(sample, *model)
        metrics = {"fitness": float(fitness["log_fitness"]), "precision": float(precision)}
        shuffled = sample[[CASE, ACTIVITY, TIME]].copy()
        rng = np.random.default_rng(spec["seed"])
        for _, group in shuffled.groupby(CASE, sort=False):
            shuffled.loc[group.index, ACTIVITY] = rng.permutation(group[ACTIVITY].to_numpy())
        shuffled_fitness = pm4py.fitness_token_based_replay(shuffled, *model)
        net = model[0]
        visible = {t.label for t in net.transitions if t.label is not None}
        result = {
            "status": "ok", "id": config["id"], "label": config["label"],
            "metrics": metrics, "f1": f1_score(metrics),
            "fit_traces_percent": fitness["percentage_of_fitting_traces"],
            "shuffled_fitness": shuffled_fitness["log_fitness"],
            "shuffled_fit_traces_percent": shuffled_fitness["percentage_of_fitting_traces"],
            "order_fitness_gap": fitness["log_fitness"] - shuffled_fitness["log_fitness"],
            "places": len(net.places), "transitions": len(net.transitions), "arcs": len(net.arcs),
            "silent_transitions": sum(t.label is None for t in net.transitions),
            "missing_log_labels": sorted(log_labels - visible),
            "evaluated_cases": sample[CASE].unique().tolist(),
            "seconds": time.monotonic() - started,
        }
        write_json(directory / "result.json", result)
        return 0
    except Exception as exc:
        write_json(directory / "result.json", {"status": "error", "id": config["id"],
                   "label": config["label"], "error": f"{type(exc).__name__}: {exc}",
                   "seconds": time.monotonic() - started})
        return 1


def process_rss(pid):
    import psutil
    try:
        process = psutil.Process(pid)
        return process.memory_info().rss + sum(p.memory_info().rss for p in process.children(recursive=True))
    except psutil.NoSuchProcess:
        return 0


def monitor_worker(command, log_path, timeout_seconds, max_memory_gb):
    """Limiti osservati ogni 0,5 s: riducono il rischio, non garantiscono contro picchi OOM."""
    started = time.monotonic()
    peak = 0
    status = None
    env = dict(os.environ, OMP_NUM_THREADS="1", OPENBLAS_NUM_THREADS="1")
    flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    with Path(log_path).open("w", encoding="utf-8") as log:
        with subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT, env=env,
                              creationflags=flags) as process:
            try:
                while process.poll() is None:
                    if time.monotonic() - started > timeout_seconds:
                        status = "timeout"
                        break
                    if max_memory_gb is not None:
                        peak = max(peak, process_rss(process.pid))
                        if peak > max_memory_gb * 2**30:
                            status = "memory_limit"
                            break
                    time.sleep(.5)
            finally:
                if process.poll() is None:
                    process.kill()
                process.wait()
    return {"status": status or ("finished" if process.returncode == 0 else "worker_error"),
            "returncode": process.returncode, "peak_worker_gb": peak / 2**30,
            "seconds": time.monotonic() - started}


def validate_configs(configs):
    if not configs:
        raise ValueError("Scegli almeno un candidato")
    if len({c["id"] for c in configs}) != len(configs) or len({c["label"] for c in configs}) != len(configs):
        raise ValueError("ID ed etichette devono essere unici")
    for c in configs:
        if not re.fullmatch(r"[a-z0-9_-]+", c["id"]):
            raise ValueError("ID candidato non valido")
        allowed = {"Inductive Miner": {"noise_threshold"}, "Heuristic Miner": {"dependency_threshold"},
                   "Alpha Miner": set()}
        if c["miner"] not in allowed or set(c["parameters"]) != allowed[c["miner"]]:
            raise ValueError("Algoritmo o parametri non supportati nel confronto")
        if not all(isinstance(v, (int, float)) and 0 <= v <= 1 for v in c["parameters"].values()):
            raise ValueError("Le soglie devono essere numeri fra 0 e 1")


def save_checkpoint(root, results, configs, metadata, backup_dir=None):
    models, scores = {}, {}
    for config in configs:
        directory = root / "candidates" / config["id"]
        if (directory / "models.pkl").exists():
            with (directory / "models.pkl").open("rb") as handle:
                models.update(pickle.load(handle))
        result = next((r for r in results if r["id"] == config["id"]), None)
        if result is not None:
            scores[config["label"]] = result["metrics"] if result["status"] == "ok" else {"error": result.get("error", result["status"])}
    with (root / "data/models.pkl").open("wb") as handle:
        pickle.dump(models, handle, protocol=pickle.HIGHEST_PROTOCOL)
    write_json(root / "data/metrics.json", scores)
    eval_metadata = dict(metadata)
    eval_metadata["metrics_sha256"] = hashlib.sha256(json.dumps(scores, sort_keys=True).encode()).hexdigest()
    write_json(root / "data/evaluation_metadata.json", eval_metadata)
    write_json(root / "comparison_results.json", results)
    valid = [r for r in results if r["status"] == "ok" and r.get("f1") is not None]
    winner = max(valid, key=lambda r: r["f1"])["label"] if valid else None
    write_json(root / "comparison_manifest.json", {
        "configs": configs, "completed": len(results), "planned": len(configs),
        "packages": {name: importlib.metadata.version(name) for name in ["pm4py", "pandas", "numpy"]},
        "first_by_in_sample_f1": winner, "dataset_csv_sha256": sha256_file(root / "data/dataset_aruba_attivita.csv"),
        "evaluation": eval_metadata,
        "note": "Classifica in-sample: non dimostra generalizzazione. Controllare anche precision e sequenze permutate.",
    })
    (root / "requirements_colab.txt").write_text("".join(f"{name}=={importlib.metadata.version(name)}\n" for name in ["pm4py", "pandas", "numpy"]), encoding="utf-8")
    rows = [{"Modello": r["label"], "Stato": r["status"],
             "Fitness": r.get("metrics", {}).get("fitness"), "Precision": r.get("metrics", {}).get("precision"),
             "F1": r.get("f1"), "Tracce fitting %": r.get("fit_traces_percent"),
             "Fitness mescolata": r.get("shuffled_fitness"), "Differenza ordine": r.get("order_fitness_gap"),
             "Etichette omesse": ", ".join(r.get("missing_log_labels", [])), "Errore": r.get("error", "")}
            for r in results]
    pd.DataFrame(rows).to_csv(root / "comparison.csv", index=False)
    if backup_dir is not None:
        shutil.copytree(root, backup_dir, dirs_exist_ok=True)
    del models
    gc.collect()


def run_comparison(csv_path, output_dir, configs=None, max_eval_cases=20, seed=42,
                   timeout_seconds=600, max_memory_gb=4, backup_dir=None):
    configs = DEFAULT_CONFIGS if configs is None else configs
    validate_configs(configs)
    if timeout_seconds <= 0 or (max_memory_gb is not None and max_memory_gb <= 0):
        raise ValueError("Limiti di tempo e memoria non validi")
    if max_memory_gb is not None:
        process_rss(os.getpid())  # Richiede psutil, installato dal notebook.
    root = Path(output_dir).resolve()
    if backup_dir is not None:
        backup_dir = Path(backup_dir).resolve()
        if root == backup_dir or root in backup_dir.parents or backup_dir in root.parents:
            raise ValueError("Output e backup devono essere cartelle separate, non annidate")
    root.mkdir(parents=True, exist_ok=False)
    (root / "data").mkdir()
    (root / "candidates").mkdir()
    full_csv = root / "data/dataset_aruba_attivita.csv"
    shutil.copyfile(csv_path, full_csv)
    eval_csv = root / "evaluation_log.csv"
    metadata = prepare_evaluation(full_csv, eval_csv, max_cases=max_eval_cases, seed=seed)
    results = []
    save_checkpoint(root, results, configs, metadata, backup_dir)
    for config in configs:
        print(f"Avvio {config['label']} (timeout {timeout_seconds}s, RAM worker {max_memory_gb} GiB)", flush=True)
        directory = root / "candidates" / config["id"]
        directory.mkdir()
        spec = {"full_csv": str(full_csv), "evaluation_csv": str(eval_csv),
                "directory": str(directory), "config": config, "seed": seed,
                "checkpoint_dir": str(backup_dir / "candidates" / config["id"]) if backup_dir else None}
        write_json(directory / "spec.json", spec)
        execution = monitor_worker([sys.executable, str(Path(__file__).resolve()), "--worker", str(directory / "spec.json")],
                                   directory / "worker.log", timeout_seconds, max_memory_gb)
        result_path = directory / "result.json"
        if execution["status"] == "finished" and result_path.exists():
            result = json.loads(result_path.read_text(encoding="utf-8"))
        elif execution["status"] == "worker_error" and result_path.exists():
            result = json.loads(result_path.read_text(encoding="utf-8"))
        else:
            result = {"id": config["id"], "label": config["label"], "status": execution["status"],
                      "error": "Limite tempo/RAM o arresto del worker; consultare worker.log"}
        result["execution"] = execution
        results.append(result)
        save_checkpoint(root, results, configs, metadata, backup_dir)
        print(f"  -> {result['status']}; F1={result.get('f1')}; backup aggiornato", flush=True)
    return pd.read_csv(root / "comparison.csv")


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--worker":
        raise SystemExit(worker(sys.argv[2]))
    raise SystemExit("Usare run_comparison dal notebook")
