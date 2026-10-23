import csv
import gzip
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
import numpy as np
from number_prediction.data import day_index, validate_row, eligibility, deduplicate, observations, read_external, make_snapshot, load_snapshot, digest
from number_prediction.features import FeatureBuilder, queries_for
from number_prediction.baselines import Baseline
from number_prediction.evaluation import metrics, chronological_folds


def row(day="2007-08-18", province="A", region="xsmn", g8=0, db=9):
    return {"date": day, "region": region, "province": province, "G.8": g8, "G.ĐB": db}


class DataTests(unittest.TestCase):
    def test_immutable_snapshot_evidence_and_tamper_detection(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "collector"
            folder = root / "years" / "2007"
            (folder / "raw").mkdir(parents=True)
            raw = b"synthetic raw evidence, not a live scrape"
            (folder / "raw" / "2007-08-18.html.gz").write_bytes(gzip.compress(raw))
            db = sqlite3.connect(root / "history.sqlite3")
            db.execute("CREATE TABLE settings(key TEXT,value TEXT)")
            db.executemany("INSERT INTO settings VALUES (?,?)", [("region", "xsmt"), ("start", "2007-08-18"), ("end", "2007-08-18")])
            db.commit()
            db.close()
            url = "https://xosodaiphat.com/xsmt-18-08-2007.html"
            record = {"date": "2007-08-18", "source_url": url, "status": "saved", "sha256": digest(raw),
                      "raw_path": "years/2007/raw/2007-08-18.html.gz", "draws": [{"province": "A", "prizes": {"G.8": ["09"], "G.ĐB": ["000001"]}, "quality_flags": []}]}
            (folder / "results.jsonl").write_text(json.dumps(record) + "\n", encoding="utf-8")
            with (folder / "prizes.csv").open("w", newline="", encoding="utf-8") as stream:
                writer = csv.writer(stream)
                writer.writerow(["date", "weekday", "province", "prize", "position", "number", "loto", "quality_flags", "source_url"])
                for prize, number in (("G.8", "09"), ("G.ĐB", "000001")):
                    writer.writerow(["2007-08-18", "Saturday", "A", prize, "1", number, number[-2:], "", url])
            before = (folder / "prizes.csv").read_bytes()
            destination = Path(temp) / "snapshot"
            m = make_snapshot([{"root": root, "region": "xsmt"}], destination)
            rows, loaded = load_snapshot(destination)
            self.assertEqual(len(rows), 2)
            self.assertEqual(m["data_version"], loaded["data_version"])
            self.assertEqual(before, (folder / "prizes.csv").read_bytes())
            with self.assertRaises(FileExistsError):
                make_snapshot([{"root": root, "region": "xsmt"}], destination)
            for evidence in (destination / "eligibility.jsonl", destination / "sources/xsmt/years/2007/prizes.csv"):
                original = evidence.read_bytes()
                evidence.write_bytes(b"changed evidence")
                with self.assertRaisesRegex(ValueError, "evidence changed"):
                    load_snapshot(destination)
                evidence.write_bytes(original)
            (destination / "records.jsonl").write_text("changed", encoding="utf-8")
            with self.assertRaises(ValueError):
                load_snapshot(destination)

    def test_excel_text_columns_and_explicit_mapping(self):
        from openpyxl import Workbook
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "input.xlsx"
            book = Workbook()
            book.active.append(["published_number", "ending"])
            book.active.append(["000009", "09"])
            book.save(path)
            rows = read_external(path, {"published_number": "number", "ending": "loto"}, missing_flags=True)
            self.assertEqual(rows[0]["number"], "000009")
            book.active.cell(2, 1, 9)
            book.save(path)
            with self.assertRaises(ValueError):
                read_external(path, {"published_number": "number", "ending": "loto"})

    def test_strings_quality_and_fixed_index(self):
        r = {"date": "2026-10-21", "weekday": "Wednesday", "province": "Khánh Hòa", "prize": " G. ĐB ",
             "position": "1", "number": "044743", "loto": "43", "quality_flags": "G.6: unexpected digit count in source",
             "source_url": "https://xosodaiphat.com/xsmt-21-10-2026.html"}
        normalized = validate_row(r, "xsmt")
        self.assertEqual(normalized["number"], "044743")
        self.assertTrue(eligibility(normalized, "flagged")[0])
        self.assertFalse(eligibility({**normalized, "quality_flags": "Source loto table differs from prize endings"}, "flagged")[0])
        self.assertFalse(eligibility(normalized, "review")[0])
        self.assertEqual(day_index("2007-08-20"), 3)
        with self.assertRaises(ValueError):
            validate_row(r, "xsmn")
        with self.assertRaises(ValueError):
            validate_row({**r, "loto": "3"}, "xsmt")

    def test_duplicate_conflict_masks(self):
        a = {"date": "2007-08-18", "region": "xsmt", "province": "A", "prize": "G.8", "number": "00", "loto": "00"}
        self.assertEqual(len(deduplicate([a, a])), 1)
        self.assertIsNone(observations([a])[0]["G.ĐB"])
        self.assertEqual(observations([a])[0]["G.8"], 0)
        with self.assertRaises(ValueError):
            deduplicate([a, {**a, "number": "09", "loto": "09"}])

    def test_future_and_same_date_both_regions_do_not_change_features(self):
        base = [row(), row("2007-08-19", region="xsmt"), row("2007-08-20")]
        q = {"date": "2007-08-19", "region": "xsmn", "province": "A"}
        ids = [("xsmn", "A"), ("xsmt", "A")]
        changed = [base[0], {**base[1], "G.ĐB": 99}, {**base[2], "G.8": 99}]
        a, b = FeatureBuilder(base, ids), FeatureBuilder(changed, ids)
        np.testing.assert_array_equal(a.vector(q), b.vector(q))
        np.testing.assert_array_equal(a.sequence(q)[0], b.sequence(q)[0])
        np.testing.assert_array_equal(Baseline().predict(base, [q]), Baseline().predict(changed, [q]))
        self.assertEqual(len(a.prior({**q, "region": "xsmt"})), 0)
        self.assertEqual(len(a.prior({**q, "date": "2007-08-22", "origin": "2007-08-19"})), 1)

    def test_baselines_warmup_and_uniform_metrics(self):
        q, y = queries_for([row()])
        for kind in ("uniform", "frequency", "smoothed", "province", "markov"):
            np.testing.assert_allclose(Baseline(kind).predict([row()], q), .01)
        result = metrics(np.arange(100), np.full((100, 100), .01))
        self.assertAlmostEqual(result["log_loss"], np.log(100))
        self.assertAlmostEqual(result["brier_sum"], .99)
        self.assertEqual(result["top_10"], .1)

    def test_all_date_rows_stay_together(self):
        qs = [{"date": f"2020-01-{d:02d}", "origin": f"2020-01-{d:02d}"} for d in range(1, 21) for _ in range(2)]
        for train, valid in chronological_folds(qs):
            self.assertLess(max(qs[i]["date"] for i in train), min(qs[i]["date"] for i in valid))


if __name__ == "__main__":
    unittest.main()
