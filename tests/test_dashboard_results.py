import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pandas as pd
from dashboard_results import (available_results, best_models, load_result_bundle,
                               comparison_details, selected_model_context)
from project_paths import PROJECT_DIR


class DashboardResultsTests(unittest.TestCase):
    def test_installed_comparison_loads_seven_consistent_models(self):
        catalog = available_results()
        folder = next(p for p in catalog.values() if p.parent.name == 'comparison_20261023T213310299553Z')
        df, models, scores, meta, details = load_result_bundle(folder)
        self.assertEqual((len(df), len(models), len(details)), (329885, 7, 7))
        self.assertEqual(len(meta['evaluated_cases']), 20)
        self.assertEqual(best_models(scores), ['Heuristic dependency=0.30', 'Heuristic dependency=0.50'])
        table = comparison_details(details).set_index('Modello')
        self.assertEqual(table.loc['Heuristic dependency=0.30', 'Tracce mescolate fitting %'], 0)
        self.assertTrue((table['Etichette omesse'] == 'Nessuna').all())

    def test_catalog_excludes_incomplete_packages(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            run = root/'experiments/test/data'
            run.mkdir(parents=True)
            (root/'models.pkl').write_bytes(b'old')
            self.assertFalse(available_results(root))
            for name in ('models.pkl', 'metrics.json', 'dataset_aruba_attivita.csv'):
                (run/name).touch()
            self.assertEqual(list(available_results(root).values()), [run])

    def test_mismatched_csv_is_rejected_before_pickle_loading(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            pd.DataFrame({'case:concept:name':['a'], 'concept:name':['A'],
                          'time:timestamp':['2012-01-01 00:00:00']}).to_csv(root/'dataset_aruba_attivita.csv', index=False)
            (root/'metrics.json').write_text('{}')
            (root/'evaluation_metadata.json').write_text(json.dumps({'dataset_sha256':'incorrect'}))
            with patch('dashboard_results.pickle.load') as unpickle, self.assertRaisesRegex(ValueError, 'CSV'):
                load_result_bundle(root)
            unpickle.assert_not_called()

    def test_ai_context_tracks_selected_configuration(self):
        model=(SimpleNamespace(places=set(), transitions=set(), arcs=set()), None, None)
        scores={'A':{'fitness':1,'precision':.1},'B':{'fitness':.9,'precision':.2}}
        context=json.loads(selected_model_context('B',model,scores,{'B':{'status':'ok'}}, {'seed':42}, 'Test'))
        self.assertEqual(context['modello_selezionato'], 'B')
        self.assertEqual(context['metriche_selezionate'], scores['B'])
        self.assertEqual(context['valutazione']['seed'], 42)

    def test_switching_model_resets_chat_and_changes_metrics(self):
        from streamlit.testing.v1 import AppTest
        # No remote LLM requests; initialization is disabled for the UI check.
        with patch('llm_chatbot.GeminiEngine.init_llm_from_config', return_value=False):
            app=AppTest.from_file(str(PROJECT_DIR/'dashboard.py'), default_timeout=120).run()
            self.assertFalse(app.exception, str(app.exception))
            self.assertNotIn('ai_mode_choice', [r.key for r in app.radio])
            self.assertEqual(len([b for b in app.button if b.label == 'Configura Gemini']), 1)
            self.assertEqual(app.selectbox(key='selected_process_model').value, 'Heuristic dependency=0.30')
            app.session_state['messages']=[{'role':'assistant','content':'OLD MODEL RESPONSE'}]
            app.session_state['last_report']='OLD REPORT'
            app.selectbox(key='selected_process_model').set_value('Inductive noise=0.00').run()
            self.assertFalse(app.exception, str(app.exception))
            self.assertEqual(app.metric[0].value, '1.0000')
            self.assertEqual(app.metric[1].value, '0.0840')
            self.assertNotIn('OLD MODEL RESPONSE', str(app.session_state['messages']))
            self.assertNotIn('last_report', app.session_state)
            app.selectbox(key='results_source').set_value('Upload manuale').run()
            self.assertFalse(app.session_state['data_loaded'])
            self.assertEqual(len(app.metric), 0)


if __name__ == '__main__':
    unittest.main()
