import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pandas as pd
from pandas.testing import assert_frame_equal

from evaluation import choose_best, choose_best_model_internal, evaluate_models_safe
from llm_context import smart_sample_dataframe
from llm_chatbot import GeminiEngine
from preprocessing import load_and_transform_dataset
from project_paths import DATASET_PATH


class CoherenceTests(unittest.TestCase):
    def test_csv_matches_raw(self):
        from dashboard_results import available_results
        csv_path = next(iter(available_results().values()))/"dataset_aruba_attivita.csv"
        expected = pd.read_csv(csv_path, parse_dates=["time:timestamp"])
        assert_frame_equal(load_and_transform_dataset(DATASET_PATH), expected)

    def test_selection_uses_harmonic_mean_everywhere(self):
        scores = {"permissive": {"fitness": 1., "precision": .1},
                  "balanced": {"fitness": .5, "precision": .5},
                  "incomplete": {}, "invalid": {"fitness": float("nan"), "precision": 1}}
        self.assertEqual(choose_best(scores)[0], "balanced")
        self.assertEqual(choose_best_model_internal(scores), "balanced")
        self.assertEqual(choose_best({}), (None, None))

    def test_sampling_preserves_cases_and_budget(self):
        df = pd.DataFrame({"case:concept:name": ["a"]*5 + ["b"]*4 + ["c"]*3})
        a = smart_sample_dataframe(df, max_rows=7)
        assert_frame_equal(a, smart_sample_dataframe(df, max_rows=7))
        self.assertLessEqual(len(a), 7)
        for case in a["case:concept:name"].unique():
            self.assertEqual(len(a[a["case:concept:name"] == case]), len(df[df["case:concept:name"] == case]))
        with self.assertRaises(ValueError):
            smart_sample_dataframe(df, max_rows=2)

    def test_evaluation_sampling_is_reproducible(self):
        df = pd.DataFrame({"case:concept:name": [str(i) for i in range(60)],
                           "concept:name": ["A"]*60,
                           "time:timestamp": pd.date_range("2011-11-01", periods=60, freq="h")})
        selected = []
        def evaluate(sample, *model):
            selected.append(sample["case:concept:name"].tolist())
            return {"fitness": 1., "precision": 1.}
        with tempfile.TemporaryDirectory() as d, patch("evaluation.evaluate", side_effect=evaluate):
            meta = Path(d)/"metadata.json"
            evaluate_models_safe(df, {"test": (None, None, None)}, metadata_path=meta)
            evaluate_models_safe(df, {"test": (None, None, None)})
            self.assertEqual(selected[0], selected[1])
            self.assertEqual(len(selected[0]), 50)
            self.assertEqual(json.loads(meta.read_text(encoding="utf-8"))["seed"], 42)

    def test_gemini_client_and_model_are_session_scoped(self):
        first, second = GeminiEngine(), GeminiEngine()
        with patch("llm_chatbot.genai.Client") as client:
            self.assertTrue(first.init_llm_from_config(api_key="test", model_name="configured-model"))
            self.assertIsNone(second.client)
            client.return_value.models.generate_content.return_value = SimpleNamespace(text="ok")
            self.assertEqual(first.ask_llm("question", "DFG", "csv"), "ok")
            kwargs = client.return_value.models.generate_content.call_args.kwargs
            self.assertEqual(kwargs["model"], "configured-model")
            self.assertIn("csv", kwargs["contents"])

    def test_gemini_requires_key_without_creating_client(self):
        with tempfile.TemporaryDirectory() as folder:
            config = Path(folder)/"config.json"
            config.write_text('{"model_name":"configured-model"}')
            with patch.dict("os.environ", {"GOOGLE_API_KEY": ""}), patch("llm_chatbot.genai.Client") as client:
                engine = GeminiEngine()
                self.assertFalse(engine.init_llm_from_config(config_path=config))
                client.assert_not_called()
                self.assertIn("API key", engine.last_error)


if __name__ == "__main__":
    unittest.main()
