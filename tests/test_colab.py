import ast
import contextlib
import gc
import io
import shutil
from types import SimpleNamespace
from unittest.mock import Mock
import json
import pickle
import tempfile
import unittest
import zipfile
from pathlib import Path

import pandas as pd
from pandas.testing import assert_frame_equal
import pm4py
from colab_pipeline import (CASE, ACTIVITY, TIME, preprocess_raw_to_csv, load_event_log,
                            discover_one, export_results, package_results)
from project_paths import DATASET_PATH, PROJECT_DIR


class ColabTests(unittest.TestCase):
    def test_streaming_preprocessing_matches_current_dataset(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)/"prepared.csv"
            info = preprocess_raw_to_csv(DATASET_PATH, output)
            result = load_event_log(output)
            from dashboard_results import available_results
            expected = load_event_log(next(iter(available_results().values()))/"dataset_aruba_attivita.csv")
            assert_frame_equal(result, expected)
            self.assertEqual(info["written_events"], len(expected))

    def test_unsorted_input_does_not_overwrite_previous_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            source, output = Path(tmp)/"raw.txt", Path(tmp)/"prepared.csv"
            source.write_text("2011-11-01 08:00:00 M003 ON\n2011-11-01 07:00:00 M005 ON\n")
            output.write_text("previous")
            with self.assertRaisesRegex(ValueError, "non cronologico"):
                preprocess_raw_to_csv(source, output)
            self.assertEqual(output.read_text(), "previous")
            self.assertFalse(output.with_suffix(".partial.csv").exists())

    def test_discovery_export_download_bundle_roundtrip(self):
        df = pd.DataFrame({CASE: ["a", "a", "b", "b"], ACTIVITY: ["A", "B", "A", "B"],
                           TIME: pd.date_range("2011-11-01", periods=4, freq="h")})
        models = discover_one(df, noise_threshold=0)
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp)/"input.csv"
            df.to_csv(source, index=False)
            root = Path(tmp)/"run"
            export_results(df, models, root, source, {"miner": "Inductive Miner"})
            archive = package_results(root)
            with zipfile.ZipFile(archive) as z:
                self.assertTrue({"data/models.pkl", "data/metrics.json", "data/dataset_aruba_attivita.csv",
                                 "data/model_1.pnml", "run_manifest.json", "requirements_colab.txt"}.issubset(z.namelist()))
                self.assertEqual(json.loads(z.read("data/metrics.json")), {})
                manifest = json.loads(z.read("run_manifest.json"))
                self.assertEqual(manifest["evaluation"], "not_run")
                self.assertEqual(manifest["events"], 4)
                restored = pickle.loads(z.read("data/models.pkl"))
                self.assertEqual(set(restored), {"Inductive Miner"})
            net, _, _ = pm4py.read_pnml(str(root/"data/model_1.pnml"))
            self.assertEqual({t.label for t in net.transitions if t.label}, {"A", "B"})
            assert_frame_equal(load_event_log(root/"data/dataset_aruba_attivita.csv"), load_event_log(source))

    def test_date_window_is_inclusive_and_reports_exclusions(self):
        raw = (
            "2011-11-01 23:59:00 M003 ON\n"
            "2011-11-02 00:00:00 M003 ON\n"
            "2011-11-02 00:01:00 M003 OFF\n"
            "2011-11-02 06:00:00 M003 ON\n"
            "2011-11-02 06:01:00 M005 ON\n"
            "2011-11-02 20:00:00 T001 17\n"
            "2011-11-02 20:00:00 D003 OPEN\n"
            "2011-11-02 broken M003 ON\n"
            "bad\n"
            "2011-11-03 00:00:00 M003 ON\n"
        )
        with tempfile.TemporaryDirectory() as tmp:
            source, output = Path(tmp)/"raw.txt", Path(tmp)/"prepared.csv"
            source.write_text(raw)
            info = preprocess_raw_to_csv(source, output, "2011-11-02", "2011-11-02")
            result = load_event_log(output)
            self.assertEqual(len(result), 3)
            self.assertEqual(result[CASE].tolist(), ["2011-11-02_Notte", "2011-11-02_Mattina", "2011-11-02_Mattina"])
            self.assertEqual(info["outside_date_range"], 2)
            self.assertEqual(info["excluded_non_motion_door"], 1)
            self.assertEqual(info["unmapped_sensor_counts"], {"D003": 1})
            self.assertEqual(info["invalid_timestamps"], 1)
            self.assertEqual(info["malformed_lines"], 1)
            self.assertEqual(info["consecutive_duplicates_removed"], 1)
            self.assertEqual(sum(info["events_by_period"].values()), 3)
            self.assertEqual(info["states_before_compression"], {"OFF": 1, "ON": 3})

    def test_notebook_preprocesses_before_discovery_and_backs_up(self):
        nb = json.loads((PROJECT_DIR/"Aruba_Colab_Training.ipynb").read_text(encoding="utf-8"))
        code = ["".join(c["source"]) for c in nb["cells"] if c["cell_type"] == "code"]
        preprocess = next(c for c in code if c.startswith("import pandas as pd\n"))
        load = next(c for c in code if c.startswith("df = load_event_log("))
        discovery = next(c for c in code if c.startswith("gc.collect()"))
        with tempfile.TemporaryDirectory() as tmp, contextlib.redirect_stdout(io.StringIO()):
            root = Path(tmp)
            source = root/"raw.txt"
            source.write_text("2011-11-01 07:00:00 M003 ON\n2011-11-01 07:01:00 M003 OFF\n2011-11-01 07:02:00 M005 ON\n")
            run = root/"run"
            prepared = run/"data/prepared.csv"
            prepared.parent.mkdir(parents=True)
            fake_miner = Mock(return_value={})
            scope = {"DATASET": source, "PREPARED_CSV": prepared, "RUN_DIR": run,
                     "DRIVE_DIR": root/"drive", "INPUT_KIND": "raw_sensors",
                     "START_DATE": None, "END_DATE": None, "MINER": "Inductive Miner",
                     "NOISE_THRESHOLD": .2, "display": lambda *_: None,
                     "preprocess_raw_to_csv": preprocess_raw_to_csv, "load_event_log": load_event_log,
                     "shutil": shutil, "json": json, "gc": gc, "discover_one": fake_miner,
                     "psutil": SimpleNamespace(virtual_memory=lambda: SimpleNamespace(available=2**30))}
            exec(compile(preprocess, "preprocessing_cell", "exec"), scope)
            self.assertNotIn("df", scope)
            self.assertTrue((root/"drive/preprocessing_report.json").exists())
            self.assertTrue((root/"drive/data/prepared.csv").exists())
            exec(compile(load, "load_cell", "exec"), scope)
            self.assertEqual(len(scope["df"]), 2)
            exec(compile(discovery, "discovery_cell", "exec"), scope)
            self.assertIs(fake_miner.call_args.args[0], scope["df"])

    def test_notebook_cells_compile_and_embedded_code_is_current(self):
        nb = json.loads((PROJECT_DIR/"Aruba_Colab_Training.ipynb").read_text(encoding="utf-8"))
        found = False
        for cell in nb["cells"]:
            if cell["cell_type"] != "code":
                continue
            source = "".join(cell["source"])
            tree = ast.parse(source)
            for node in tree.body:
                if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "SOURCES" for t in node.targets):
                    found = True
                    for name, content in ast.literal_eval(node.value).items():
                        self.assertEqual(content, (PROJECT_DIR/name).read_text(encoding="utf-8"))
        self.assertTrue(found)


if __name__ == "__main__":
    unittest.main()
