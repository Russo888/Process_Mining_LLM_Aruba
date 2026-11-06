"""Preserve the edited English report and add the saved-model evaluation."""
from pathlib import Path
import json
import shutil
from docx import Document
from docx.shared import Inches, Pt
from docx.oxml import OxmlElement

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'audit/quality_update_2026-11-05'
OUT.mkdir(exist_ok=True)
source = ROOT / 'PROJECT_DOCUMENTATION_EN.docx'
backup = OUT / 'original.docx'
if not backup.exists():
    shutil.copy2(source, backup)
doc = Document(backup)
paras = list(doc.paragraphs)
paras[5].text = 'Project report | Updated 5 November 2026 | English edition'
paras[76].text = 'Durations below are supervisor measurements for each process, including process startup. Fitness and precision were read from the original JSON files and checked against the CSV and metadata; those expensive calculations were not repeated on the PC. The separate November evaluation below computes Simplicity and Generalization directly on the saved models.'
paras[90].text = 'The October execution recorded PM4Py 2.7.23.11, pandas 2.2.3, and NumPy 2.1.3. Its integrity checks establish consistency among exported artefacts, not independent recomputation of fitness and precision. The supplementary November calculation records its own runtime versions. Ranking remains in-sample; selecting a threshold and reporting performance on the same cases does not establish performance on new days.'

def before(anchor, text, style=None):
    return anchor.insert_paragraph_before(text, style)

before(paras[42], 'Simplicity measures structural economy using PM4Py’s arc-degree method. It depends on node connectivity, rather than simply counting places or transitions. Generalization uses PM4Py’s token-replay method, which rewards repeated visits to transitions. Both range from 0 to 1, with higher values favoured by the respective definition. This Generalization score is a structural replay measure, not an estimate of predictive accuracy on unseen days.')
before(paras[42], 'The four quality dimensions are reported together in the supplementary evaluation in Chapter 7. The harmonic mean remains a separate summary of fitness and precision only; no unsupported overall average across all four dimensions is introduced.')
anchor = paras[94]
before(anchor, 'Supplementary evaluation on the saved models', 'Heading 2')
before(anchor, 'On 5 November 2026, the seven saved Petri nets were evaluated for Simplicity and Generalization without repeating discovery. The script evaluate_saved_models.py loads the original models.pkl and reconstructs the exact 20 case identifiers stored in evaluation_metadata.json, containing 21,069 events. It verifies the dataset fingerprint and sample size. Fitness and precision below are copied unchanged from the original comparison.')
before(anchor, 'The calculation uses PM4Py 2.7.23.11, the same PM4Py version as the Colab benchmark, and pandas 3.0.1. Simplicity uses SIMPLICITY_ARC_DEGREE with the default k = 2; Generalization uses GENERALIZATION_TOKEN. The JSON supplement records the computation date, runtime versions, input fingerprints, evaluated cases, methods, and results.')
data = json.loads((ROOT/'data/experiments/comparison_20261023T213310299553Z/quality_metrics.json').read_text())
table = doc.add_table(rows=1, cols=5)
table.style = doc.tables[6].style
headers = ['Configuration', 'Fitness', 'Precision', 'Simplicity', 'Generalization']
for c, text in zip(table.rows[0].cells, headers):
    c.text = text
for r in data['results']:
    cells = table.add_row().cells
    cells[0].text = r['model'].replace(' (riferimento)', '').replace(' noise=', ' ').replace(' dependency=', ' ')
    for cell, key in zip(cells[1:], ['fitness','precision','simplicity','generalization']):
        cell.text = f'{r[key]:.4f}'
for row in table.rows:
    for cell in row.cells:
        for p in cell.paragraphs:
            for run in p.runs:
                run.font.size = Pt(9)
    prop = row._tr.get_or_add_trPr()
    prop.append(OxmlElement('w:cantSplit'))
table.rows[0]._tr.get_or_add_trPr().append(OxmlElement('w:tblHeader'))
anchor._p.addprevious(table._tbl)
before(anchor, 'Table — Four quality dimensions for all seven saved configurations. Values are rounded to four decimals; full precision is retained in quality_metrics.json and quality_metrics.csv.', 'Caption')
before(anchor, 'Heuristic 0.30 and 0.50 remain tied and retain the strongest harmonic mean of fitness and precision. Their Simplicity is 0.4630 and Generalization is 0.6806. Inductive 0.00 has the highest Simplicity score, 0.6257, even though it contains more nodes than the Inductive reference: arc-degree simplicity measures connectivity, not raw net size. Inductive 0.10 and 0.20 achieve Generalization 0.7878 but remain permissive, with Precision 0.0840.')
before(anchor, 'Alpha obtains the highest Generalization score, 0.9128, while Fitness is only 0.0033 and no evaluated case fits perfectly. Repeated transition visits during imperfect token replay can yield a high Generalization score. This combination does not establish that Alpha explains the log or generalizes to new days. The four dimensions must therefore be interpreted jointly, together with complete-trace replay and order diagnostics.')
before(anchor, 'Heuristic 0.30 remains the proposed demonstration model, tied with 0.50, because of its comparatively better fitness–precision balance. It is not the winner on every dimension, and no model has established reliable routine recognition or predictive monitoring. The supplementary measurements strengthen the comparison without reversing these limitations.')
before(anchor, 'Implementation alignment for Inductive Miner', 'Heading 2')
before(anchor, 'New local and Colab runs now explicitly call pm4py.discover_process_tree_inductive and then pm4py.convert_to_petri_net. Alpha and Heuristic retain their respective PM4Py discovery functions. Both notebooks embed the updated source code. This fulfils the specified process-tree-to-Petri-net workflow for future executions. The seven historical models were not regenerated or relabelled as outputs of a new experiment.')
before(anchor, 'The original metrics, metadata, model files and exports remain unchanged. The supplement is stored beside them as quality_metrics.json and quality_metrics.csv. Future evaluations calculate all four dimensions. Existing dashboard screenshots and the current presentation still show the historical fitness, precision and harmonic-mean comparison; they do not yet display the supplementary dimensions.')

before(paras[214], 'Delivery scope and remaining requirements', 'Heading 2')
before(paras[214], 'The implementation now includes all three required discovery families and quantitative evaluation on all four quality dimensions. The report documents the experiments, their limitations and the website. This is a substantial exploratory project, but it is not yet fully compliant with every item of the supplied assignment checklist.')
before(paras[214], 'Before claiming full compliance, the dashboard and presentation must include the four-dimension comparison. Quantitative temporal analysis of case durations and inter-event intervals must also be implemented and interpreted carefully: intervals between sensor records do not directly measure room occupancy or service waiting times. Predictive monitoring still requires a defined target, an implemented baseline and evaluation on chronologically held-out complete cases. Gemini integration requires a recorded functional demonstration; suggested next activities in an LLM response are not a validated predictor.')
doc.add_paragraph('Supplementary evaluation: evaluate_saved_models.py and data/experiments/comparison_20261023T213310299553Z/quality_metrics.json and quality_metrics.csv. These files preserve the original sample and record the provenance of the additional measurements.')
doc.save(source)
readme = ROOT/'README.md'
text = readme.read_text(encoding='utf-8')
text = text.replace('È il documento aggiornato manualmente dall\'autore.', 'Conserva le modifiche dell’autore e include la valutazione aggiuntiva del 5 novembre 2026.')
text = text.replace('Il nuovo calcolo delle quattro dimensioni del 5 novembre 2026 è documentato qui sotto; Word e slide non sono stati modificati in questo aggiornamento e devono ancora recepirlo.', 'Il calcolo delle quattro dimensioni del 5 novembre 2026 è documentato qui sotto e nella relazione Word. Le slide e i grafici della dashboard devono ancora integrare Simplicity e Generalization; analisi temporale quantitativa e predizione validata restano requisiti aperti per la piena conformità alla traccia.')
readme.write_text(text, encoding='utf-8')
print('Updated English report and README; original Word preserved in', backup)
