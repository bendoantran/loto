import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from number_prediction.data import canonical, digest
from number_prediction.backtest import verify_policy
from number_prediction.optimization import freeze_policy


ROOT = Path(__file__).resolve().parents[2]


class CLITests(unittest.TestCase):
    def test_entrypoints_and_reserved_test_refusal(self):
        for command in ("snapshot", "train", "predict", "backtest", "benchmark", "package", "experiments", "compare", "select_model", "cadence", "gpu_check", "supervise"):
            result = subprocess.run([sys.executable, str(ROOT / "number_prediction" / (command + ".py")), "--help"], capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr.decode())

    def test_frozen_policy_model_data_and_range(self):
        class Model:
            model_version = "model-v1"
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "policy.json"
            freeze_policy(path, {"model_version": "model-v1", "data_version": "data-v1", "selection_end": "2024-12-31",
                "final_test_start": "2025-01-01", "final_test_end": "2026-10-21", "evaluation": "frozen_weights_updated_past_history"})
            self.assertTrue(verify_policy(path, Model(), "2025-01-01", "2026-10-21", "data-v1"))
            with self.assertRaises(ValueError):
                verify_policy(path, Model(), "2025-01-01", "2026-10-21", "other-data")
            content = json.loads(path.read_text(encoding="utf-8"))
            content["selection_end"] = "2026-01-01"
            path.write_text(json.dumps(content), encoding="utf-8")
            with self.assertRaises(ValueError):
                verify_policy(path, Model(), "2025-01-01", "2026-10-21", "data-v1")
