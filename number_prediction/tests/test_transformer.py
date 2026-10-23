import tempfile
import unittest
from pathlib import Path
import numpy as np
import torch
from number_prediction.transformer import TransformerModel, sequence_inputs
from number_prediction.features import FeatureBuilder
from number_prediction.tests.test_data import row


class TransformerTests(unittest.TestCase):
    def test_causality_padding_empty_history_and_roundtrip(self):
        builder = FeatureBuilder([row(), row("2007-08-19")], [("xsmn", "A")])
        qs = [{"date": "2007-08-18", "region": "xsmn", "province": "A"},
              {"date": "2007-08-20", "region": "xsmn", "province": "A"}]
        inputs = sequence_inputs(builder, qs, 8)
        obj = TransformerModel(1, d_model=16, nhead=2, layers=1, sequence_length=8, dropout=0)
        obj.model.eval()
        original = obj.predict_proba(inputs)
        mutated = [x.copy() for x in inputs]
        mutated[0][:, 5:, :2] = 55
        np.testing.assert_allclose(original, obj.predict_proba(mutated), atol=1e-7)
        obj.fit(inputs, np.array([[0, 9], [-1, 9]]), (inputs, np.array([[0, 9], [-1, 9]])), epochs=2)
        with tempfile.TemporaryDirectory() as temp:
            obj.save(Path(temp) / "transformer")
            np.testing.assert_allclose(obj.predict_proba(inputs), TransformerModel.load(Path(temp) / "transformer").predict_proba(inputs), atol=1e-7)
        self.assertTrue(np.isfinite(original).all())
