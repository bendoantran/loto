import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import numpy as np
from number_prediction.recovery import (CheckpointStore, StopRequested, ensure_context,
    exclusive_lock, read_json)


class RecoveryTests(unittest.TestCase):
    def child(self, kind, destination, mode, code=0):
        env = {**os.environ, "OMP_NUM_THREADS": "2", "OPENBLAS_NUM_THREADS": "2", "MKL_NUM_THREADS": "2"}
        result = subprocess.run([sys.executable, "-m", "number_prediction.tests.recovery_worker",
            kind, str(destination), mode], capture_output=True, text=True, encoding="utf-8", env=env, timeout=45)
        self.assertEqual(result.returncode, code, result.stdout + result.stderr)

    def test_abrupt_transformer_restart_restores_stochastic_training(self):
        with tempfile.TemporaryDirectory() as temp:
            full, interrupted = Path(temp) / "full", Path(temp) / "interrupted"
            self.child("transformer", full, "normal")
            self.child("transformer", interrupted, "crash", 23)
            self.child("transformer", interrupted, "resume")
            a, b = np.load(full / "result.npz"), np.load(interrupted / "result.npz")
            self.assertEqual(int(b["resumed"]), 2)
            np.testing.assert_array_equal(a["probabilities"], b["probabilities"])
            np.testing.assert_array_equal(a["losses"], b["losses"])
            import torch
            x = torch.load(full / "final.pt", weights_only=True)
            y = torch.load(interrupted / "final.pt", weights_only=True)
            for name in x:
                self.assertTrue(torch.equal(x[name], y[name]), name)

    def test_abrupt_native_tree_restart(self):
        with tempfile.TemporaryDirectory() as temp:
            for kind in ("catboost", "xgboost", "lightgbm"):
                with self.subTest(kind=kind):
                    full, interrupted = Path(temp) / (kind + "-full"), Path(temp) / (kind + "-interrupted")
                    self.child(kind, full, "normal")
                    self.child(kind, interrupted, "crash", 23)
                    self.child(kind, interrupted, "resume")
                    a, b = np.load(full / "result.npz"), np.load(interrupted / "result.npz")
                    np.testing.assert_allclose(a["probabilities"], b["probabilities"], atol=1e-12, rtol=1e-12)
                    if kind != "catboost":
                        self.assertEqual(int(b["resumed"]), 3)

    def test_atomic_commit_failure_corruption_and_context_guard(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            store = CheckpointStore(root)
            store.commit(lambda p: p.write_bytes(b"committed"), ".bin", {"step": 1})
            def partial(path):
                path.write_bytes(b"partial")
                raise RuntimeError("power failure before pointer commit")
            with self.assertRaises(RuntimeError):
                store.commit(partial, ".bin", {"step": 2})
            path, progress = store.load()
            self.assertEqual(path.read_bytes(), b"committed")
            self.assertEqual(progress["step"], 1)
            path.write_bytes(b"corrupt")
            with self.assertRaisesRegex(ValueError, "hash mismatch"):
                store.load()
            ensure_context(root / "context", {"identities": [("xsmt", "Huế")]})
            ensure_context(root / "context", {"identities": [("xsmt", "Huế")]})
            with self.assertRaisesRegex(ValueError, "context changed"):
                ensure_context(root / "context", {"identities": [("xsmt", "Other")]})

    def test_catboost_corrupt_native_snapshot_fails_without_reset(self):
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
            self.child("catboost", root, "resume", 1)

    def test_kernel_lock_releases_after_process_death(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            code = "from number_prediction.recovery import exclusive_lock; import sys;\nwith exclusive_lock(sys.argv[1]): print('locked', flush=True); sys.stdin.read()"
            child = subprocess.Popen([sys.executable, "-c", code, str(root / "lock")],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            try:
                self.assertEqual(child.stdout.readline().strip(), "locked")
                with self.assertRaisesRegex(RuntimeError, "Another worker"):
                    with exclusive_lock(root / "lock"):
                        pass
            finally:
                child.kill()
                child.communicate(timeout=10)
            with exclusive_lock(root / "lock"):
                self.assertTrue((root / "lock").exists())

    def test_ensemble_reuses_committed_children_after_stop(self):
        from number_prediction.synthetic import generate
        from number_prediction.features import FeatureBuilder, queries_for
        from number_prediction.pipeline import Predictor
        from number_prediction.trees import TreeModel
        draws = generate(days=35, dependency="province")
        builder = FeatureBuilder(draws, [(r, p) for r in ("xsmn", "xsmt") for p in ("A", "B")], windows=(5,), lags=1)
        qs, y = queries_for(draws)
        params = {"iterations": 3, "depth": 2, "d_model": 16, "nhead": 2, "layers": 1,
                  "sequence_length": 8, "epochs": 1, "dropout": 0}
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            def stop():
                if (root / "base-catboost" / "fitted" / "latest.json").exists():
                    raise StopRequested("intentional stop after first base fit")
            with self.assertRaises(StopRequested):
                Predictor("average", builder, params=params).fit(qs, y, root, stop_check=stop)
            original = TreeModel.fit
            def guarded(obj, *args, **kwargs):
                self.assertNotEqual(obj.params["family"], "catboost", "completed child was unnecessarily fitted again")
                return original(obj, *args, **kwargs)
            with patch.object(TreeModel, "fit", guarded):
                obj = Predictor("average", builder, params=params).fit(qs, y, root)
            query = {**qs[-1], "date": "2010-03-01", "origin": "2010-03-01"}
            np.testing.assert_allclose(obj.predict([query]).sum(1), 1, atol=1e-6)

    def test_supervisor_bounds_retries_and_respects_stop(self):
        from number_prediction.supervise import supervise
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            command = [sys.executable, "-c", "raise SystemExit(4)"]
            self.assertEqual(supervise(command, root, max_retries=1, retry_seconds=0), 78)
            self.assertEqual(read_json(root / "supervisor-state.json")["attempts"], 2)
            self.assertEqual(supervise(command, root, max_retries=1, retry_seconds=0), 78)
            self.assertEqual(read_json(root / "supervisor-state.json")["attempts"], 2)
            stopped = root / "intentional"
            stopped.mkdir()
            (stopped / "STOP").touch()
            self.assertEqual(supervise(command, stopped, retry_seconds=0), 75)
            self.assertEqual(read_json(stopped / "supervisor-state.json")["attempts"], 0)

    def test_cli_and_grid_resume_after_result_commit_before_publish(self):
        from argparse import Namespace
        from number_prediction.data import PRIZES, canonical, digest
        from number_prediction.experiments import execute
        from number_prediction.recovery import StopControl, atomic_json, verify_completed_run
        from number_prediction.synthetic import generate
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            snapshot = root / "snapshot"
            snapshot.mkdir()
            records = []
            for draw in generate(days=60):
                for prize in PRIZES:
                    value = draw[prize]
                    if value is not None:
                        records.append({**{k: draw[k] for k in ("date", "region", "province")},
                            "prize": prize, "number": f"{value:06d}" if prize == PRIZES[1] else f"{value:02d}",
                            "loto": f"{value:02d}"})
            raw = b"\n".join(canonical(r) for r in records) + b"\n"
            (snapshot / "records.jsonl").write_bytes(raw)
            manifest = {"rows": len(records), "records_sha256": digest(raw),
                "identities": [[r, p] for r in ("xsmn", "xsmt") for p in ("A", "B")]}
            atomic_json(snapshot / "manifest.json", {**manifest, "data_version": digest(canonical(manifest))})
            params = root / "pilot.json"
            params.write_bytes(Path(__file__).parents[1].joinpath("pilot.json").read_bytes())
            destination = root / "job"
            command = [sys.executable, str(Path(__file__).parents[1] / "train.py"), "--data", str(snapshot),
                "--out", str(destination), "--family", "xgboost", "--prize", "both", "--params", str(params),
                "--train-start", "2010-01-01", "--train-end", "2010-01-20", "--calibration-end", "2010-02-05",
                "--validation-end", "2010-02-20", "--checkpoint-every", "1"]
            crash = "import os,sys; import number_prediction.train as t; t.publish_directory=lambda *a: os._exit(23); sys.argv=sys.argv[1:]; t.main()"
            result = subprocess.run([sys.executable, "-c", crash, *command[1:]], capture_output=True, timeout=30)
            self.assertEqual(result.returncode, 23, result.stderr.decode())
            self.assertFalse((destination / "xgboost-prize0").exists())
            self.assertTrue((destination / ".recovery/xgboost-prize0/result/latest.json").exists())
            args = Namespace(out=root, max_jobs=1)
            jobs = [{"label": "job", "command": command}]
            execute(args, {"synthetic": True}, jobs, StopControl(root / "STOP"))
            verify_completed_run(destination)
            native = destination / "xgboost-prize0/model/model.ubj"
            modified = native.stat().st_mtime_ns
            execute(args, {"synthetic": True}, jobs, StopControl(root / "STOP"))
            self.assertEqual(native.stat().st_mtime_ns, modified)
            (destination / "STOP").touch()
            stopped = subprocess.run([*command, "--resume"], capture_output=True, timeout=30)
            self.assertEqual(stopped.returncode, 75, stopped.stderr.decode())
            self.assertTrue((destination / "STOP").exists())
            (destination / "STOP").unlink()  # Only this test's own explicit stop is cleared.
            changed = [*command, "--resume"]
            changed[changed.index("--train-end") + 1] = "2010-01-21"
            refused = subprocess.run(changed, capture_output=True, timeout=30)
            self.assertNotEqual(refused.returncode, 0)
            self.assertIn(b"Run context changed", refused.stderr)
            self.assertEqual(native.stat().st_mtime_ns, modified)
            native.write_bytes(b"damaged native model")
            with self.assertRaisesRegex(ValueError, "model file changed"):
                execute(args, {"synthetic": True}, jobs, StopControl(root / "STOP"))


if __name__ == "__main__":
    unittest.main()
