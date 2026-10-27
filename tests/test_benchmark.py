import ast
import contextlib
import io
import json
import pickle
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd
from colab_benchmark import (DEFAULT_CONFIGS, prepare_evaluation, run_comparison,
                             monitor_worker, validate_configs)
from colab_pipeline import CASE, ACTIVITY, TIME, discover_one
from project_paths import PROJECT_DIR


class BenchmarkTests(unittest.TestCase):
    def tiny_log(self):
        return pd.DataFrame({CASE: [str(i//3) for i in range(24)],
                             ACTIVITY: ["A", "B", "C"]*8,
                             TIME: pd.date_range("2012-01-01", periods=24, freq="h")})

    def test_heuristic_threshold_is_forwarded(self):
        with patch("colab_pipeline.pm4py.discover_petri_net_heuristics", return_value=(1,2,3)) as miner:
            discover_one(self.tiny_log(), miner="Heuristic Miner", dependency_threshold=.1)
            self.assertEqual(miner.call_args.kwargs["dependency_threshold"], .1)

    def test_current_colab_evaluation_cases_are_reused(self):
        from dashboard_results import available_results
        folder = next(iter(available_results().values()))
        old = json.loads((folder/"evaluation_metadata.json").read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as tmp:
            meta = prepare_evaluation(folder/"dataset_aruba_attivita.csv", Path(tmp)/"eval.csv", max_cases=20, seed=42)
            self.assertEqual(meta["evaluated_cases"], old["evaluated_cases"])
            self.assertEqual(meta["dataset_sha256"], old["dataset_sha256"])
            self.assertEqual(meta["evaluated_events"], old["evaluated_events"])

    def test_isolated_candidates_share_cases_and_export_all_models(self):
        with tempfile.TemporaryDirectory() as tmp, contextlib.redirect_stdout(io.StringIO()):
            tmp = Path(tmp)
            source = tmp/"log.csv"
            self.tiny_log().to_csv(source, index=False)
            configs = [DEFAULT_CONFIGS[0], DEFAULT_CONFIGS[3]]
            result = run_comparison(source, tmp/"run", configs=configs, max_eval_cases=3,
                                    timeout_seconds=90, max_memory_gb=None, backup_dir=tmp/"backup")
            self.assertEqual(result.Stato.tolist(), ["ok", "ok"])
            records = json.loads((tmp/"run/comparison_results.json").read_text(encoding="utf-8"))
            self.assertEqual(records[0]["evaluated_cases"], records[1]["evaluated_cases"])
            self.assertEqual(len(records[0]["evaluated_cases"]), 3)
            with (tmp/"run/data/models.pkl").open("rb") as handle:
                self.assertEqual(set(pickle.load(handle)), {c["label"] for c in configs})
            metadata = json.loads((tmp/"run/data/evaluation_metadata.json").read_text(encoding="utf-8"))
            self.assertIn("in_sample", metadata["scope"])
            self.assertTrue((tmp/"backup/candidates/inductive_020/discovery.json").exists())
            self.assertTrue((tmp/"backup/comparison.csv").exists())

    def test_timeout_stops_only_the_owned_worker(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = monitor_worker([sys.executable, "-c", "import time; time.sleep(20)"],
                                    Path(tmp)/"worker.log", timeout_seconds=.2, max_memory_gb=None)
            self.assertEqual(result["status"], "timeout")
            self.assertNotEqual(result["returncode"], 0)

    def test_memory_limit_is_recorded(self):
        with tempfile.TemporaryDirectory() as tmp, patch("colab_benchmark.process_rss", return_value=2*2**30):
            result = monitor_worker([sys.executable, "-c", "import time; time.sleep(20)"],
                                    Path(tmp)/"worker.log", timeout_seconds=5, max_memory_gb=1)
            self.assertEqual(result["status"], "memory_limit")

    def test_checkpoint_flow_with_simulated_workers(self):
        """Controlla esportazione e campione comune senza avviare processi o training."""
        def fake_worker(command, log_path, timeout_seconds, max_memory_gb):
            spec = json.loads(Path(command[-1]).read_text(encoding="utf-8"))
            config = spec["config"]
            directory = Path(spec["directory"])
            cases = pd.read_csv(spec["evaluation_csv"])[CASE].unique().tolist()
            with (directory/"models.pkl").open("wb") as handle:
                pickle.dump({config["label"]: (None, None, None)}, handle)
            result = {"status": "ok", "id": config["id"], "label": config["label"],
                      "metrics": {"fitness": .8, "precision": .6}, "f1": 2*.8*.6/1.4,
                      "evaluated_cases": cases, "missing_log_labels": []}
            (directory/"result.json").write_text(json.dumps(result), encoding="utf-8")
            return {"status": "finished", "returncode": 0}
        with tempfile.TemporaryDirectory() as tmp, contextlib.redirect_stdout(io.StringIO()), patch("colab_benchmark.monitor_worker", side_effect=fake_worker):
            root = Path(tmp)
            source = root/"log.csv"
            self.tiny_log().to_csv(source, index=False)
            configs = [DEFAULT_CONFIGS[0], DEFAULT_CONFIGS[3]]
            table = run_comparison(source, root/"run", configs=configs, max_eval_cases=3,
                                   max_memory_gb=None, backup_dir=root/"backup")
            self.assertEqual(table.Stato.tolist(), ["ok", "ok"])
            results = json.loads((root/"run/comparison_results.json").read_text(encoding="utf-8"))
            self.assertEqual(results[0]["evaluated_cases"], results[1]["evaluated_cases"])
            with (root/"run/data/models.pkl").open("rb") as handle:
                self.assertEqual(set(pickle.load(handle)), {c["label"] for c in configs})
            self.assertTrue((root/"backup/comparison.csv").exists())

    def test_watchdog_with_simulated_process(self):
        """Verifica timeout/RAM senza lanciare né terminare processi reali."""
        class FakeProcess:
            pid = 123
            returncode = None
            def __enter__(self): return self
            def __exit__(self, *_): return False
            def poll(self): return self.returncode
            def kill(self): self.returncode = -9
            def wait(self): return self.returncode
        with tempfile.TemporaryDirectory() as tmp:
            fake = FakeProcess()
            with patch("colab_benchmark.subprocess.Popen", return_value=fake), patch("colab_benchmark.time.monotonic", side_effect=[0, 1, 2]):
                result = monitor_worker(["unused"], Path(tmp)/"timeout.log", .01, None)
                self.assertEqual(result["status"], "timeout")
                self.assertEqual(fake.returncode, -9)
            fake = FakeProcess()
            with patch("colab_benchmark.subprocess.Popen", return_value=fake), patch("colab_benchmark.time.monotonic", side_effect=[0, .1, .2]), patch("colab_benchmark.process_rss", return_value=2*2**30):
                result = monitor_worker(["unused"], Path(tmp)/"memory.log", 5, 1)
                self.assertEqual(result["status"], "memory_limit")
                self.assertEqual(fake.returncode, -9)

    def test_configs_and_embedded_notebook_sources_are_valid(self):
        validate_configs(DEFAULT_CONFIGS)
        self.assertEqual({c["miner"] for c in DEFAULT_CONFIGS},
                         {"Alpha Miner", "Heuristic Miner", "Inductive Miner"})
        self.assertEqual(len(DEFAULT_CONFIGS), 7)
        with self.assertRaises(ValueError):
            validate_configs([{"id": "alpha", "label": "Alpha", "miner": "Alpha Miner",
                               "parameters": {"noise_threshold": .2}}])
        with self.assertRaises(ValueError):
            validate_configs([DEFAULT_CONFIGS[0], DEFAULT_CONFIGS[0]])
        nb = json.loads((PROJECT_DIR/"Aruba_Colab_Confronto_Modelli.ipynb").read_text(encoding="utf-8"))
        found = False
        for cell in nb["cells"]:
            if cell["cell_type"] != "code":
                continue
            tree = ast.parse("".join(cell["source"]))
            for node in tree.body:
                if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "SOURCES" for t in node.targets):
                    found = True
                    for name, content in ast.literal_eval(node.value).items():
                        self.assertEqual(content, (PROJECT_DIR/name).read_text(encoding="utf-8"))
        self.assertTrue(found)


if __name__ == "__main__":
    unittest.main()
