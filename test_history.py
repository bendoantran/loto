"""Offline regression tests for data preservation and resumable collection."""
import gzip
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import URLError

import history

FIXTURES = Path(__file__).resolve().parent / "tests" / "fixtures"
TEST_ROOT = Path(__file__).resolve().parent / "test-runs"


class Fixture:
    def __init__(self, name):
        self.name = name

    def read_bytes(self):
        return gzip.decompress((FIXTURES / self.name).read_bytes())


MODERN = Fixture("modern.html.gz")
OLD = Fixture("historical.html.gz")
MISSING = Fixture("unavailable.html.gz")
NO_DRAW = Fixture("no-draw.html.gz")


class ParserTests(unittest.TestCase):
    def test_modern_leading_zeros_and_repeated_loto(self):
        result = history.parse_day(MODERN.read_bytes(), "2026-10-21")
        self.assertEqual(result["status"], "saved")
        self.assertEqual(len(result["draws"]), 3)
        first = result["draws"][0]
        self.assertEqual(first["prizes"]["G.ĐB"], ["041493"])
        self.assertEqual(first["loto_by_head"]["9"].count("93"), 2)

    def test_historical_source_anomalies_preserved_and_flagged(self):
        result = history.parse_day(OLD.read_bytes(), "2007-08-18")
        self.assertEqual(len(result["draws"]), 4)
        self.assertEqual(result["status"], "flagged")
        first, _, third, _ = result["draws"]
        self.assertEqual(first["prizes"]["G.ĐB"], ["39842"])
        self.assertEqual(third["prizes"]["G.8"], ["864"])
        self.assertEqual(third["prizes"]["G.7"], ["55"])
        self.assertTrue(third["quality_flags"])

    def test_explicit_unavailable(self):
        result = history.parse_day(MISSING.read_bytes(), "2007-08-17")
        self.assertEqual(result["status"], "unavailable")
        self.assertEqual(result["draws"], [])

    def test_explicit_cancelled_draw_is_not_a_parsing_error(self):
        result = history.parse_day(NO_DRAW.read_bytes(), "2020-04-01")
        self.assertEqual(result["status"], "no_draw")
        self.assertEqual(result["draws"], [])
        self.assertIn("01/04/2020", result["note"])
        with self.assertRaises(ValueError):
            history.parse_day(NO_DRAW.read_bytes(), "2020-04-02")

    def test_wrong_date_and_captcha_are_rejected(self):
        with self.assertRaises(ValueError):
            history.parse_day(MODERN.read_bytes(), "2026-10-14")
        with self.assertRaises(ValueError):
            history.parse_day(b"<html>Please verify you are human</html>", "2026-10-21")


class ResumeTests(unittest.TestCase):
    def setUp(self):
        TEST_ROOT.mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=TEST_ROOT)
        self.root = Path(self.temp.name)
        self.raw = MODERN.read_bytes()

    def tearDown(self):
        assert self.root.resolve().is_relative_to(TEST_ROOT.resolve())
        self.temp.cleanup()

    def raw_for(self, day):
        return self.raw.replace(b"21/10/2026", history.date.fromisoformat(day).strftime("%d/%m/%Y").encode())

    def test_restart_skips_completed_day_and_keeps_exports_unique(self):
        db = history.connect(self.root, "2026-10-21", "2026-10-22")
        with patch.object(history, "fetch", return_value=self.raw) as fetch:
            history.collect(self.root, db, interval=0, limit=1)
            self.assertEqual(fetch.call_count, 1)
        db.close()
        db = history.connect(self.root)
        with patch.object(history, "fetch", return_value=self.raw_for("2026-10-22")) as fetch:
            history.collect(self.root, db, interval=0)
            self.assertEqual(fetch.call_count, 1)
            self.assertIn("22-10-2026", fetch.call_args.args[0])
        self.assertEqual(db.execute("SELECT COUNT(*) FROM days WHERE status='saved'").fetchone()[0], 2)
        with patch.object(history, "fetch") as fetch:
            history.collect(self.root, db, interval=0)
            fetch.assert_not_called()
        lines = (self.root / "years/2026/results.jsonl").read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(lines), 2)
        self.assertEqual(len({json.loads(line)["date"] for line in lines}), 2)
        self.assertEqual(json.loads((self.root / "progress.json").read_text())["state"], "finished")
        db.close()

    def test_connection_outage_then_recovery(self):
        db = history.connect(self.root, "2026-10-21", "2026-10-21")
        clock = [1000.0]
        def wait(seconds, stop_file):
            clock[0] += seconds + 0.1
            return True
        with patch.object(history, "fetch", side_effect=[URLError("offline"), URLError("offline"), self.raw]) as fetch, patch.object(history.time, "time", side_effect=lambda: clock[0]), patch.object(history, "interruptible_wait", side_effect=wait):
            history.collect(self.root, db, interval=0)
        row = db.execute("SELECT * FROM days").fetchone()
        self.assertEqual(fetch.call_count, 3)
        self.assertEqual(row["status"], "saved")
        self.assertEqual(row["attempts"], 3)
        self.assertEqual(row["number_count"], 54)
        db.close()

    def test_offline_stop_and_restart_retries_same_day(self):
        db = history.connect(self.root, "2026-10-21", "2026-10-21")
        def stop_during_retry(seconds, stop_file):
            stop_file.write_text("stop")
            return False
        with patch.object(history, "fetch", side_effect=URLError("offline")), patch.object(history, "interruptible_wait", side_effect=stop_during_retry):
            history.collect(self.root, db, interval=0)
        self.assertEqual(db.execute("SELECT status FROM days").fetchone()[0], "retry")
        self.assertEqual(json.loads((self.root / "progress.json").read_text())["processed_days"], 0)
        (self.root / "STOP").unlink()
        db.execute("UPDATE days SET next_retry=0")
        db.commit()
        with patch.object(history, "fetch", return_value=self.raw):
            history.collect(self.root, db, interval=0)
        self.assertEqual(db.execute("SELECT status FROM days").fetchone()[0], "saved")
        db.close()

    def test_html_cached_before_crash_is_reused(self):
        db = history.connect(self.root, "2026-10-21", "2026-10-21")
        raw_file = self.root / "years/2026/raw/2026-10-21.html.gz"
        raw_file.parent.mkdir(parents=True)
        raw_file.write_bytes(gzip.compress(self.raw))
        with patch.object(history, "fetch") as fetch:
            history.collect(self.root, db, interval=0)
            fetch.assert_not_called()
        self.assertEqual(db.execute("SELECT status FROM days").fetchone()[0], "saved")
        db.close()

    def test_year_boundary_exports_both_years(self):
        db = history.connect(self.root, "2025-12-31", "2026-01-01")
        with patch.object(history, "fetch", side_effect=[self.raw_for("2025-12-31"), self.raw_for("2026-01-01")]):
            history.collect(self.root, db, interval=0)
        for year in (2025, 2026):
            self.assertEqual(len((self.root / f"years/{year}/results.jsonl").read_text(encoding="utf-8").splitlines()), 1)
        self.assertEqual(history.summary(db)["processed_days"], 2)
        db.close()

    def test_duplicate_worker_lock(self):
        with history.WorkerLock(self.root):
            self.assertTrue(history.lock_held(self.root))
            with self.assertRaises(RuntimeError):
                with history.WorkerLock(self.root):
                    pass
        self.assertFalse(history.lock_held(self.root))

    def test_bad_html_is_preserved_for_review(self):
        db = history.connect(self.root, "2026-10-21", "2026-10-21")
        with patch.object(history, "fetch", return_value=b"<html>changed layout</html>"):
            history.collect(self.root, db, interval=0)
        self.assertEqual(db.execute("SELECT status FROM days").fetchone()[0], "review")
        self.assertTrue((self.root / "years/2026/raw/2026-10-21.html.gz").exists())
        self.assertEqual(len((self.root / "years/2026/issues.jsonl").read_text().splitlines()), 1)
        db.close()

    def test_cancelled_draw_checkpoint_and_exports(self):
        db = history.connect(self.root, "2020-04-01", "2020-04-01")
        with patch.object(history, "fetch", return_value=NO_DRAW.read_bytes()):
            history.collect(self.root, db, interval=0)
        summary = history.summary(db)
        self.assertEqual(summary["processed_days"], 1)
        self.assertEqual(summary["no_draw_days"], 1)
        self.assertEqual(summary["review_days"], 0)
        self.assertEqual(summary["years"][0]["state"], "complete")
        record = json.loads((self.root / "years/2020/results.jsonl").read_text(encoding="utf-8"))
        self.assertEqual(record["status"], "no_draw")
        self.assertIn("không mở thưởng", record["note"])
        self.assertEqual((self.root / "years/2020/issues.jsonl").read_text(), "")
        with patch.object(history, "fetch") as fetch:
            history.collect(self.root, db, interval=0)
            fetch.assert_not_called()
        db.close()


if __name__ == "__main__":
    unittest.main()
