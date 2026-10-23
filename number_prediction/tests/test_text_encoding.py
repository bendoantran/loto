"""Check Unicode persistence and redirected CLI output without relying on locale."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import numpy as np
from number_prediction.features import FeatureBuilder
from number_prediction.pipeline import Predictor


class TextEncodingTests(unittest.TestCase):
    def test_model_and_schedule_reads_explicitly_use_utf8(self):
        from number_prediction.schedules import Schedule
        history = [{"date": "2007-08-18", "region": "xsmt", "province": "Huế", "G.8": 9, "G.ĐB": 43}]
        query = {"date": "2007-08-19", "region": "xsmt", "province": "Huế"}
        builder = FeatureBuilder(history, [("xsmt", "Huế")])
        model = Predictor("uniform", builder).fit([history[0]], np.array([43]))
        original = Path.read_text
        observed = []

        def read_utf8(path, *args, **kwargs):
            self.assertEqual(kwargs.get("encoding"), "utf-8", str(path))
            observed.append(path.name)
            return original(path, *args, **kwargs)

        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary) / "model"
            model.save(folder, {"selection_end": "2007-08-18"})
            with patch.object(Path, "read_text", read_utf8):
                loaded = Predictor.load(folder)
                self.assertEqual(Schedule().resolve("Huế"), "xsmt")
            self.assertEqual(loaded.builder.identities, [("xsmt", "Huế")])
            np.testing.assert_allclose(loaded.predict([query]), .01)
            self.assertIn("state.json", observed)
            self.assertIn("schedules.json", observed)

    def test_cli_help_overrides_redirected_cp1252_encoding(self):
        root = Path(__file__).resolve().parents[2]
        environment = {**os.environ, "PYTHONIOENCODING": "cp1252", "PYTHONUTF8": "0"}
        result = subprocess.run([sys.executable, str(root / "number_prediction/train.py"), "--help"],
                                env=environment, capture_output=True, check=True)
        self.assertIn("G.ĐB", result.stdout.decode("utf-8"))
