"""Record then reveal/score historical outcomes, with reserved-test policy guards."""
import argparse
import json
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
import numpy as np
if __package__ in (None, ""):
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from number_prediction.data import load_snapshot, observations, day_index, canonical, digest, PRIZES
from number_prediction.features import queries_for
from number_prediction.pipeline import Predictor
from number_prediction.baselines import Baseline
from number_prediction.evaluation import grouped_metrics, paired_block_interval
from number_prediction.ledger import ForecastLedger
from number_prediction.export import export_forecasts


def verify_policy(path, model, start, end, data_version):
    policy = json.loads(Path(path).read_text(encoding="utf-8"))
    hash_value = policy.pop("policy_hash")
    if digest(canonical(policy)) != hash_value:
        raise ValueError("Frozen policy changed")
    if (policy["model_version"] != model.model_version or policy["data_version"] != data_version or
        policy["selection_end"] >= start or policy["final_test_start"] != start or policy["final_test_end"] != end or
        policy["evaluation"] != "frozen_weights_updated_past_history"):
        raise ValueError("Final evaluation differs from frozen model/data/policy")
    return hash_value


def main():
    from number_prediction import configure_cli
    configure_cli()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--model", type=Path, help="Saved learned/baseline package; omit for operational baseline")
    parser.add_argument("--baseline", choices=("uniform", "frequency", "smoothed", "province", "markov"), default="uniform")
    parser.add_argument("--start", required=True)
    parser.add_argument("--end", required=True)
    parser.add_argument("--prize", choices=PRIZES, default="G.ĐB")
    parser.add_argument("--region", choices=("xsmn", "xsmt", "both"), default="both")
    parser.add_argument("--horizons", default="1")
    parser.add_argument("--final-policy", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--config", type=Path, default=Path(__file__).with_name("config.json"))
    args = parser.parse_args()
    if args.out.exists() or args.start > args.end:
        parser.error("Use a new output directory and ordered dates")
    config = json.loads(args.config.read_text(encoding="utf-8"))
    rows, manifest = load_snapshot(args.data)
    draws = observations(rows)
    model = Predictor.load(args.model, draws) if args.model else None
    if model and model.prize != args.prize:
        parser.error("Package target prize differs")
    policy_hash = None
    if args.end >= config["final_test_start"]:
        if not args.final_policy or not model:
            parser.error("Reserved final test requires a saved model and frozen selection policy")
        policy_hash = verify_policy(args.final_policy, model, args.start, args.end, manifest["data_version"])
    qs, labels = queries_for(draws, args.prize, tuple(int(x) for x in args.horizons.split(",")))
    ix = [i for i, q in enumerate(qs) if args.start <= q["date"] <= args.end and (args.region == "both" or q["region"] == args.region)]
    queries, y = [qs[i] for i in ix], labels[ix]
    if not len(queries):
        raise ValueError("No eligible targets; inspect coverage")
    if model:
        from number_prediction.pipeline import FAMILIES
        if model.family in (*FAMILIES, "average", "stack") and any(q["horizon"] not in model.metadata["trained_horizons"] for q in queries):
            raise ValueError("Requested direct horizon was not trained")
    # Outcomes remain available only to scoring; model inputs always have strict date filtering.
    args.out.parent.mkdir(parents=True, exist_ok=True)
    ledger_path = args.out.parent / (args.out.name + ".ledger.sqlite3")
    if ledger_path.exists():
        raise ValueError("Backtest ledger already exists; retain it and choose a new run name")
    ledger = ForecastLedger(ledger_path)
    predictions, forecasts, eligibility_mask = [], [], []
    grouped = defaultdict(list)
    for i, query in enumerate(queries):
        grouped[query["date"]].append(i)
    started = time.monotonic()
    try:
        for indices in grouped.values():
            batch = [queries[i] for i in indices]
            eligible = [bool(model and q["origin"] > max(model.training_end, model.metadata.get("selection_end", model.training_end))) for q in batch]
            if model:
                p = np.full((len(batch), 100), .01)
                valid_ix = [i for i, allowed in enumerate(eligible) if allowed]
                if valid_ix:
                    p[valid_ix] = model.predict([batch[i] for i in valid_ix])
            else:
                p = Baseline(args.baseline).predict(draws, batch, args.prize)
            batch_records = []
            # Commit every province/prize forecast for the date before reading any score.
            for query, distribution, allowed in zip(batch, p, eligible):
                latest = max((r["date"] for r in draws if r["date"] < query["origin"]), default=None)
                metadata = {"forecast_timestamp": query["origin"] + "T00:00:00+07:00", "simulated": True,
                    "model_version": (model.model_version + ("" if allowed else "/uniform-warmup")) if model else args.baseline + "-v1",
                    "model_training_cutoff": model.training_end if model else None,
                    "latest_input_date": latest, "day_index": day_index(query["date"]),
                    "data_version": manifest["data_version"], "baseline_status": "advantage_not_established" if model else "baseline",
                    "policy_hash": policy_hash, "uniform_warmup": bool(model and not allowed)}
                batch_records.append(ledger.record(query, distribution, metadata))
            for i, record, distribution, allowed in zip(indices, batch_records, p, eligible):
                ledger.score(record["id"], int(y[i]), manifest["data_version"])
                forecasts.append(record)
                predictions.append(distribution)
                eligibility_mask.append(allowed)
        p = np.asarray(predictions)
        export_forecasts(args.out, forecasts)
        uniform = np.full_like(p, .01)
        report = {"data_version": manifest["data_version"], "metrics": grouped_metrics(queries, y, p),
            "paired_vs_uniform": paired_block_interval(queries, y, p, uniform), "seconds": time.monotonic() - started,
            "final_policy_hash": policy_hash, "mode": "simulated_historical", "tie_policy": "lower_class_first",
            "scoring_clip": 1e-15, "brier_normalization": "sum_over_100_classes_mean_over_draws",
            "coverage": manifest["coverage"], "prospective_evidence": False}
        common = np.flatnonzero(eligibility_mask)
        report["model_eligible_metrics"] = grouped_metrics([queries[i] for i in common], y[common], p[common]) if len(common) else None
        report["uniform_warmup_draws"] = int(sum(bool(model and not e) for e in eligibility_mask))
        (args.out / "report.json").write_bytes(canonical(report))
        print(json.dumps(report["metrics"]["equal_draw"]))
    finally:
        ledger.close()


if __name__ == "__main__":
    main()
