import errno
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from number_prediction import server
from number_prediction.recovery import CheckpointStore, atomic_json, read_json


class ServerTests(unittest.TestCase):
    @unittest.skipIf(os.name == "nt", "Linux shell launcher")
    def test_launcher_overrides_ascii_locale_for_unicode_paths(self):
        with tempfile.TemporaryDirectory(prefix="loto Huế ") as temp:
            root = Path(temp)
            (root / ".venv/bin").mkdir(parents=True)
            (root / ".venv/loto-setup-complete.json").write_text("{}")
            (root / ".venv/bin/python").symlink_to(sys.executable)
            shutil.copy2(Path(server.__file__).parent / "server_bundle/loto", root / "loto")
            env = {**os.environ, "LC_ALL": "C", "PYTHONUTF8": "0", "PYTHONCOERCECLOCALE": "0"}
            code = "import pathlib,sys; p=pathlib.Path('G.ĐB.txt'); p.write_text('00',encoding='utf-8'); print(sys.flags.utf8_mode); print(str(pathlib.Path.cwd()))"
            result = subprocess.run(["bash", str(root / "loto"), "python", "-c", code],
                cwd=root, env=env, capture_output=True, text=True, encoding="utf-8", timeout=15)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertTrue(result.stdout.startswith("1\n"))
            self.assertIn("Huế", result.stdout)
            self.assertEqual((root / "G.ĐB.txt").read_text(encoding="utf-8"), "00")

    def test_opencl_selection_matches_cuda_uuid_and_rejects_wrong_gpu(self):
        devices = [{"platform_id": 0, "device_id": 0, "name": "Other GPU", "uuid": "other"},
                   {"platform_id": 1, "device_id": 2, "name": "Allocated GPU", "uuid": "allocated"}]
        with patch.object(server, "opencl_devices", return_value=devices), patch("torch.cuda.is_available", return_value=True), \
             patch("torch.cuda.get_device_properties", return_value=SimpleNamespace(uuid="GPU-allocated")), \
             patch.dict(os.environ, {}, clear=True):
            self.assertEqual(server.gpu_selection()["gpu_device_id"], 2)
            with patch.dict(os.environ, {"LOTO_OPENCL_PLATFORM": "0", "LOTO_OPENCL_DEVICE": "0"}):
                with self.assertRaisesRegex(RuntimeError, "differs"):
                    server.gpu_selection()
            with patch.dict(os.environ, {"LOTO_OPENCL_PLATFORM": "1"}):
                with self.assertRaisesRegex(ValueError, "both"):
                    server.gpu_selection()

    def test_disk_full_during_commit_preserves_previous_checkpoint(self):
        with tempfile.TemporaryDirectory() as temp:
            store = CheckpointStore(temp)
            store.commit(lambda p: p.write_bytes(b"good"), ".bin", {"rounds": 3})
            def full(path):
                path.write_bytes(b"partial")
                raise OSError(errno.ENOSPC, "No space left on device")
            with self.assertRaises(OSError):
                store.commit(full, ".bin", {"rounds": 4})
            path, progress = store.load()
            self.assertEqual((path.read_bytes(), progress["rounds"]), (b"good", 3))
            # Also fail at the durability boundary after writing a new payload.
            with patch("number_prediction.recovery.os.fsync", side_effect=OSError(errno.ENOSPC, "full")):
                with self.assertRaises(OSError):
                    store.commit(lambda p: p.write_bytes(b"not durable"), ".bin", {"rounds": 4})
            self.assertEqual(store.load()[1]["rounds"], 3)

    def test_transfer_verifier_rejects_damage_and_external_symlinks(self):
        from number_prediction.server_bundle.verify_bundle import verify
        from number_prediction.recovery import file_hash
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "data").write_bytes(b"00 G.\xc4\x90B")
            atomic_json(root / "bundle-manifest.json", {"data_version": "test", "files": {"data": {"sha256": file_hash(root / "data")}}})
            self.assertEqual(verify(root)["verified_files"], 1)
            (root / "data").write_bytes(b"broken")
            with self.assertRaisesRegex(ValueError, "checksum"):
                verify(root)
            (root / "data").unlink()
            if os.name != "nt":
                (root / "data").symlink_to("/etc/passwd")
                with self.assertRaisesRegex(ValueError, "unsafe"):
                    verify(root)

    @unittest.skipIf(os.name == "nt", "POSIX detached-session acceptance")
    def test_detached_launch_stop_explicit_resume_and_duplicate_guard(self):
        with tempfile.TemporaryDirectory(prefix="loto space Huế ") as temp:
            root = Path(temp)
            source = Path(server.__file__).parent
            shutil.copytree(source, root / "number_prediction", ignore=shutil.ignore_patterns(
                ".venv*", "datasets", "runs", "artifacts", "reports", "__pycache__"))
            with patch.object(server, "ROOT", root), patch.object(server, "DATA", root / "snapshot"), patch.object(server, "doctor", return_value={"passed": True}):
                folder = server.prepare("small", "cpu")
                output = root / "number_prediction/runs/small"
                code = ("import os,pathlib,sys,time; p=pathlib.Path(sys.argv[2]); p.mkdir(exist_ok=True); "
                    "(p/'ready').write_text(str(os.getsid(0))); "
                    "exec(\"while not (p/'STOP').exists(): time.sleep(.02)\"); sys.exit(75)")
                atomic_json(folder / "command.json", [sys.executable, "-c", code, "--out", str(output)])
                processes = []
                try:
                    for resume in (False, True):
                        result = server.launch(folder, resume=resume)
                        processes.append(result["pid"])
                        deadline = time.monotonic() + 15
                        while not (output / "ready").exists() and time.monotonic() < deadline:
                            time.sleep(.02)
                        self.assertTrue((output / "ready").exists())
                        self.assertNotEqual(int((output / "ready").read_text()), os.getsid(0))
                        with self.assertRaisesRegex(RuntimeError, "live"):
                            server.launch(folder)
                        _, supervisor = server.state_paths(folder)
                        atomic_json(output / "STOP", {"test": True})
                        deadline = time.monotonic() + 15
                        while server.locked(supervisor / "supervisor.lock") and time.monotonic() < deadline:
                            time.sleep(.02)
                        self.assertFalse(server.locked(supervisor / "supervisor.lock"))
                        state = read_json(supervisor / "supervisor-state.json")
                        self.assertEqual((state["state"], state["attempts"]), ("stopped", 1))
                        (output / "ready").unlink()
                    self.assertTrue((folder / "supervisor-0/supervisor-state.json").exists())
                    self.assertTrue((folder / "supervisor-1/supervisor-state.json").exists())
                    with self.assertRaisesRegex(RuntimeError, "STOP"):
                        server.launch(folder)
                finally:
                    (output / "STOP").touch()
                    for pid in processes:
                        try:
                            os.waitpid(pid, 0)
                        except ChildProcessError:
                            pass

    def test_prepare_does_not_train_and_refuses_name_reuse_or_traversal(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(server, "ROOT", Path(temp)):
            base = Path(temp) / "number_prediction"
            base.mkdir()
            atomic_json(base / "pilot.json", {"model": {"iterations": 8, "epochs": 1}})
            folder = server.prepare("safe", "cpu")
            self.assertFalse((base / "runs/safe").exists())
            command = read_json(folder / "command.json")
            self.assertIn("2007-12-31", command)
            self.assertNotIn("2025-01-01", command)
            with self.assertRaises(FileExistsError):
                server.prepare("safe", "cpu")
            with self.assertRaises(ValueError):
                server.prepare("../unsafe", "cpu")
