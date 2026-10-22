"""Chronological contracts and paired date-block uncertainty."""
from collections import defaultdict
import numpy as np
from .baselines import probabilities


def metrics(y, p):
    p = probabilities(p)
    y = np.asarray(y, dtype=int)
    if len(y) != len(p) or not len(y) or (y < 0).any() or (y > 99).any():
        raise ValueError("Invalid scoring labels")
    ranked = np.argsort(-p, axis=1, kind="stable")  # ties: lower class first
    truth = np.eye(100)[y]
    confidence, correct = p.max(axis=1), (ranked[:, 0] == y)
    bins = []
    for lo in np.linspace(0, 0.9, 10):
        mask = (confidence >= lo) & (confidence < lo + .1 if lo < .9 else confidence <= 1)
        if mask.any():
            bins.append({"n": int(mask.sum()), "confidence": float(confidence[mask].mean()),
                         "accuracy": float(correct[mask].mean())})
    return {"n": len(y), "log_loss": float(-np.log(np.clip(p[np.arange(len(y)), y], 1e-15, 1)).mean()),
            "brier_sum": float(((p - truth) ** 2).sum(axis=1).mean()),
            **{f"top_{k}": float((ranked[:, :k] == y[:, None]).any(axis=1).mean()) for k in (1, 3, 5, 10)},
            "calibration": bins}


def grouped_metrics(queries, y, p):
    groups = defaultdict(list)
    for i, q in enumerate(queries):
        for key in ("region", "province", "prize", "horizon"):
            groups[(key, str(q.get(key, "unknown")))].append(i)
        groups[("year", q["date"][:4])].append(i)
    output = {f"{k}|{v}": metrics(np.asarray(y)[ix], p[ix]) for (k, v), ix in groups.items()}
    return {"equal_draw": metrics(y, p), "groups": output,
            **{key + "_balanced_log_loss": float(np.mean([v["log_loss"] for k, v in output.items() if k.startswith(key + "|")]))
               for key in ("region", "province")}}


def chronological_folds(queries, blocks=4):
    dates = sorted({q.get("origin", q["date"]) for q in queries})
    if len(dates) < blocks:
        raise ValueError("Insufficient dates for chronological folds")
    for segment in np.array_split(dates, blocks)[1:]:
        first, last = segment[0], segment[-1]
        train = [i for i, q in enumerate(queries) if q["date"] < first]
        valid = [i for i, q in enumerate(queries) if first <= q.get("origin", q["date"]) <= last]
        if train and valid:
            yield np.asarray(train), np.asarray(valid)


def paired_block_interval(queries, y, p, reference, seed=1729, repetitions=500, block_days=28, alpha=.05):
    p, reference = probabilities(p), probabilities(reference)
    losses = -np.log(np.clip(p[np.arange(len(y)), y], 1e-15, 1)) + np.log(np.clip(reference[np.arange(len(y)), y], 1e-15, 1))
    by_date = defaultdict(list)
    for q, loss in zip(queries, losses):
        by_date[q["date"]].append(loss)
    dates = sorted(by_date)
    # Contiguous calendar blocks retain date dependence and every draw within a date.
    from datetime import date
    origin = date.fromisoformat(dates[0])
    groups = defaultdict(list)
    for day in dates:
        groups[(date.fromisoformat(day) - origin).days // block_days].extend(by_date[day])
    groups = list(groups.values())
    if len(groups) < 2:
        return {"mean_difference": float(losses.mean()), "interval": None, "reason": "insufficient_blocks"}
    rng = np.random.default_rng(seed)
    means = [np.concatenate([groups[i] for i in rng.integers(len(groups), size=len(groups))]).mean() for _ in range(repetitions)]
    return {"mean_difference": float(losses.mean()), "interval": np.quantile(means, [alpha / 2, 1 - alpha / 2]).tolist(),
            "blocks": len(groups), "block_calendar_days": block_days, "alpha": alpha}
