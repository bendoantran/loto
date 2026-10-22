"""Record prospective next-draw/five-calendar-day forecasts before revealing outcomes."""
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
if __package__ in (None, ""):
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from number_prediction.data import load_snapshot, observations, day_index, PRIZES
from number_prediction.pipeline import Predictor, FAMILIES
from number_prediction.schedules import Schedule
from number_prediction.ledger import ForecastLedger
from number_prediction.export import export_forecasts


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", type=Path, action="append", required=True, help="One saved package per requested prize")
    parser.add_argument("--data", type=Path, help="Optional newer validated immutable snapshot for feature updates")
    parser.add_argument("--region", choices=("xsmn", "xsmt"))
    parser.add_argument("--province", required=True)
    parser.add_argument("--prize", choices=(*PRIZES, "both"), default="G.ĐB")
    parser.add_argument("--scope", choices=("next", "five-day"), default="next")
    parser.add_argument("--schedules", type=Path)
    parser.add_argument("--top-k", type=int, default=10)
    parser.add_argument("--ledger", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if not 1 <= args.top_k <= 100 or args.out.exists():
        parser.error("top-k must be 1..100 and output directory must be new")
    history, data_version = None, None
    if args.data:
        rows, manifest = load_snapshot(args.data)
        history, data_version = observations(rows), manifest["data_version"]
    models = [Predictor.load(path, history) for path in args.model]
    prizes = PRIZES if args.prize == "both" else (args.prize,)
    if sorted(m.prize for m in models) != sorted(prizes):
        parser.error("Supply exactly one model package for each requested prize")
    now = datetime.now(timezone.utc)
    dates = Schedule(args.schedules).dates(args.province, now, args.region, args.scope)
    ledger = ForecastLedger(args.ledger)
    records, unavailable = [], []
    try:
        for model in models:
            for query in dates:
                query["prize"] = model.prize
                if model.family in (*FAMILIES, "average", "stack") and query["horizon"] not in model.metadata["trained_horizons"]:
                    unavailable.append({**query, "reason": "No trained/validated direct model for this calendar horizon"})
                    continue
                p = model.predict([query])[0]
                latest = max((r["date"] for r in model.builder.history if r["date"] < query["origin"]), default=None)
                metadata = {"forecast_timestamp": now.isoformat(), "simulated": False,
                    "model_version": model.model_version, "model_training_cutoff": model.training_end,
                    "latest_input_date": latest, "day_index": day_index(query["date"]),
                    "model_data_version": model.metadata["data_version"],
                    "input_data_version": data_version or model.metadata["data_version"],
                    "baseline_status": model.metadata["baseline_status"], "informational_outlook": args.scope == "five-day"}
                records.append(ledger.record(query.copy(), p, metadata))
        export_forecasts(args.out, records, args.top_k, unavailable)
    finally:
        ledger.close()
    print(json.dumps({"recorded": len(records), "unavailable": len(unavailable), "out": str(args.out)}))


if __name__ == "__main__":
    main()
