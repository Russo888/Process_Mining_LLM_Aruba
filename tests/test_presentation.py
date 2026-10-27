import unittest

import pandas as pd

from dashboard_data import (CASE, ZONE, TIME, PERIODS, period_summary,
                            transition_summary, daily_summary)
from dashboard_charts import metric_comparison_chart, simplified_dfg


class PresentationTests(unittest.TestCase):
    def test_period_exposure_handles_partial_days(self):
        df = pd.DataFrame({CASE: ["a", "a", "b", "b"], ZONE: ["A", "B", "A", "B"],
                           TIME: pd.to_datetime(["2011-11-01 18:00", "2011-11-01 20:00",
                                                 "2011-11-02 03:00", "2011-11-02 07:00"])})
        stats = period_summary(df).set_index("Periodo")
        self.assertEqual(list(stats.index), PERIODS)
        self.assertEqual(stats["Ore di calendario"].to_dict(),
                         {"Notte": 6., "Mattina": 1., "Pomeriggio": 1., "Sera": 5.})
        self.assertEqual(stats.Eventi.sum(), 4)
        self.assertAlmostEqual(stats.loc["Sera", "Eventi per ora"], 0.2)
        self.assertEqual(stats["Ore di calendario"].sum(), 13.)

    def test_zero_exposure_is_not_an_infinite_rate(self):
        df = pd.DataFrame({CASE: ["a"], ZONE: ["A"], TIME: pd.to_datetime(["2011-11-01 07:00"])})
        stats = period_summary(df)
        self.assertTrue(stats["Eventi per ora"].isna().all())

    def test_dfg_does_not_connect_different_cases(self):
        df = pd.DataFrame({CASE: ["a", "a", "b", "b"], ZONE: ["A", "B", "C", "D"],
                           TIME: pd.date_range("2011-11-01", periods=4, freq="h")})
        flows = transition_summary(df)
        self.assertEqual(set(zip(flows.Da, flows.A)), {("A", "B"), ("C", "D")})
        graph, count, shown, total = simplified_dfg(df, max_edges=1)
        self.assertEqual((count, shown, total), (2, 1, 2))
        self.assertNotIn("C", graph.source)

    def test_metric_chart_has_separate_bars_on_unit_scale(self):
        table = pd.DataFrame({"Modello": ["A", "B"], "Fitness": [.1, .9],
                              "Precision": [.8, .2], "F1 Score": [.178, .327]}).set_index("Modello")
        spec = metric_comparison_chart(table).to_dict()
        self.assertEqual(spec["encoding"]["y"]["scale"]["domain"], [0, 1])
        self.assertIsNone(spec["encoding"]["y"]["stack"])
        self.assertEqual(spec["encoding"]["xOffset"]["field"], "Metrica")
        self.assertEqual(sum(len(rows) for rows in spec["datasets"].values()), 6)

    def test_long_logs_keep_all_events_when_grouping_days(self):
        df = pd.DataFrame({CASE: list(map(str, range(90))), ZONE: ["A"]*90,
                           TIME: pd.date_range("2011-11-01", periods=90, freq="D")})
        days = daily_summary(df)
        self.assertLessEqual(len(days), 28)
        self.assertEqual(days.Eventi.sum(), 90)
        self.assertEqual(days.iloc[0].Dal, "2011-11-01")
        self.assertEqual(days.iloc[-1].Al, "2012-01-29")


if __name__ == "__main__":
    unittest.main()
