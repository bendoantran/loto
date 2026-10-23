"""Explicit opt-in GPU tests: eight boosting rounds or one tiny Transformer epoch."""
import os
import re
import signal
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
import numpy as np


@unittest.skipUnless(os.environ.get("LOTO_GPU_TESTS") == "1", "Set LOTO_GPU_TESTS=1 explicitly on a CUDA host")
class GPURecoveryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import torch
        if not torch.cuda.is_available():
            raise RuntimeError("GPU tests requested, but CUDA is unavailable; no CPU fallback")

    def child(self, kind, destination, mode, expected=0):
        env = {**os.environ, "CUBLAS_WORKSPACE_CONFIG": ":4096:8", "OMP_NUM_THREADS": "2",
               "OPENBLAS_NUM_THREADS": "2", "MKL_NUM_THREADS": "2", "NUMEXPR_NUM_THREADS": "2"}
        result = subprocess.run([sys.executable, "-m", "number_prediction.tests.recovery_worker",
            kind, str(destination), mode, "cuda"], capture_output=True, text=True, encoding="utf-8", env=env, timeout=60)
        self.assertEqual(result.returncode, expected, result.stdout + result.stderr)

    def test_transformer_gpu_amp_batch_recovery(self):
        import torch
        with tempfile.TemporaryDirectory() as temp:
            full, interrupted = Path(temp) / "full", Path(temp) / "interrupted"
            self.child("transformer", full, "normal")
            self.child("transformer", interrupted, "crash", 23)
            self.child("transformer", interrupted, "resume")
            a, b = np.load(full / "result.npz"), np.load(interrupted / "result.npz")
            self.assertEqual(int(b["resumed"]), 2)
            self.assertTrue(bool(b["mixed_precision"]))
            self.assertTrue(str(b["training_device"]).startswith("cuda"))
            np.testing.assert_allclose(a["probabilities"], b["probabilities"], atol=1e-6, rtol=1e-5)
            np.testing.assert_allclose(a["losses"], b["losses"], atol=1e-5, rtol=1e-5)
            x = torch.load(full / "final.pt", weights_only=True, map_location="cpu")
            y = torch.load(interrupted / "final.pt", weights_only=True, map_location="cpu")
            for name in x:
                torch.testing.assert_close(x[name], y[name], atol=1e-6, rtol=1e-5)

    def test_xgboost_and_lightgbm_gpu_round_recovery(self):
        with tempfile.TemporaryDirectory() as temp:
            for kind in ("xgboost", "lightgbm"):
                with self.subTest(kind=kind):
                    full, interrupted = Path(temp) / (kind + "-full"), Path(temp) / (kind + "-interrupted")
                    self.child(kind, full, "normal")
                    self.child(kind, interrupted, "crash", 23)
                    self.child(kind, interrupted, "resume")
                    a, b = np.load(full / "result.npz"), np.load(interrupted / "result.npz")
                    self.assertEqual(int(b["resumed"]), 3)
                    self.assertIn(str(b["training_device"]), ("gpu", "cuda:0", "cuda"))
                    np.testing.assert_allclose(a["probabilities"], b["probabilities"], atol=1e-6, rtol=1e-5)

    def test_catboost_gpu_completed_native_snapshot_reload(self):
        # GPU callbacks are unavailable. This verifies a completed native snapshot,
        # not an unmeasured mid-fit GPU interruption.
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp) / "catboost"
            self.child("catboost", folder, "normal")
            expected = np.load(folder / "result.npz")["probabilities"].copy()
            self.assertGreater((folder / "checkpoint/native.snapshot").stat().st_size, 0)
            self.child("catboost", folder, "resume")
            actual = np.load(folder / "result.npz")
            self.assertEqual(str(actual["training_device"]), "gpu")
            np.testing.assert_allclose(expected, actual["probabilities"], atol=1e-6, rtol=1e-5)

    def test_catboost_gpu_rejects_damaged_native_snapshot(self):
        from number_prediction.recovery import CheckpointStore
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.child("catboost", root, "normal")
            result = (root / "result.npz").read_bytes()
            (root / "checkpoint/native.snapshot").write_bytes(b"damaged native snapshot")
            self.child("catboost", root, "resume", 1)
            self.assertTrue((root / "checkpoint/invalid-snapshot.json").exists())
            backup = CheckpointStore(root / "checkpoint/resume-evidence").load()[0]
            self.assertEqual(backup.read_bytes(), b"damaged native snapshot")
            self.assertEqual((root / "result.npz").read_bytes(), result)

    @unittest.skipIf(os.name == "nt", "POSIX process pause/kill test")
    def test_catboost_gpu_midfit_native_snapshot_after_sigkill(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            folder = root / "fit"
            command = [sys.executable, "-m", "number_prediction.tests.recovery_worker",
                       "catboost-midfit", str(folder), "normal", "cuda"]
            observed, paused = None, False
            with (root / "killed.log").open("w", encoding="utf-8") as log:
                child = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT)
                deadline = time.monotonic() + 45
                try:
                    while child.poll() is None and time.monotonic() < deadline:
                        snapshot = folder / "checkpoint/native.snapshot"
                        metrics = folder / "checkpoint/native-log/learn_error.tsv"
                        if metrics.exists():
                            lines = metrics.read_text(encoding="utf-8").strip().splitlines()
                            if len(lines) > 1:
                                iteration = int(lines[-1].split("\t")[0])
                                if not paused and iteration < 6:
                                    # Simulate OS preemption so the one-second native
                                    # snapshot timer expires within only eight rounds.
                                    child.send_signal(signal.SIGSTOP)
                                    time.sleep(1.2)
                                    child.send_signal(signal.SIGCONT)
                                    paused = True
                                if snapshot.exists() and snapshot.stat().st_size and iteration < 7:
                                    observed = iteration
                                    child.kill()
                                    break
                        time.sleep(.002)
                finally:
                    if child.poll() is None:
                        child.kill()
                    child.wait(timeout=15)
            self.assertIsNotNone(observed, "No partial native snapshot observed; do not claim mid-fit recovery")
            self.assertEqual(child.returncode, -signal.SIGKILL)
            resumed = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", timeout=60)
            self.assertEqual(resumed.returncode, 0, resumed.stdout + resumed.stderr)
            match = re.search(r"Restore #(\d+) trees from progress", resumed.stdout + resumed.stderr)
            self.assertIsNotNone(match, "Native CatBoost did not report restoring partial progress")
            self.assertGreater(int(match[1]), 0)
            self.assertLess(int(match[1]), 8)
            result = np.load(folder / "result.npz")
            self.assertEqual(int(result["trees"]), 8)
            self.assertEqual(str(result["training_device"]), "gpu")
            self.assertEqual(result["probabilities"].shape, (128, 100))
            self.assertTrue(np.isfinite(result["probabilities"]).all())
            np.testing.assert_allclose(result["probabilities"].sum(1), 1, atol=1e-6)

    def test_gpu_native_packages_load_for_cpu_inference(self):
        from number_prediction.trees import TreeModel
        from number_prediction.transformer import TransformerModel
        with tempfile.TemporaryDirectory() as temp:
            for kind in ("catboost", "xgboost", "lightgbm", "transformer"):
                with self.subTest(kind=kind):
                    folder = Path(temp) / kind
                    self.child(kind, folder, "normal")
                    expected = np.load(folder / "result.npz")["probabilities"]
                    rng = np.random.default_rng(71)
                    if kind == "transformer":
                        sequence = rng.integers(1, 100, (32, 8, 3))
                        sequence[:, 0, :2], sequence[:, :, 2] = 102, np.arange(8)
                        inputs = [sequence, np.full(32, 7), np.zeros(32, dtype=int), np.arange(32) % 2,
                                  np.column_stack((np.arange(32), np.ones(32, dtype=int)))]
                        model = TransformerModel.load(folder / "native", device="cpu")
                        self.assertEqual(next(model.model.parameters()).device.type, "cpu")
                        actual = model.predict_proba(inputs)
                    else:
                        inputs = rng.normal(size=(128, 6))
                        model = TreeModel.load(folder / "native")
                        actual = model.predict_proba(inputs)
                    np.testing.assert_allclose(expected, actual, atol=1e-6, rtol=1e-5)
                    np.testing.assert_allclose(actual.sum(1), 1, atol=1e-6)


if __name__ == "__main__":
    unittest.main()
