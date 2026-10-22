import tempfile
import unittest
from pathlib import Path
import numpy as np
from number_prediction.trees import TreeModel
from number_prediction.baselines import align


class TreeTests(unittest.TestCase):
    def test_missing_classes_native_roundtrip_and_dependency(self):
        rng = np.random.default_rng(1729)
        x = rng.normal(size=(120, 5))
        y = np.where(x[:, 0] > 0, 7, 93)
        for family in ("catboost", "xgboost", "lightgbm"):
            with self.subTest(family=family), tempfile.TemporaryDirectory() as temp:
                obj = TreeModel(family, iterations=8, depth=2).fit(x, y)
                p = obj.predict_proba(x)
                self.assertEqual(p.shape, (120, 100))
                self.assertTrue(np.isfinite(p).all())
                self.assertGreater((p.argmax(1) == y).mean(), .8)
                self.assertTrue((p[:, 0] > 0).all())
                folder = Path(temp) / family
                obj.save(folder)
                np.testing.assert_allclose(p, TreeModel.load(folder).predict_proba(x), atol=1e-7)

    def test_single_class_fallback(self):
        for family in ("catboost", "xgboost", "lightgbm"):
            obj = TreeModel(family).fit(np.zeros((3, 2)), np.full(3, 9))
            self.assertEqual(obj.predict_proba(np.zeros((1, 2))).argmax(), 9)

    def test_invalid_probability_contract(self):
        with self.assertRaises(ValueError):
            align(np.ones((1, 2)), [7, 7])
        with self.assertRaises(ValueError):
            align(np.array([[np.nan]]), [0])
