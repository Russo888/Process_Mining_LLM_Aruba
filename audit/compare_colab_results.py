"""Verifica nuovi artefatti Colab, senza modificare i risultati della pipeline."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import hashlib
import json
import pickle
from collections import Counter
import numpy as np
import pandas as pd
import pm4py
from project_paths import OUTPUT_CSV, OUTPUT_MODELS, OUTPUT_METRICS, EVALUATION_METADATA, DATASET_PATH
from evaluation import f1_score

C,A,T = "case:concept:name", "concept:name", "time:timestamp"
df=pd.read_csv(OUTPUT_CSV, usecols=[C,A,T])
df[T]=pd.to_datetime(df[T],format="ISO8601")
scores=json.loads(OUTPUT_METRICS.read_text(encoding="utf-8"))
meta=json.loads(EVALUATION_METADATA.read_text(encoding="utf-8"))
fingerprint=df[[C,A,T]].copy()
fingerprint[T]=pd.to_datetime(fingerprint[T]).astype(str)
actual_hash=hashlib.sha256(fingerprint.to_csv(index=False,lineterminator="\n").encode("utf-8")).hexdigest()
metric_hash=hashlib.sha256(json.dumps(scores,sort_keys=True).encode("utf-8")).hexdigest()
selected=df[df[C].isin(meta["evaluated_cases"])].copy()
with OUTPUT_MODELS.open("rb") as f: models=pickle.load(f)
model=models["Inductive Miner"]
net,im,fm=model
fitness=pm4py.fitness_token_based_replay(selected,*model)
shuffled=selected.copy()
rng=np.random.default_rng(42)
for _,group in shuffled.groupby(C,sort=False):
    shuffled.loc[group.index,A]=rng.permutation(group[A].to_numpy())
random_fitness=pm4py.fitness_token_based_replay(shuffled,*model)
lengths=df.groupby(C,sort=False).size()
variants=df.groupby(C,sort=False)[A].agg(tuple).value_counts()
old={"fitness":0.9978118074392874,"precision":0.1548791832645564}
new=scores["Inductive Miner"]
labels=sorted({t.label for t in net.transitions if t.label is not None})
raw_first=raw_last=None
raw_days=Counter()
with DATASET_PATH.open(encoding="utf-8-sig") as f:
    for line in f:
        parts=line.split()
        if len(parts)>=4:
            raw_days[parts[0]] += 1
            if raw_first is None: raw_first=parts[:4]
            raw_last=parts[:4]
missing=pd.date_range(df[T].min().normalize(),df[T].max().normalize()).difference(pd.DatetimeIndex(df[T].dt.normalize().unique()))
try:
    tree_text=str(pm4py.convert_to_process_tree(*model))
except Exception as exc:
    tree_text="Conversione non disponibile: "+str(exc)
report={
 "events":len(df),"cases":int(df[C].nunique()),"zones":int(df[A].nunique()),
 "start":str(df[T].min()),"end":str(df[T].max()),
 "calendar_days_with_events":int(df[T].dt.normalize().nunique()),
 "csv_sorted":bool(df[T].is_monotonic_increasing),
 "nulls":{k:int(v) for k,v in df.isna().sum().to_dict().items()},
 "metadata_dataset_hash_matches":actual_hash==meta["dataset_sha256"],
 "metadata_metrics_hash_matches":metric_hash==meta["metrics_sha256"],
 "metadata_total_cases_matches":df[C].nunique()==meta["total_cases"],
 "all_evaluated_cases_exist":set(meta["evaluated_cases"]).issubset(set(df[C])),
 "evaluated_cases":int(selected[C].nunique()),"evaluated_events":len(selected),
 "metadata_evaluated_events_matches":len(selected)==meta["evaluated_events"],
 "metrics_fitness_matches_replay":bool(np.isclose(fitness['log_fitness'],new['fitness'])),
 "local_pm4py_version":pm4py.__version__,"colab_pm4py_version":meta["pm4py_version"],
 "old":{"fitness":old["fitness"],"precision":old["precision"],"f1":f1_score(old),"evaluation_cases":50,"events":65783,"cases":109},
 "new":{"fitness":new["fitness"],"precision":new["precision"],"f1":f1_score(new),"evaluation_cases":len(meta["evaluated_cases"])},
 "new_replay":fitness,"new_shuffled_replay":random_fitness,
 "trace_lengths":lengths.describe().to_dict(),"unique_variants":len(variants),
 "events_by_zone":{str(k):int(v) for k,v in df[A].value_counts().to_dict().items()},
 "model":{"places":len(net.places),"transitions":len(net.transitions),"silent":sum(t.label is None for t in net.transitions),"arcs":len(net.arcs),"labels":labels,"missing_log_labels":sorted(set(df[A])-set(labels))},
 "raw_first":raw_first,"raw_last":raw_last,
 "missing_calendar_days":[str(x.date()) for x in missing],
 "raw_rows_on_missing_days":{str(x.date()):raw_days.get(str(x.date()),0) for x in missing},
 "process_tree":tree_text,
 "dataset_hash_serialization":"CSV con fine riga LF, indipendente dal sistema operativo",
 "evaluation_scope":meta["scope"],
}
output=Path(__file__).with_name("colab_comparison_2026-10-23.json")
output.write_text(json.dumps(report,indent=2,ensure_ascii=False,default=lambda v:v.item()),encoding="utf-8")
print(json.dumps(report,indent=2,ensure_ascii=True,default=lambda v:v.item()))
