"""Read-only checks of exported results; no model training or expensive replay."""
import hashlib
import json
import math
from pathlib import Path
import xml.etree.ElementTree as ET
import pandas as pd
import numpy as np
import networkx as nx

ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT/'audit/colab_received_2026-10-27/comparison_20261023T213310299553Z'
def read(path): return json.loads(path.read_text(encoding='utf-8'))
def sha(data): return hashlib.sha256(data).hexdigest()
manifest=read(RUN/'comparison_manifest.json')
meta=read(RUN/'data/evaluation_metadata.json')
metrics=read(RUN/'data/metrics.json')
records=read(RUN/'comparison_results.json')
old=read(ROOT/'data/evaluation_metadata.json')
checks={}
def verify(name, condition):
    checks[name]=bool(condition)
    assert condition, name
keys=['case:concept:name','concept:name','time:timestamp']
df=pd.read_csv(RUN/'data/dataset_aruba_attivita.csv',usecols=keys)
df[keys[2]]=pd.to_datetime(df[keys[2]],format='ISO8601')
df=df.sort_values(keys[2],kind='stable').reset_index(drop=True)
fingerprint=df[keys].copy()
fingerprint[keys[2]]=fingerprint[keys[2]].astype(str)
verify('raw_csv_hash',sha((RUN/'data/dataset_aruba_attivita.csv').read_bytes())==manifest['dataset_csv_sha256'])
verify('canonical_dataset_hash',sha(fingerprint.to_csv(index=False,lineterminator='\n').encode())==meta['dataset_sha256'])
verify('same_dataset_as_previous_colab',meta['dataset_sha256']==old['dataset_sha256'])
verify('metrics_hash',sha(json.dumps(metrics,sort_keys=True).encode())==meta['metrics_sha256'])
verify('manifest_metadata',manifest['evaluation']==meta)
verify('same_cases_as_previous_colab',meta['evaluated_cases']==old['evaluated_cases'])
cases=df[keys[0]].unique()
chosen=np.random.default_rng(meta['seed']).choice(cases,meta['max_eval_cases'],replace=False)
sample=df[df[keys[0]].isin(chosen)].reset_index(drop=True)
exported=pd.read_csv(RUN/'evaluation_log.csv')
exported[keys[2]]=pd.to_datetime(exported[keys[2]],format='ISO8601')
verify('evaluation_log_exact_complete_case_sample',sample.equals(exported[keys]))
verify('sample_event_count',len(sample)==meta['evaluated_events'])
verify('case_count',len(cases)==meta['total_cases'])
verify('all_seven_completed',len(records)==manifest['completed']==manifest['planned']==7 and all(r['status']=='ok' for r in records))
table=pd.read_csv(RUN/'comparison.csv').set_index('Modello')
graphs={}
for r in records:
    folder=RUN/'candidates'/r['id']
    verify(r['id']+'_sample',r['evaluated_cases']==meta['evaluated_cases'])
    verify(r['id']+'_metrics',r['metrics']==metrics[r['label']])
    expected=dict(r); expected.pop('execution')
    verify(r['id']+'_individual_result',read(folder/'result.json')==expected)
    f,p=r['metrics']['fitness'],r['metrics']['precision']
    verify(r['id']+'_harmonic_mean',math.isclose(r['f1'],2*f*p/(f+p),abs_tol=1e-12))
    verify(r['id']+'_csv',all(math.isclose(table.loc[r['label'],c],v,abs_tol=1e-12) for c,v in [('Fitness',f),('Precision',p),('F1',r['f1'])]))
    verify(r['id']+'_order_gap',math.isclose(f-r['shuffled_fitness'],r['order_fitness_gap'],abs_tol=1e-12))
    tree=ET.parse(folder/'model.pnml')
    page=tree.find('.//page')
    places=page.findall('place'); transitions=page.findall('transition'); arcs=page.findall('arc')
    verify(r['id']+'_pnml_dimensions',(len(places),len(transitions),len(arcs))==(r['places'],r['transitions'],r['arcs']))
    g=nx.DiGraph()
    final={e.attrib['idref']:e.findtext('text') for e in tree.findall('.//finalmarkings/marking/place')}
    labels=set(); silent=0
    for e in places:
        g.add_node(e.attrib['id'],kind='place',label='',initial=e.findtext('initialMarking/text','0'),final=final.get(e.attrib['id'],'0'))
    for e in transitions:
        invisible=any(t.attrib.get('activity')=='$invisible$' for t in e.findall('toolspecific'))
        label=None if invisible else e.findtext('name/text')
        silent+=invisible
        if label is not None: labels.add(label)
        g.add_node(e.attrib['id'],kind='transition',label=label,initial='0',final='0')
    for e in arcs: g.add_edge(e.attrib['source'],e.attrib['target'],weight=e.findtext('inscription/text','1'))
    verify(r['id']+'_pnml_labels',sorted(set(df[keys[1]])-labels)==r['missing_log_labels'])
    verify(r['id']+'_pnml_silent',silent==r['silent_transitions'])
    graphs[r['id']]=g
equivalences={}
for a,b in [('heuristic_030','heuristic_050'),('inductive_020','inductive_010')]:
    equivalences[a+'__'+b]=nx.is_isomorphic(graphs[a],graphs[b],node_match=lambda x,y:x==y,edge_match=lambda x,y:x==y)
summary={'checks':checks,'passed':len(checks),'events':len(df),'cases':len(cases),'zones':df[keys[1]].nunique(),
         'start':str(df[keys[2]].min()),'end':str(df[keys[2]].max()),'sample_events':len(sample),
         'same_marked_labeled_graph':equivalences,'worker_seconds_sum':sum(r['execution']['seconds'] for r in records),
         'ram_peak_available':False,'note':'peak_worker_gb=0 is not a measurement: monitoring was disabled with max_memory_gb=None.',
         'f1_relative_gain':records[3]['f1']/records[0]['f1']-1,'records':records,
         'validation_scope':'Integrity and consistency checks; no independent recomputation of fitness or precision.'}
(ROOT/'audit/comparison_verification_2026-10-27.json').write_text(json.dumps(summary,indent=2,ensure_ascii=False),encoding='utf-8')
print(json.dumps({k:v for k,v in summary.items() if k not in ['checks','records']},indent=2))
