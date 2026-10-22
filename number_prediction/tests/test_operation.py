import json
import sqlite3
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
import numpy as np
from number_prediction.data import PRIZES
from number_prediction.features import FeatureBuilder, queries_for
from number_prediction.pipeline import Predictor
from number_prediction.schedules import Schedule
from number_prediction.ledger import ForecastLedger
from number_prediction.synthetic import generate, null_simulations


class OperationTests(unittest.TestCase):
    def test_schedules_actual_days_and_scope(self):
        schedule = Schedule()
        now = datetime.fromisoformat("2026-10-22T09:00:00+07:00")
        dates = schedule.dates("Khánh Hòa", now, "xsmt", "five-day")
        self.assertEqual([q["date"] for q in dates], ["2026-10-25"])
        self.assertEqual(dates[0]["horizon"], 4)
        with self.assertRaises(ValueError):
            schedule.dates("Huế", datetime.fromisoformat("2026-09-01T00:00:00+07:00"))
        with self.assertRaises(ValueError):
            schedule.resolve("TPHCM")
        with self.assertRaises(ValueError):
            schedule.dates("An Giang", datetime.fromisoformat("2026-10-22T17:00:00+07:00"))

    def test_ledger_commit_before_score_immutable_and_revisions(self):
        with tempfile.TemporaryDirectory() as temp:
            ledger = ForecastLedger(Path(temp) / "ledger.sqlite3")
            q = {"region": "xsmt", "province": "A", "date": "2026-10-23", "origin": "2026-10-22",
                 "prize": "G.ĐB", "horizon": 2}
            meta = {"forecast_timestamp": "2026-10-22T00:00:00+07:00", "model_version": "uniform-v1", "simulated": True,
                    "latest_input_date": "2026-10-21"}
            with self.assertRaises(ValueError):
                ledger.score("missing", 9, "raw-hash")
            rec = ledger.record(q, np.full(100, .01), meta)
            ledger.score(rec["id"], 9, "raw-hash-v1")
            ledger.score(rec["id"], 7, "raw-hash-v2")
            with self.assertRaises(sqlite3.IntegrityError):
                ledger.record(q, np.full(100, .01), meta)
            with self.assertRaises(sqlite3.IntegrityError):
                ledger.db.execute("UPDATE forecasts SET payload='changed'")
            self.assertEqual(ledger.db.execute("SELECT count(*) FROM scores").fetchone()[0], 2)
            ledger.close()

    def test_full_model_pipeline_chronology_and_packages(self):
        draws = generate(days=40, dependency="province")
        builder = FeatureBuilder(draws, [(r, p) for r in ("xsmn", "xsmt") for p in ("A", "B")], windows=(5,), lags=1)
        qs, y = queries_for(draws)
        train = [i for i, q in enumerate(qs) if q["date"] < "2010-02-01"]
        valid = [i for i, q in enumerate(qs) if q["date"] >= "2010-02-01"]
        params = {"iterations": 3, "depth": 2, "d_model": 16, "nhead": 2, "layers": 1, "sequence_length": 8,
                  "epochs": 1, "batch_size": 64, "dropout": 0}
        with tempfile.TemporaryDirectory() as temp:
            for family in ("province", "catboost", "xgboost", "lightgbm", "transformer", "average", "stack"):
                with self.subTest(family=family):
                    model = Predictor(family, builder, params=params).fit([qs[i] for i in train], y[train])
                    p = model.predict([qs[i] for i in valid])
                    np.testing.assert_allclose(p.sum(1), 1, atol=1e-6)
                    if family not in ("province",):
                        with self.assertRaises(ValueError):
                            model.predict([qs[train[0]]])
                    folder = Path(temp) / family
                    model.save(folder, {"selection_end": "2010-01-31"})
                    loaded = Predictor.load(folder)
                    np.testing.assert_allclose(p, loaded.predict([qs[i] for i in valid]), atol=1e-6)
                    if family == "stack":
                        self.assertTrue(all(f["train_label_max"] < f["valid_origin_min"] for f in model.fold_evidence))

    def test_repeated_null_and_cross_prize_dependency(self):
        report = null_simulations(repetitions=8)
        self.assertEqual(report["runs"], 8)
        self.assertTrue(np.isfinite(report["mean_log_loss_minus_uniform"]))
        draws = generate(days=100, dependency="cross_prize")
        builder = FeatureBuilder(draws, [(r, p) for r in ("xsmn", "xsmt") for p in ("A", "B")], windows=(5,), lags=1)
        qs, y = queries_for(draws)
        x = builder.transform(qs)
        # One-hot previous G.8 is a deterministic predictor of the injected G.ĐB.
        offset = 2 + 4 + 2 + 7 + 2
        prediction = x[:, offset:offset + 100].argmax(1)
        has_prior = x[:, offset:offset + 100].sum(1) > 0
        self.assertEqual((prediction[has_prior] == y[has_prior]).mean(), 1.)
        from number_prediction.trees import TreeModel
        from number_prediction.evaluation import metrics
        tr = np.asarray([i for i, q in enumerate(qs) if q["date"] < "2010-03-20"])
        va = np.asarray([i for i, q in enumerate(qs) if q["date"] >= "2010-03-20"])
        learned = TreeModel("xgboost", iterations=15, depth=2, learning_rate=.2).fit(x[tr], y[tr])
        self.assertLess(metrics(y[va], learned.predict_proba(x[va]))["log_loss"], np.log(100) - 1)
