"""Paired comparison on identical eligible draws, with date-block uncertainty."""
import argparse
import json
from pathlib import Path
import numpy as np
if __package__ in (None, ""):
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from number_prediction.data import canonical
from number_prediction.evaluation import grouped_metrics, paired_block_interval


def compare(reference_dir, candidate_dir, family, prize_index=1, comparisons=1):
    def load(folder):
        qs = json.loads((folder / f"validation-queries-prize{prize_index}.json").read_text())
        values = np.load(folder / f"validation-{family}-prize{prize_index}.npz", allow_pickle=False)
        keyed = {canonical(q).decode(): (q, int(y), p) for q, y, p in zip(qs, values["y"], values["probabilities"])}
        if len(keyed) != len(qs):
            raise ValueError("Duplicate validation examples")
        return keyed
    reference, candidate = load(Path(reference_dir)), load(Path(candidate_dir))
    keys = sorted(reference.keys() & candidate.keys())
    if not keys:
        raise ValueError("No matched eligible draws")
    if any(reference[k][1] != candidate[k][1] for k in keys):
        raise ValueError("Source outcomes differ; use the same frozen snapshot")
    qs, y, ref = zip(*(reference[k] for k in keys))
    p = np.stack([candidate[k][2] for k in keys])
    y, ref = np.asarray(y), np.stack(ref)
    result = {"matched_draws": len(keys), "reference_only": len(reference) - len(keys), "candidate_only": len(candidate) - len(keys),
        "reference": grouped_metrics(qs, y, ref), "candidate": grouped_metrics(qs, y, p),
        "paired": paired_block_interval(qs, y, p, ref, repetitions=2000, alpha=.05 / comparisons),
        "comparison_count": comparisons, "adjustment": "Bonferroni across predeclared comparison count"}
    result["by_region"] = {}
    for region in ("xsmn", "xsmt"):
        ix = [i for i, q in enumerate(qs) if q["region"] == region]
        if ix:
            result["by_region"][region] = paired_block_interval([qs[i] for i in ix], y[ix], p[ix], ref[ix],
                repetitions=2000, alpha=.05 / comparisons)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--family", required=True)
    parser.add_argument("--prize-index", type=int, choices=(0, 1), default=1)
    parser.add_argument("--comparison-count", type=int, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.comparison_count < 1:
        parser.error("Predeclare at least one comparison")
    result = compare(args.reference, args.candidate, args.family, args.prize_index, args.comparison_count)
    with args.out.open("xb") as stream:
        stream.write(canonical(result))
    print(json.dumps(result["paired"]))


if __name__ == "__main__":
    main()
