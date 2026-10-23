"""Compare fixed daily/weekly/monthly refit policies on development dates only."""
import argparse
import calendar
import json
import time
from datetime import date, timedelta
from pathlib import Path
import numpy as np
if __package__ in (None, ""):
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from number_prediction.data import load_snapshot, observations, canonical, PRIZES
from number_prediction.features import FeatureBuilder, queries_for
from number_prediction.pipeline import Predictor, FAMILIES
from number_prediction.optimization import TemperatureCalibration
from number_prediction.evaluation import grouped_metrics


def next_refit(day, cadence):
    day = date.fromisoformat(day)
    if cadence in ("daily", "weekly"):
        return str(day + timedelta(days=1 if cadence == "daily" else 7))
    if cadence == "monthly":
        year, month = (day.year + 1, 1) if day.month == 12 else (day.year, day.month + 1)
        return str(date(year, month, min(day.day, calendar.monthrange(year, month)[1])))
    raise ValueError("Unknown refit cadence")


def evaluate_cadence(draws, identities, start, end, cadence, family, prize, params=None, calibration_days=30):
    queries, y = queries_for(draws, prize)
    builder = FeatureBuilder(draws, identities, windows=(5, 10, 20, 50, 100), lags=5)
    target_ix = [i for i, q in enumerate(queries) if start <= q["date"] <= end]
    if not target_ix or calibration_days < 1:
        raise ValueError("No target examples or invalid calibration period")
    predictions, tested, truth, fits = [], [], [], []
    model, next_date = None, start
    for origin in sorted({queries[i]["date"] for i in target_ix}):
        batch_ix = [i for i in target_ix if queries[i]["date"] == origin]
        if origin >= next_date:
            boundary = str(date.fromisoformat(origin) - timedelta(days=calibration_days))
            train = [i for i, q in enumerate(queries) if q["date"] < boundary]
            cal = [i for i, q in enumerate(queries) if boundary <= q["date"] < origin]
            if len(train) >= 100 and len(cal) >= 20:
                started = time.monotonic()
                model = Predictor(family, builder, prize, params).fit([queries[i] for i in train], y[train])
                cq = [queries[i] for i in cal]
                calibration = TemperatureCalibration().fit(model.predict(cq), y[cal], cq, model.training_end)
                model.calibration = calibration.temperature
                model.training_end = max(queries[i]["date"] for i in cal)
                fits.append({"origin": origin, "fit_label_end": max(queries[i]["date"] for i in train),
                             "calibration_label_end": model.training_end, "seconds": time.monotonic() - started})
            next_date = next_refit(origin, cadence)
        batch = [queries[i] for i in batch_ix]
        predictions.extend(model.predict(batch) if model else np.full((len(batch), 100), .01))
        tested.extend(batch)
        truth.extend(y[batch_ix])
    return {"cadence": cadence, "metrics": grouped_metrics(tested, truth, np.asarray(predictions)),
            "refits": fits, "fixed_policy": "fit_before_calibration_then_temperature_fit_in_later_past_segment",
            "calibration_days": calibration_days, "feature_history_updates": "every_origin_without_weight_refit"}


def main():
    from number_prediction import configure_cli
    configure_cli()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--start", required=True)
    parser.add_argument("--end", required=True)
    parser.add_argument("--family", choices=(*FAMILIES, "average", "stack"), default="catboost")
    parser.add_argument("--prize", choices=PRIZES, default="G.ĐB")
    parser.add_argument("--params", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--config", type=Path, default=Path(__file__).with_name("config.json"))
    args = parser.parse_args()
    config = json.loads(args.config.read_text(encoding="utf-8"))
    if args.start > args.end or args.end >= config["final_test_start"]:
        parser.error("Cadence selection must use ordered development dates before the final test")
    rows, manifest = load_snapshot(args.data)
    settings = json.loads(args.params.read_text(encoding="utf-8")) if args.params else {}
    report = {"data_version": manifest["data_version"], "start": args.start, "end": args.end,
        "policies": [evaluate_cadence(observations(rows), manifest["identities"], args.start, args.end, cadence,
                     args.family, args.prize, settings.get("model", {})) for cadence in ("daily", "weekly", "monthly")]}
    with args.out.open("xb") as stream:
        stream.write(canonical(report))
    print(json.dumps({p["cadence"]: {"refits": len(p["refits"]), "log_loss": p["metrics"]["equal_draw"]["log_loss"]} for p in report["policies"]}))


if __name__ == "__main__":
    main()
