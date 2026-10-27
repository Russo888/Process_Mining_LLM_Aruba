"""Audit storico: richiede CSV e modelli originali della finestra novembre 2011.

Non eseguire sui risultati 2012: le baseline e gli split sono specifici del 2011.
I risultati originali sono conservati in results_audit.json.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import json
import pickle
from collections import deque
import numpy as np
import pandas as pd
import pm4py
from project_paths import OUTPUT_CSV, OUTPUT_MODELS, DATASET_PATH
from preprocessing import SENSOR_ACTIVITY_MAP, get_time_of_day
from llm_context import smart_sample_dataframe

C,A,T = "case:concept:name", "concept:name", "time:timestamp"
df=pd.read_csv(OUTPUT_CSV,parse_dates=[T])
lengths=df.groupby(C,sort=False).size()
variants=df.groupby(C,sort=False)[A].agg(tuple).value_counts()
period=df[C].str.rsplit("_",n=1).str[-1]
period_stats=df.assign(period=period).groupby("period").agg(events=(A,"size"),cases=(C,"nunique"))
period_stats["events_per_case"]=period_stats.events/period_stats.cases
period_stats["hours_in_window"]=pd.Series({"Notte":6,"Mattina":6,"Pomeriggio":7,"Sera":5})
period_stats["events_per_nominal_hour"]=period_stats.events_per_case/period_stats.hours_in_window
raw=pd.read_csv(DATASET_PATH,sep=r"\s+",header=None,usecols=range(5),names=["date","time","sensor","state","sensor_type"])
raw["ts"]=pd.to_datetime(raw.date+" "+raw.time)
raw=raw[raw.sensor.isin(SENSOR_ACTIVITY_MAP)].sort_values("ts",kind="stable")
raw["zone"]=raw.sensor.map(SENSOR_ACTIVITY_MAP)
raw[C]=raw.ts.dt.date.astype(str)+"_"+raw.ts.dt.hour.map(get_time_of_day)
active=raw[raw.state.isin(["ON","OPEN"])].copy()
mask=active.zone.ne(active.zone.shift()) | active[C].ne(active[C].shift())
active=active[mask]
sample=smart_sample_dataframe(df,max_rows=100)
sample_period=sample[C].str.rsplit("_",n=1).str[-1]
with open(OUTPUT_MODELS,"rb") as f: models=pickle.load(f)
model_stats={}
for name,model in models.items():
 net,im,fm=model
 model_stats[name]={"places":len(net.places),"transitions":len(net.transitions),"silent":sum(t.label is None for t in net.transitions),"arcs":len(net.arcs),"labels":sorted({t.label for t in net.transitions if t.label is not None})}
# Controllo negativo: mantieni frequenze, casi e timestamp, mescola soltanto l'ordine delle zone.
selected=lengths.index[:10]
real=df[df[C].isin(selected)].copy()
shuffled=real.copy()
rng=np.random.default_rng(42)
for case,group in shuffled.groupby(C,sort=False): shuffled.loc[group.index,A]=rng.permutation(group[A].to_numpy())
net,im,fm=models["Inductive Miner"]
real_f=pm4py.fitness_token_based_replay(real,net,im,fm)
random_f=pm4py.fitness_token_based_replay(shuffled,net,im,fm)
# Baseline next-zone: split cronologico per giorni, senza transizioni attraverso i casi.
next_zone=df.groupby(C,sort=False)[A].shift(-1)
paired=df.assign(next_zone=next_zone).dropna(subset=["next_zone"])
train=paired[paired[T]<"2011-11-22"]
test=paired[paired[T]>="2011-11-22"]
majority=train.next_zone.mode().iloc[0]
lookup=train.groupby(A).next_zone.agg(lambda x:x.value_counts().index[0])
pred=test[A].map(lookup).fillna(majority)
report={"events":len(df),"cases":len(lengths),"zones":df[A].nunique(),"trace_lengths":lengths.describe().to_dict(),"unique_variants":len(variants),"top5_variant_case_coverage":float(variants.head(5).sum()/len(lengths)),"periods":period_stats.to_dict(orient="index"),"zone_counts":df[A].value_counts().to_dict(),"raw_states":raw.state.value_counts().to_dict(),"sensor_types":raw.sensor_type.value_counts().to_dict(),"active_only_events":len(active),"change_from_both_states":float(1-len(active)/len(df)),"local_sample_events":len(sample),"local_sample_cases":sample[C].nunique(),"local_sample_periods":sample_period.value_counts().to_dict(),"models":model_stats,"negative_control_10_first_cases":{"real_fitness":real_f,"shuffled_fitness":random_f},"next_zone_chronological_baseline":{"train_before":"2011-11-22","train_transitions":len(train),"test_transitions":len(test),"majority_label":majority,"majority_accuracy":float(test.next_zone.eq(majority).mean()),"markov_top1_accuracy":float(pred.eq(test.next_zone).mean())}}
# Diagnostica strutturale: raggiungibilità nel grafo, non prova completa di soundness.
for name, (net, im, fm) in models.items():
    nodes = set(net.places) | set(net.transitions)
    def reach(starts, reverse=False):
        found = set(starts)
        queue = deque(starts)
        while queue:
            node = queue.popleft()
            for arc in node.in_arcs if reverse else node.out_arcs:
                nxt = arc.source if reverse else arc.target
                if nxt not in found:
                    found.add(nxt)
                    queue.append(nxt)
        return found
    report["models"][name]["nodes_unreachable_from_initial"] = len(nodes - reach(im.keys()))
    report["models"][name]["nodes_unable_to_reach_final"] = len(nodes - reach(fm.keys(), True))
    report["models"][name]["source_transitions"] = sorted(t.label for t in net.transitions if not t.in_arcs and t.label)
    report["models"][name]["sink_transitions"] = sorted(t.label for t in net.transitions if not t.out_arcs and t.label)
from project_paths import EVALUATION_METADATA
metadata = json.loads(EVALUATION_METADATA.read_text(encoding="utf-8"))
eval_df = df[df[C].isin(metadata["evaluated_cases"])]
report["inductive_evaluation_50_cases"] = pm4py.fitness_token_based_replay(eval_df, *models["Inductive Miner"])
out=Path(__file__).with_name("results_audit.json")
out.write_text(json.dumps(report,indent=2,ensure_ascii=False,default=float),encoding="utf-8")
print(json.dumps(report,indent=2,ensure_ascii=True,default=float))
