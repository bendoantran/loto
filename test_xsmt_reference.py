"""Assessment-tool tests only; these do not implement an XSMT collector."""
import gzip
import hashlib
import json
import shutil
import tempfile
import unittest
from pathlib import Path

import history
from tools.check_xsmt_benchmark import check

REPO = Path(__file__).resolve().parent
TEST_ROOT = REPO / "test-runs"


class XsmtReferenceTests(unittest.TestCase):
    def setUp(self):
        TEST_ROOT.mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=TEST_ROOT)
        self.root = Path(self.temp.name)
        self.reference = json.loads((REPO / "reference/xsmt/expected.json").read_text(encoding="utf-8"))

    def tearDown(self):
        assert self.root.resolve().is_relative_to(TEST_ROOT.resolve())
        self.temp.cleanup()

    def make_candidate(self, case="pilot"):
        # A test-only known-good output assembled from frozen source references.
        # The Kubuntu assignment must fetch and implement real XSMT collection itself.
        expected = {d: r for d, r in self.reference["days"].items() if (d >= "2026-10-16") == (case == "pilot")}
        db = history.connect(self.root, min(expected), max(expected))
        db.execute("INSERT INTO settings(key,value) VALUES ('region','xsmt')")
        for day, record in expected.items():
            relative = f"years/{day[:4]}/raw/{day}.html.gz"
            raw_path = self.root / relative
            raw_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(REPO / record["raw_path"], raw_path)
            payload = {k: record[k] for k in ("status", "draws", "flags")}
            db.execute("""UPDATE days SET status='saved',source_url=?,fetched_at=?,sha256=?,raw_path=?,payload=?,draw_count=?,number_count=? WHERE date=?""",
                       (record["source_url"], record["fetched_at_utc"], record["raw_sha256"], relative,
                        json.dumps(payload, ensure_ascii=False), record["draw_count"], record["number_count"], day))
        db.commit()
        for year in sorted({int(d[:4]) for d in expected}):
            history.export_year(self.root, db, year)
        history.write_progress(self.root, db, "finished")
        db.close()

    def test_frozen_source_hashes_and_loto_are_consistent(self):
        region = self.reference["region_snapshot"]
        raw = gzip.decompress((REPO / region["raw_path"]).read_bytes())
        self.assertEqual(hashlib.sha256(raw).hexdigest(), region["raw_sha256"])
        for day, record in self.reference["days"].items():
            raw = gzip.decompress((REPO / record["raw_path"]).read_bytes())
            self.assertEqual(hashlib.sha256(raw).hexdigest(), record["raw_sha256"])
            self.assertEqual(history.parse_day(raw, day)["draws"], record["draws"])

    def test_grader_accepts_the_exact_pilot(self):
        self.make_candidate()
        self.assertEqual(check(self.root)["winning_numbers"], 306)

    def test_grader_accepts_year_boundary_exports(self):
        self.make_candidate("year-boundary")
        result = check(self.root, "year-boundary")
        self.assertEqual((result["dates"], result["province_date_draws"], result["winning_numbers"]), (2, 5, 90))

    def test_grader_rejects_modified_csv_numbers(self):
        self.make_candidate()
        path = self.root / "years/2026/prizes.csv"
        text = path.read_text(encoding="utf-8-sig")
        path.write_text(text.replace(",G.8,1,55,55,", ",G.8,1,54,54,", 1), encoding="utf-8-sig")
        with self.assertRaises(ValueError):
            check(self.root)

    def test_grader_rejects_the_wrong_region_checkpoint(self):
        self.make_candidate()
        db = history.connect(self.root)
        db.execute("UPDATE settings SET value='xsmn' WHERE key='region'")
        db.commit()
        db.close()
        with self.assertRaises(ValueError):
            check(self.root)


if __name__ == "__main__":
    unittest.main()
