import unittest
from unittest.mock import patch
import pandas as pd
import pm4py
from colab_pipeline import discover_one, CASE, ACTIVITY, TIME
from evaluation import evaluate_additional_dimensions


class QualityDimensionsTests(unittest.TestCase):
    def test_explicit_tree_conversion_and_finite_quality(self):
        df = pd.DataFrame({CASE: ['a','a','b','b'], ACTIVITY: ['A','B','A','B'],
                           TIME: pd.date_range('2020-01-01', periods=4, freq='h')})
        with patch.object(pm4py, 'discover_process_tree_inductive', wraps=pm4py.discover_process_tree_inductive) as tree, \
             patch.object(pm4py, 'convert_to_petri_net', wraps=pm4py.convert_to_petri_net) as convert:
            model = discover_one(df, noise_threshold=0)['Inductive Miner']
        tree.assert_called_once()
        convert.assert_called_once()
        metrics = evaluate_additional_dimensions(df, *model)
        self.assertEqual(set(metrics), {'simplicity', 'generalization'})
        self.assertAlmostEqual(metrics['generalization'], 1 - 1 / (2 ** .5))
        self.assertEqual(metrics['simplicity'], 1.0)


if __name__ == '__main__':
    unittest.main()
