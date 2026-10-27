"""Strumenti Colab: ETL in streaming e modelli esportabili alla dashboard.

Non modifica la pipeline locale né la semantica della mappa sensori corrente.
"""
import hashlib
import importlib.metadata
import json
import pickle
import platform
import shutil
from datetime import date, datetime
from pathlib import Path

import pandas as pd
import pm4py
from preprocessing import SENSOR_ACTIVITY_MAP, get_time_of_day

CASE, ACTIVITY, TIME = "case:concept:name", "concept:name", "time:timestamp"


def preprocess_raw_to_csv(source, destination, start_date=None, end_date=None):
    """Preprocessing del progetto in streaming: M/D, mappa, fasce e compressione.

    Entrambi gli stati sono mantenuti. Il raw deve essere cronologico;
    le date opzionali includono l'intera giornata iniziale/finale.
    """
    import csv
    from collections import Counter

    source, destination = Path(source), Path(destination)
    if source.resolve() == destination.resolve():
        raise ValueError("Ingresso e uscita devono essere file diversi")
    lower = date.fromisoformat(start_date) if start_date else None
    upper = date.fromisoformat(end_date) if end_date else None
    if lower and upper and lower > upper:
        raise ValueError("START_DATE deve precedere o coincidere con END_DATE")
    destination.parent.mkdir(parents=True, exist_ok=True)
    counts = {
        "lines": 0, "malformed_lines": 0, "excluded_non_motion_door": 0,
        "excluded_unmapped": 0, "invalid_timestamps": 0, "outside_date_range": 0,
        "mapped_events": 0, "written_events": 0,
    }
    unmapped, states, zones, periods = Counter(), Counter(), Counter(), Counter()
    cases = set()
    first_timestamp = final_timestamp = last_timestamp = None
    previous = None
    temporary = destination.with_suffix(".partial.csv")
    try:
        with source.open(encoding="utf-8-sig") as incoming, temporary.open("w", encoding="utf-8", newline="") as outgoing:
            writer = csv.writer(outgoing)
            writer.writerow([CASE, ACTIVITY, TIME])
            for line in incoming:
                counts["lines"] += 1
                parts = line.split()
                if len(parts) < 4:
                    counts["malformed_lines"] += 1
                    continue
                if not parts[2].startswith(("M", "D")):
                    counts["excluded_non_motion_door"] += 1
                    continue
                if parts[2] not in SENSOR_ACTIVITY_MAP:
                    counts["excluded_unmapped"] += 1
                    unmapped[parts[2]] += 1
                    continue
                try:
                    timestamp = datetime.fromisoformat(parts[0] + " " + parts[1])
                except ValueError:
                    counts["invalid_timestamps"] += 1
                    continue
                if last_timestamp is not None and timestamp < last_timestamp:
                    raise ValueError(f"Raw non cronologico alla riga {counts['lines']}: ordinare il file prima della compressione streaming")
                last_timestamp = timestamp
                if (lower and timestamp.date() < lower) or (upper and timestamp.date() > upper):
                    counts["outside_date_range"] += 1
                    continue
                first_timestamp = first_timestamp or timestamp
                final_timestamp = timestamp
                counts["mapped_events"] += 1
                states[parts[3]] += 1
                period = get_time_of_day(timestamp.hour)
                case = f"{timestamp.date()}_{period}"
                activity = SENSOR_ACTIVITY_MAP[parts[2]]
                if (case, activity) != previous:
                    writer.writerow([case, activity, timestamp.isoformat(sep=" ")])
                    counts["written_events"] += 1
                    zones[activity] += 1
                    periods[period] += 1
                    cases.add(case)
                    previous = (case, activity)
        if not counts["written_events"]:
            raise ValueError(f"Nessun evento utilizzabile nel raw o nella finestra selezionata. Contatori: {counts}")
        temporary.replace(destination)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise
    counts.update({
        "consecutive_duplicates_removed": counts["mapped_events"] - counts["written_events"],
        "cases": len(cases), "zones": len(zones),
        "first_input_event_in_window": first_timestamp.isoformat(sep=" "),
        "last_input_event_in_window": final_timestamp.isoformat(sep=" "),
        "requested_start_date": start_date, "requested_end_date": end_date,
        "states_before_compression": dict(sorted(states.items())),
        "unmapped_sensor_counts": dict(sorted(unmapped.items())),
        "events_by_zone": dict(sorted(zones.items())),
        "events_by_period": dict(sorted(periods.items())),
        "sensor_activity_map": dict(SENSOR_ACTIVITY_MAP),
        "case_definition": "date_plus_period_00_06_12_19_24",
        "state_filter": "all_states_as_in_local_project",
    })
    return counts


def load_event_log(path):
    # Carica solo le tre colonne necessarie. Il log derivato deve comunque stare in RAM.
    df = pd.read_csv(path, usecols=[CASE, ACTIVITY, TIME], dtype={CASE: "string", ACTIVITY: "string"})
    if df.empty or df[[CASE, ACTIVITY, TIME]].isna().any().any():
        raise ValueError("Event log vuoto o con colonne PM4Py mancanti/nulle")
    df[TIME] = pd.to_datetime(df[TIME], format="ISO8601", errors="raise")
    df = df.sort_values(TIME, kind="stable").reset_index(drop=True)
    # Condividi le stringhe ripetute senza utilizzare categorie incompatibili con alcune versioni PM4Py.
    for col in (CASE, ACTIVITY):
        codes, values = pd.factorize(df[col], sort=False)
        df[col] = values.astype(object).take(codes)
    return df[[CASE, ACTIVITY, TIME]]


def discover_one(df, miner="Inductive Miner", noise_threshold=0.2, dependency_threshold=0.5):
    common = dict(case_id_key=CASE, activity_key=ACTIVITY, timestamp_key=TIME)
    if miner == "Inductive Miner":
        model = pm4py.discover_petri_net_inductive(df, noise_threshold=noise_threshold, **common)
    elif miner == "Heuristic Miner":
        model = pm4py.discover_petri_net_heuristics(df, dependency_threshold=dependency_threshold, **common)
    elif miner == "Alpha Miner":
        model = pm4py.discover_petri_net_alpha(df, **common)
    else:
        raise ValueError(f"Miner non supportato: {miner}")
    return {miner: model}


def sha256_file(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def export_results(df, models, directory, source_path, settings, scores=None, evaluation_metadata=None):
    root = Path(directory)
    data = root / "data"
    data.mkdir(parents=True, exist_ok=True)
    df[[CASE, ACTIVITY, TIME]].to_csv(data / "dataset_aruba_attivita.csv", index=False)
    with (data / "models.pkl").open("wb") as handle:
        pickle.dump(models, handle, protocol=pickle.HIGHEST_PROTOCOL)
    (data / "metrics.json").write_text(json.dumps(scores or {}, indent=2), encoding="utf-8")
    if evaluation_metadata is not None:
        target = data / "evaluation_metadata.json"
        if Path(evaluation_metadata).resolve() != target.resolve():
            shutil.copyfile(evaluation_metadata, target)
    else:
        (data / "evaluation_metadata.json").unlink(missing_ok=True)
    for i, model in enumerate(models.values(), start=1):
        pm4py.write_pnml(*model, str(data / f"model_{i}.pnml"))
    versions = {name: importlib.metadata.version(name) for name in ["pm4py", "pandas", "numpy"]}
    manifest = {
        "python": platform.python_version(), "packages": versions,
        "source_name": Path(source_path).name, "source_sha256": sha256_file(source_path),
        "events": len(df), "cases": int(df[CASE].nunique()), "activities": int(df[ACTIVITY].nunique()),
        "settings": settings, "evaluation": "completed" if scores is not None else "not_run",
        "files_sha256": {str(p.relative_to(root)): sha256_file(p) for p in data.iterdir() if p.is_file()},
    }
    (root / "run_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    (root / "requirements_colab.txt").write_text(
        "".join(f"{name}=={version}\n" for name, version in versions.items()), encoding="utf-8")
    return root


def package_results(directory):
    directory = Path(directory)
    return Path(shutil.make_archive(str(directory), "zip", root_dir=directory))
