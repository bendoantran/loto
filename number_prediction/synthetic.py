"""Reproducible null and explicitly injected dependencies, never archive evidence."""
from datetime import date, timedelta
import numpy as np


def generate(days=150, seed=1729, dependency="uniform"):
    if dependency not in ("uniform", "province", "cross_prize", "cross_region"):
        raise ValueError("Unknown synthetic dependency")
    rng = np.random.default_rng(seed)
    result, previous = [], {}
    for i in range(days):
        day = str(date(2010, 1, 1) + timedelta(days=i))
        today = []
        for region in ("xsmn", "xsmt"):
            for province in ("A", "B"):
                g8, db = map(int, rng.integers(100, size=2))
                if dependency == "province":
                    db = 7 if province == "A" else 93
                elif dependency == "cross_prize" and (region, province) in previous:
                    db = previous[(region, province)]["G.8"]
                elif dependency == "cross_region" and ("xsmn", province) in previous:
                    db = previous[("xsmn", province)]["G.8"]
                today.append({"date": day, "region": region, "province": province, "G.8": g8, "G.ĐB": db})
        result.extend(today)
        previous.update({(r["region"], r["province"]): r for r in today})
    return result


def null_simulations(repetitions=30, seed=1729):
    """Measure positive development fluctuations, with fixed policies and fresh seeds."""
    from .baselines import Baseline
    from .features import queries_for
    from .evaluation import metrics
    differences = []
    for run in range(repetitions):
        data = generate(90, seed + run)
        queries, y = queries_for(data[-120:])
        p = Baseline("province", alpha=10).predict(data, queries)
        differences.append(metrics(y, p)["log_loss"] - np.log(100))
    return {"runs": repetitions, "seed": seed, "mean_log_loss_minus_uniform": float(np.mean(differences)),
            "fraction_apparent_improvements": float(np.mean(np.asarray(differences) < 0)),
            "interpretation": "Descriptive repeated null simulation; an isolated improvement is not evidence of predictive advantage."}
