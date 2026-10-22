"""Train and compare on development dates only; final test remains reserved."""
import argparse
import json
import time
from pathlib import Path
import numpy as np
if __package__ in (None, ""):
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from number_prediction.data import load_snapshot, observations, PRIZES, canonical
from number_prediction.features import FeatureBuilder, queries_for
from number_prediction.pipeline import Predictor, FAMILIES, environment
from number_prediction.evaluation import grouped_metrics
from number_prediction.optimization import TemperatureCalibration, tune


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--config", type=Path, default=Path(__file__).with_name("config.json"))
    parser.add_argument("--family", choices=(*FAMILIES, "average", "stack", "uniform", "frequency", "smoothed", "province", "markov", "all"), default="all")
    parser.add_argument("--prize", choices=(*PRIZES, "both"), default="G.ĐB")
    parser.add_argument("--input-prizes", choices=("both", *PRIZES), default="both")
    parser.add_argument("--training-region", choices=("both", "xsmn", "xsmt"), default="both")
    parser.add_argument("--province", help="Optional province-only training comparison")
    parser.add_argument("--train-start", default="2007-08-18")
    parser.add_argument("--train-end", default="2021-12-31")
    parser.add_argument("--calibration-end", default="2023-06-30")
    parser.add_argument("--validation-end", default="2024-12-31")
    parser.add_argument("--horizons", default="1", help="Comma-separated calendar horizons, 1..5")
    parser.add_argument("--params", type=Path, help="JSON fixed model/feature settings")
    parser.add_argument("--tune-trials", type=int, default=0)
    parser.add_argument("--tune-seconds", type=int, default=3600)
    args = parser.parse_args()
    config = json.loads(args.config.read_text())
    if not args.train_start <= args.train_end < args.calibration_end < args.validation_end < config["final_test_start"]:
        parser.error("Require train_start <= train_end < calibration_end < validation_end < final_test_start")
    args.out.mkdir(parents=True, exist_ok=False)
    rows, manifest = load_snapshot(args.data)
    draws = observations(rows)
    settings = json.loads(args.params.read_text()) if args.params else {}
    params = settings.get("model", {})
    inputs = PRIZES if args.input_prizes == "both" else (args.input_prizes,)
    builder = FeatureBuilder(draws, manifest["identities"], inputs=inputs, **settings.get("features", {}))
    report = {"data_version": manifest["data_version"], "environment": environment(), "arguments": {k: str(v) for k, v in vars(args).items()},
              "selection_end": args.validation_end, "final_test_untouched": True, "models": {}}
    families = ("uniform", "frequency", "smoothed", "province", "markov", *FAMILIES, "average", "stack") if args.family == "all" else (args.family,)
    for prize in (PRIZES if args.prize == "both" else (args.prize,)):
        qs, labels = queries_for(draws, prize, tuple(int(x) for x in args.horizons.split(",")))
        train = np.asarray([i for i, q in enumerate(qs) if args.train_start <= q["date"] <= args.train_end and
                            (args.training_region == "both" or q["region"] == args.training_region) and
                            (not args.province or q["province"] == args.province)], dtype=int)
        cal = np.asarray([i for i, q in enumerate(qs) if args.train_end < q["origin"] and q["date"] <= args.calibration_end], dtype=int)
        valid = np.asarray([i for i, q in enumerate(qs) if args.calibration_end < q["origin"] and q["date"] <= args.validation_end], dtype=int)
        if not len(train) or not len(cal) or not len(valid):
            raise ValueError("No eligible examples in a requested chronological segment; inspect regional coverage")
        tq, cq, vq = ([qs[i] for i in ix] for ix in (train, cal, valid))
        for family in families:
            started = time.monotonic()
            chosen = {**params, "training_regions": args.training_region}
            if family in ("average", "stack"):
                chosen["base_models"] = params.get("base_models", dict(params))
            tuning = None
            if args.tune_trials and family in (*FAMILIES, "average", "stack"):
                def evaluate(candidate, tr, va):
                    candidate = {**params, **candidate}
                    if family in ("average", "stack"):
                        candidate["base_models"] = params.get("base_models", dict(params))
                    obj = Predictor(family, builder, prize, candidate).fit([tq[i] for i in tr], labels[train][tr])
                    return obj.predict([tq[i] for i in va])
                tuning = tune(tq, labels[train], evaluate, "sqlite:///" + str((args.out / "studies.sqlite3").resolve()),
                    family + "-" + str(PRIZES.index(prize)), config["final_test_start"], args.tune_trials, args.tune_seconds,
                    config["seed"], "tree" if family in FAMILIES[:3] else "transformer" if family == "transformer" else "ensemble")
                chosen.update(tuning["params"])
            model = Predictor(family, builder, prize, chosen).fit(tq, labels[train])
            raw_cal = model.predict(cq)
            calibration = TemperatureCalibration().fit(raw_cal, labels[cal], cq, args.train_end, config["final_test_start"])
            raw_valid = model.predict(vq)
            calibrated = calibration.transform(raw_valid)
            uncal_report, cal_report = grouped_metrics(vq, labels[valid], raw_valid), grouped_metrics(vq, labels[valid], calibrated)
            use_cal = cal_report["equal_draw"]["log_loss"] + 1e-8 < uncal_report["equal_draw"]["log_loss"]
            if use_cal:
                model.calibration = calibration.temperature
                model.training_end = args.calibration_end
            metadata = {"data_version": manifest["data_version"], "selection_end": args.validation_end,
                "final_test_start": config["final_test_start"], "final_test_end": config["final_test_end"],
                "training_regions": args.training_region, "trained_horizons": sorted({q["horizon"] for q in tq}),
                "baseline_status": "baseline_candidate" if family not in (*FAMILIES, "average", "stack") else "advantage_not_established",
                "training_label_end": args.train_end, "calibration_fit_end": args.calibration_end,
                "calibration_selected": use_cal, "input_prizes": inputs, "snapshot_rows": manifest["rows"]}
            model.save(args.out / f"{family}-prize{PRIZES.index(prize)}", metadata)
            entry = {"uncalibrated": uncal_report, "calibrated": cal_report, "calibration_selected": use_cal,
                     "training_n": len(train), "calibration_n": len(cal), "validation_n": len(valid),
                     "seconds": time.monotonic() - started, "tuning": tuning}
            np.savez_compressed(args.out / f"validation-{family}-prize{PRIZES.index(prize)}.npz",
                                y=labels[valid], probabilities=calibrated if use_cal else raw_valid)
            (args.out / f"validation-queries-prize{PRIZES.index(prize)}.json").write_bytes(canonical(vq))
            report["models"][f"{family}|{prize}"] = entry
            (args.out / "development-report.json").write_bytes(canonical(report))
            print(json.dumps({"family": family, "prize": prize, "log_loss": (cal_report if use_cal else uncal_report)["equal_draw"]["log_loss"], "seconds": entry["seconds"]}))
    report["selection_warning"] = "Development metrics compare candidates; paired uncertainty and resource validation are required before selecting a final deployment. Do not tune against the reserved final test."
    (args.out / "development-report.json").write_bytes(canonical(report))


if __name__ == "__main__":
    main()
