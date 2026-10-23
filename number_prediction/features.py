"""Deterministic categorical features with a global, strict date boundary."""
from bisect import bisect_left
from collections import defaultdict
from datetime import date, timedelta
import numpy as np
from .data import PRIZES, day_index


class FeatureBuilder:
    def __init__(self, history, identities, windows=(5, 10, 20, 50, 100), lags=5, inputs=PRIZES):
        self.identities = [tuple(x) for x in identities]
        self.windows, self.lags, self.inputs = tuple(windows), lags, tuple(inputs)
        if set(self.inputs) - set(PRIZES) or not self.inputs:
            raise ValueError("Unsupported history prizes")
        self.history = sorted(history, key=lambda r: r["date"])
        self.groups = defaultdict(list)
        for row in self.history:
            self.groups[(row["region"], row["province"])].append(row)
        self.dates = {key: [r["date"] for r in rows] for key, rows in self.groups.items()}
        self.regional = {}
        for region in ("xsmn", "xsmt"):
            for prize in self.inputs:
                rows = [r for r in self.history if r["region"] == region and r[prize] is not None]
                self.regional[(region, prize)] = ([r["date"] for r in rows], [r[prize] for r in rows])

    def prior(self, query):
        if tuple((query["region"], query["province"])) not in self.identities:
            raise ValueError("Unknown region/province identity")
        origin = query.get("origin", query["date"])
        if origin > query["date"]:
            raise ValueError("Forecast origin follows target date")
        key = (query["region"], query["province"])
        return self.groups[key][:bisect_left(self.dates.get(key, []), origin)]

    def vector(self, query):
        prior = self.prior(query)
        identity = (query["region"], query["province"])
        dt = date.fromisoformat(query["date"])
        origin = query.get("origin", query["date"])
        values = [float(day_index(query["date"])), float((dt - date.fromisoformat(origin)).days + 1)]
        values += [float(identity == x) for x in self.identities]
        values += [float(query["region"] == r) for r in ("xsmn", "xsmt")]
        values += [float(dt.weekday() == d) for d in range(7)]
        for prize in self.inputs:
            available = [(r["date"], r[prize]) for r in prior if r[prize] is not None]
            labels = [v for _, v in available]
            values.extend([len(labels), float(not labels)])
            for lag in range(1, self.lags + 1):
                v = labels[-lag] if len(labels) >= lag else None
                values.extend(float(v == k) for k in range(100))
                values.append(float(v is None))
            for window in self.windows:
                sub = labels[-window:]
                counts = np.bincount(sub, minlength=100).astype(float)
                probs = (counts + 1) / (len(sub) + 100)
                values.extend(probs)
                values.extend([len(sub), -float((probs * np.log(probs)).sum())])
            # Both elapsed calendar time and elapsed observed draws; masks disambiguate absence.
            latest = {label: i for i, (_, label) in enumerate(available)}
            for k in range(100):
                if k in latest:
                    j = latest[k]
                    values.extend([(date.fromisoformat(origin) - date.fromisoformat(available[j][0])).days,
                                   len(available) - 1 - j, 0])
                else:
                    values.extend([0, 0, 1])
        for region in ("xsmn", "xsmt"):
            for prize in self.inputs:
                dates, labels = self.regional[(region, prize)]
                stop = bisect_left(dates, origin)
                recent = labels[max(0, stop - 100):stop]
                counts = np.bincount(recent, minlength=100)
                values.extend((counts + 1) / (len(recent) + 100))
                values.extend([len(recent), float(not recent)])
        return np.asarray(values, dtype=np.float32)

    def transform(self, queries):
        return np.stack([self.vector(q) for q in queries])

    def sequence(self, query, length=128):
        if length < 2:
            raise ValueError("Sequence length must include a start token and at least one historical slot")
        # Start token is always visible: empty histories never attend only to padding.
        prior = self.prior(query)[-(length - 1):]
        tokens = np.zeros((length, 3), dtype=np.int64)
        tokens[0] = [102, 102, 0]
        for i, row in enumerate(prior, 1):
            tokens[i] = [row["G.8"] + 1 if "G.8" in self.inputs and row["G.8"] is not None else 101,
                         row["G.ĐB"] + 1 if "G.ĐB" in self.inputs and row["G.ĐB"] is not None else 101,
                         day_index(row["date"])]
        return tokens, len(prior)


def queries_for(draws, prize="G.ĐB", horizons=(1,)):
    result, labels = [], []
    for row in draws:
        if row[prize] is None:
            continue
        for horizon in horizons:
            if not 1 <= horizon <= 5:
                raise ValueError("Supported calendar horizons are 1..5")
            origin = str(date.fromisoformat(row["date"]) - timedelta(days=horizon - 1))
            if origin < "2007-08-18":
                continue
            result.append({**{k: row[k] for k in ("date", "region", "province")}, "origin": origin,
                           "prize": prize, "horizon": horizon})
            labels.append(row[prize])
    return result, np.asarray(labels, dtype=np.int64)
