import ast
import json
from pathlib import Path

root = Path(__file__).resolve().parents[1]
for filename in ('Aruba_Colab_Training.ipynb', 'Aruba_Colab_Confronto_Modelli.ipynb'):
    path = root / filename
    nb = json.loads(path.read_text(encoding='utf-8'))
    for cell in nb['cells']:
        if cell['cell_type'] != 'code':
            continue
        source = ''.join(cell['source'])
        for node in ast.parse(source).body:
            if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'SOURCES' for t in node.targets):
                old = ast.literal_eval(node.value)
                current = {name: (root / name).read_text(encoding='utf-8') for name in old}
                lines = source.splitlines(keepends=True)
                source = ''.join(lines[:node.lineno-1]) + 'SOURCES = ' + repr(current) + '\n' + ''.join(lines[node.end_lineno:])
                cell['source'] = source.splitlines(keepends=True)
                cell['outputs'] = []
                cell['execution_count'] = None
                break
    path.write_text(json.dumps(nb, indent=1, ensure_ascii=False)+'\n', encoding='utf-8')

path = root/'README.md'
text = path.read_text(encoding='utf-8')
start = text.index('La [relazione di progetto]')
end = text.index('## Avvio Windows')
text = text[:start] + '''La [relazione inglese in Word](PROJECT_DOCUMENTATION_EN.docx) documenta esperimenti, risultati, limiti e uso del sito. È il documento aggiornato manualmente dall'autore. Le precedenti versioni italiane e i sorgenti Markdown sono stati rimossi.

La [presentazione in inglese](output/presentations/Aruba_Process_Mining_Visual_EN.pptx) contiene grafici e schermate della dashboard. Il nuovo calcolo delle quattro dimensioni del 5 novembre 2026 è documentato qui sotto; Word e slide non sono stati modificati in questo aggiornamento e devono ancora recepirlo.

''' + text[end:]
text = text.replace('scopre tre reti di Petri e confronta fitness e precision.', 'applica tre algoritmi di discovery e valuta Fitness, Precision, Simplicity e Generalization.')
heading = '## Discovery e valutazione\n'
addition = '''
### Aggiornamento del 5 novembre 2026

Alpha usa `pm4py.discover_petri_net_alpha`, Heuristic usa `pm4py.discover_petri_net_heuristics`. Inductive ora esegue esplicitamente `pm4py.discover_process_tree_inductive` seguito da `pm4py.convert_to_petri_net`. La modifica riguarda la pipeline locale e i sorgenti incorporati in entrambi i notebook Colab, con le stesse soglie precedenti. I modelli storici rimangono quelli esportati da Colab: non sono stati riscoperti né sostituiti.

Simplicity e Generalization sono state calcolate sui sette modelli già salvati, con PM4Py 2.7.23.11, usando gli stessi 20 casi (21.069 eventi) identificati nei metadati originali. Fitness e Precision sono riportate dai risultati originali senza ricalcolarle.

- **Simplicity:** variante PM4Py `SIMPLICITY_ARC_DEGREE`, parametro predefinito `k=2`. Misura la semplicità tramite il grado degli elementi della rete, incluse le transizioni silenti.
- **Generalization:** variante PM4Py `GENERALIZATION_TOKEN`, basata sulla frequenza delle transizioni attivate nel replay. È una metrica di qualità del process mining sul campione disponibile, non una prova predittiva su giorni nuovi.

'''
result = json.loads((root/'data/experiments/comparison_20261023T213310299553Z/quality_metrics.json').read_text(encoding='utf-8'))
addition += '| Modello | Fitness | Precision | Simplicity | Generalization |\n|---|---:|---:|---:|---:|\n'
for row in result['results']:
    addition += '| '+row['model']+' | '+' | '.join(f'{row[key]:.6f}' for key in ('fitness','precision','simplicity','generalization'))+' |\n'
addition += '''
Heuristic 0.30 e 0.50 restano a pari merito per la media armonica di Fitness e Precision, ma Inductive ottiene Simplicity più alta. Alpha ottiene Generalization alta pur avendo fitness quasi nulla: le quattro dimensioni vanno interpretate congiuntamente. Non viene introdotta una media arbitraria delle quattro metriche e il criterio F1 storico resta invariato.

Il confronto completo è disponibile in [quality_metrics.csv](data/experiments/comparison_20261023T213310299553Z/quality_metrics.csv). [quality_metrics.json](data/experiments/comparison_20261023T213310299553Z/quality_metrics.json) registra metodi, versioni, casi valutati e impronte di dati, modelli e metriche originali. Questi file integrativi conservano intatti il pacchetto Colab originale e le sue impronte. La dashboard esistente continua a leggere le metriche storiche; l'integrazione visiva delle due nuove dimensioni è un passaggio successivo.

Per ripetere esclusivamente il calcolo aggiuntivo sui modelli salvati:

```powershell
.venv_new\\Scripts\\python.exe evaluate_saved_models.py
```

È possibile specificare un altro pacchetto completo con `--experiment percorso`. Lo script verifica l'impronta del dataset e l'identità del campione prima del calcolo. Non esegue discovery o precision. Le nuove esecuzioni della pipeline e del benchmark calcolano tutte e quattro le metriche.

### Risultati e criterio di selezione originali
'''
text = text.replace(heading,heading+addition)
path.write_text(text,encoding='utf-8')
