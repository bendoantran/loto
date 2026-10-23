"""Past-only baseline distributions; region/province sequences never concatenate."""
import numpy as np
from .data import PRIZES


def probabilities(values):
    p = np.asarray(values, dtype=float)
    if p.ndim != 2 or p.shape[1] != 100 or not np.isfinite(p).all() or (p < 0).any():
        raise ValueError("Probabilities must be finite nonnegative (n,100)")
    if not np.allclose(p.sum(axis=1), 1, atol=1e-7):
        raise ValueError("Probability rows must sum to one")
    return p


def align(raw, classes, shrink=0.01):
    raw = np.asarray(raw, dtype=float)
    if not 0 <= shrink <= 1 or raw.ndim != 2 or len(set(classes)) != len(classes):
        raise ValueError("Invalid classes/shrinkage")
    if any(int(c) != c or not 0 <= c < 100 for c in classes):
        raise ValueError("Class identities must be 0..99")
    if raw.shape[1] != len(classes):
        raise ValueError("Probability/class columns differ")
    p = np.zeros((len(raw), 100))
    p[:, np.asarray(classes, dtype=int)] = raw
    return probabilities((1 - shrink) * p + shrink / 100)


class Baseline:
    def __init__(self, kind="province", alpha=1.0, min_history=5, backoff="region"):
        if kind not in ("uniform", "frequency", "smoothed", "province", "markov") or alpha <= 0:
            raise ValueError("Invalid baseline/positive smoothing")
        if backoff not in ("region", "pooled", "uniform"):
            raise ValueError("Invalid backoff")
        self.kind, self.alpha, self.min_history, self.backoff = kind, alpha, min_history, backoff

    def predict(self, history, queries, prize="G.ĐB"):
        if prize not in PRIZES:
            raise ValueError("Unsupported target")
        if self.kind == "uniform":
            return np.full((len(queries), 100), .01)
        output = []
        for q in queries:
            cutoff = q.get("origin", q["date"])
            prior = [r for r in history if r["date"] < cutoff and r[prize] is not None]
            local = [r for r in prior if (r["region"], r["province"]) == (q["region"], q["province"])]
            if self.kind == "uniform":
                labels = []
            elif self.kind in ("frequency", "smoothed"):
                labels = [r[prize] for r in prior]
            elif self.kind == "markov" and len(local) >= self.min_history:
                last = local[-1][prize]
                labels = [b[prize] for a, b in zip(local, local[1:]) if a[prize] == last]
            else:
                labels = [r[prize] for r in local]
            if len(labels) < self.min_history and self.kind not in ("uniform", "frequency", "smoothed"):
                labels = [r[prize] for r in prior if self.backoff == "pooled" or
                          (self.backoff == "region" and r["region"] == q["region"])]
            counts = np.bincount(labels, minlength=100).astype(float)
            if self.kind == "frequency" and labels:
                p = counts / len(labels)
            else:
                p = (counts + self.alpha) / (len(labels) + 100 * self.alpha)
            output.append(p)
        return probabilities(np.asarray(output))
