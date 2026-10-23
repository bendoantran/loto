import tempfile
import unittest
from pathlib import Path
import numpy as np
from number_prediction.ensemble import weighted_average, ProbabilityStack, chronological_oof
from number_prediction.optimization import TemperatureCalibration, check_development, tune


class EnsembleTests(unittest.TestCase):
    def test_weight_constraints_stack_roundtrip(self):
        p = np.full((30, 4, 100), .01)
        np.testing.assert_allclose(weighted_average(p, [.25] * 4), .01)
        with self.assertRaises(ValueError):
            weighted_average(p, [1, 1, 1, 1])
        obj = ProbabilityStack().fit(p, np.arange(30) % 3)
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "stack.json"
            obj.save(path)
            np.testing.assert_allclose(obj.predict_proba(p), ProbabilityStack.load(path).predict_proba(p))

    def test_chronological_callbacks_and_initial_rows_excluded(self):
        queries = [{"date": f"2020-01-{i:02d}"} for i in range(1, 25)]
        calls = []
        def callback(train, valid):
            self.assertLess(max(queries[i]["date"] for i in train), min(queries[i]["date"] for i in valid))
            calls.append((train, valid))
            return np.full((len(valid), 4, 100), .01)
        indices, p, evidence = chronological_oof(queries, callback)
        self.assertEqual(indices.min(), 6)
        self.assertEqual(len(calls), 3)
        with self.assertRaises(ValueError):
            check_development([{"date": "2025-01-01"}], "2025-01-01")

    def test_calibration_after_training_and_inner_search(self):
        qs = [{"date": f"2020-01-{i:02d}"} for i in range(1, 25)]
        p = np.full((24, 100), .01)
        with self.assertRaises(ValueError):
            TemperatureCalibration().fit(p, np.zeros(24, int), qs, "2020-01-02")
        obj = TemperatureCalibration().fit(p, np.zeros(24, int), qs, "2019-12-31")
        np.testing.assert_allclose(obj.transform(p), .01)
        def evaluate(params, train, valid):
            self.assertLess(max(qs[i]["date"] for i in train), min(qs[i]["date"] for i in valid))
            return p[valid]
        with tempfile.TemporaryDirectory() as temp:
            result = tune(qs, np.arange(24), evaluate, "sqlite:///" + str(Path(temp) / "study.sqlite3"), "smoke", trials=1, family="tree")
            self.assertEqual(result["trials"], 1)
            resumed = tune(qs, np.arange(24), evaluate, "sqlite:///" + str(Path(temp) / "study.sqlite3"), "smoke", trials=1, family="tree")
            self.assertEqual(resumed["trials"], 1, "Resume must not add trials beyond the fixed total budget")
