"""Freeze a development-selected predictor before any final-test scoring."""
import argparse
import json
from pathlib import Path
import numpy as np
if __package__ in (None, ""):
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from number_prediction.data import canonical, load_snapshot
from number_prediction.pipeline import Predictor, FAMILIES
from number_prediction.optimization import freeze_policy
from number_prediction.evaluation import metrics, paired_block_interval


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--prize-index", type=int, choices=(0, 1), default=1)
    parser.add_argument("--minimum-gain", type=float, default=.001, help="Predeclare practical log-loss gain before the comparison")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    _, manifest = load_snapshot(args.data)
    queries = json.loads((args.run / f"validation-queries-prize{args.prize_index}.json").read_text())
    baseline_names = ("uniform", "frequency", "smoothed", "province", "markov")
    names = (*baseline_names, *FAMILIES, "average", "stack")
    values, scores = {}, {}
    truth = None
    for family in names:
        stored = np.load(args.run / f"validation-{family}-prize{args.prize_index}.npz", allow_pickle=False)
        if truth is not None and not np.array_equal(truth, stored["y"]):
            raise ValueError("Candidate outcomes differ")
        truth = stored["y"]
        values[family] = stored["probabilities"]
        scores[family] = metrics(truth, values[family])["log_loss"]
    # Predefined conservative rule: begin with uniform; require block evidence of gain.
    baseline = min(baseline_names, key=scores.get)
    evidence = {}
    if baseline != "uniform":
        evidence[baseline] = paired_block_interval(queries, truth, values[baseline], values["uniform"], repetitions=4000, alpha=.05 / len(names))
        interval = evidence[baseline]["interval"]
        if interval is None or interval[1] >= -args.minimum_gain:
            baseline = "uniform"
    eligible = [baseline]
    for family in (*FAMILIES, "average", "stack"):
        evidence[family] = paired_block_interval(queries, truth, values[family], values[baseline], repetitions=4000, alpha=.05 / len(names))
        interval = evidence[family]["interval"]
        if interval is not None and interval[1] < -args.minimum_gain:
            eligible.append(family)
    selected = min(eligible, key=scores.get)
    model = Predictor.load(args.run / f"{selected}-prize{args.prize_index}")
    if model.metadata["data_version"] != manifest["data_version"]:
        raise ValueError("Selection snapshot differs from trained model")
    if max(q["date"] for q in queries) >= model.metadata["final_test_start"]:
        raise ValueError("Selection data enters final test")
    policy = {"model_version": model.model_version, "data_version": manifest["data_version"],
        "selection_end": model.metadata["selection_end"], "final_test_start": model.metadata["final_test_start"],
        "final_test_end": model.metadata["final_test_end"], "evaluation": "frozen_weights_updated_past_history",
        "family": selected, "minimum_gain": args.minimum_gain, "comparison_count": len(names),
        "development_log_loss": scores, "evidence": evidence,
        "advantage_status": "baseline_selected" if selected in baseline_names else "development_gain_requires_final_confirmation",
        "windows_benchmark": "pending_actual_target", "prospective_evaluation": "pending"}
    freeze_policy(args.out, policy)
    print(json.dumps({"selected": selected, "policy": str(args.out), "final_test_scored": False}))


if __name__ == "__main__":
    main()
