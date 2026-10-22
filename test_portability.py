"""Regression tests for migration, cross-process locking, and quiet monitoring."""
import contextlib
import gzip
import hashlib
import io
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path, PurePosixPath
from unittest.mock import patch

import history
from tools.restore_snapshot import restore
from tools import monitor
from tools.install_service import units

REPO = Path(__file__).resolve().parent
TEST_ROOT = REPO / "test-runs"


class PortabilityTests(unittest.TestCase):
    def setUp(self):
        TEST_ROOT.mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=TEST_ROOT)
        self.root = Path(self.temp.name)

    def tearDown(self):
        assert self.root.resolve().is_relative_to(TEST_ROOT.resolve())
        self.temp.cleanup()

    def test_real_cross_process_exclusive_lock(self):
        code = "import sys;from pathlib import Path;import history;\nwith history.WorkerLock(Path(sys.argv[1])):\n print('READY',flush=True);sys.stdin.readline()"
        kwargs = {"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {}
        process = subprocess.Popen([sys.executable, "-c", code, str(self.root)], cwd=REPO,
                                   stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                   text=True, encoding="utf-8", **kwargs)
        try:
            self.assertEqual(process.stdout.readline().strip(), "READY")
            self.assertTrue(history.lock_held(self.root))
            process.communicate("release\n", timeout=10)
            self.assertEqual(process.returncode, 0)
            self.assertFalse(history.lock_held(self.root))
        finally:
            if process.poll() is None:
                process.kill()
                process.communicate()

    def make_snapshot(self):
        source = self.root / "source"
        db = history.connect(source, "2026-10-21", "2026-10-21")
        history.write_progress(source, db, "stopped")
        db.close()
        raw = (source / "history.sqlite3").read_bytes()
        compressed = gzip.compress(raw)
        folder = source / "snapshots"
        folder.mkdir()
        (folder / "history.sqlite3.gz").write_bytes(compressed)
        (folder / "monitor-state.json").write_text('{}', encoding="utf-8")
        manifest = {"start": "2026-10-21", "end": "2026-10-21", "checked_dates": 1,
                    "status_counts": {"pending": 1}, "database_sha256": hashlib.sha256(raw).hexdigest(),
                    "database_gzip_sha256": hashlib.sha256(compressed).hexdigest()}
        (folder / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        return source

    def test_snapshot_restores_and_never_overwrites_existing_work(self):
        source = self.make_snapshot()
        destination = self.root / "destination"
        result = restore(source, destination)
        self.assertEqual(result["state"], "restored")
        with contextlib.closing(sqlite3.connect(destination / "history.sqlite3")) as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM days").fetchone()[0], 1)
            db.execute("UPDATE days SET attempts=7")
            db.commit()
        self.assertEqual(restore(source, destination)["state"], "existing_checkpoint_preserved")
        with contextlib.closing(sqlite3.connect(destination / "history.sqlite3")) as db:
            self.assertEqual(db.execute("SELECT attempts FROM days").fetchone()[0], 7)

    def test_bad_snapshot_hash_is_rejected_before_database_install(self):
        source = self.make_snapshot()
        with (source / "snapshots/history.sqlite3.gz").open("ab") as f:
            f.write(b"changed")
        destination = self.root / "destination"
        with self.assertRaises(ValueError):
            restore(source, destination)
        self.assertFalse((destination / "history.sqlite3").exists())

    def test_monitor_reports_completion_once_then_stays_quiet(self):
        db = history.connect(self.root, "2026-10-21", "2026-10-21")
        db.execute("UPDATE days SET status='no_draw'")
        db.commit()
        history.write_progress(self.root, db, "finished")
        db.close()
        with contextlib.redirect_stdout(io.StringIO()):
            first = monitor.check(self.root, notify=False, repair=False)
            second = monitor.check(self.root, notify=False, repair=False)
        self.assertIn("Full collection checked", first)
        self.assertIsNone(second)
        events = (self.root / "monitor-events.jsonl").read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(events), 1)

    def test_monitor_respects_stop_and_does_not_restart(self):
        db = history.connect(self.root, "2026-10-21", "2026-10-21")
        history.write_progress(self.root, db, "running")
        db.close()
        (self.root / "STOP").write_text("stop")
        with patch.object(monitor, "start") as start:
            self.assertIsNone(monitor.check(self.root, notify=False, repair=True))
            start.assert_not_called()

    def test_user_units_have_resume_stop_and_retry_contract(self):
        generated = units(PurePosixPath('/home/example user/Documents/xoso'), PurePosixPath('/home/example user/Documents/xoso'), PurePosixPath('/usr/bin/python3'))
        self.assertIn('Restart=on-failure', generated['loto-history.service'])
        self.assertIn('ExecCondition=', generated['loto-history.service'])
        self.assertIn('KillSignal=SIGINT', generated['loto-history.service'])
        self.assertNotIn('ExecStop=', generated['loto-history.service'])
        self.assertIn('OnUnitActiveSec=30min', generated['loto-monitor.timer'])
        self.assertIn('"/home/example user/Documents/xoso/history.py"', generated['loto-history.service'])

    def test_every_frozen_manifest_asset_is_tracked_in_git(self):
        if not (REPO / '.git').exists():
            self.skipTest('Git checkout metadata is not present')
        tracked = set(subprocess.check_output(['git', 'ls-files', '-z'], cwd=REPO).decode('utf-8').split('\0'))
        manifest = json.loads((REPO / 'snapshots/manifest.json').read_text(encoding='utf-8'))
        self.assertEqual(set(manifest['files']) - tracked, set())


if __name__ == "__main__":
    unittest.main()
