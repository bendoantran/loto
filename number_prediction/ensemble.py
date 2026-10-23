"""Four-model probability averaging and explicitly chronological stacking."""
import json
from pathlib import Path
import numpy as np
from .baselines import probabilities, align
from .evaluation import chronological_folds


def four_outputs(outputs):
    values = np.asarray(outputs, dtype=float)
    if values.ndim != 3 or values.shape[1:] != (4, 100):
        raise ValueError("Expected (n,4,100) ordered CatBoost/XGBoost/LightGBM/Transformer")
    for i in range(4):
        probabilities(values[:, i])
    return values


def weighted_average(outputs, weights, shrink=0.):
    values = four_outputs(outputs)
    weights = np.asarray(weights, dtype=float)
    if weights.shape != (4,) or not np.isfinite(weights).all() or (weights < 0).any() or not np.isclose(weights.sum(), 1):
        raise ValueError("Weights must be nonnegative and sum to one")
    if not 0 <= shrink <= 1:
        raise ValueError("Invalid uniform shrinkage")
    return probabilities(np.einsum("nmc,m->nc", values, weights) * (1 - shrink) + shrink / 100)


def chronological_oof(queries, fit_predict, blocks=4):
    """fit_predict(train_indices, heldout_indices) must fit every component anew.

    Hyperparameters are fixed before these folds or selected strictly inside each
    train block. The callback must never select early stopping using heldout rows.
    """
    predictions, indices, evidence = [], [], []
    for train, valid in chronological_folds(queries, blocks):
        boundary = min(queries[i].get("origin", queries[i]["date"]) for i in valid)
        if max(queries[i]["date"] for i in train) >= boundary:
            raise ValueError("Training outcome crosses validation information cutoff")
        p = four_outputs(fit_predict(train, valid))
        if len(p) != len(valid):
            raise ValueError("OOF prediction length mismatch")
        predictions.append(p)
        indices.extend(valid)
        evidence.append({"train_label_max": max(queries[i]["date"] for i in train), "valid_origin_min": boundary,
                         "train_n": len(train), "valid_n": len(valid)})
    if not predictions:
        raise ValueError("No chronological stacking examples")
    return np.asarray(indices), np.concatenate(predictions), evidence


class ProbabilityStack:
    def __init__(self, regularization=1., shrink=.01, seed=1729):
        if regularization <= 0:
            raise ValueError("Regularization C must be positive")
        self.regularization, self.shrink, self.seed = regularization, shrink, seed

    def fit(self, oof, y):
        x = four_outputs(oof).reshape(len(oof), 400)
        self.classes = np.unique(y)
        self.coef, self.intercept = None, None
        if len(self.classes) > 1:
            from sklearn.linear_model import LogisticRegression
            obj = LogisticRegression(C=self.regularization, max_iter=1000, solver="lbfgs", random_state=self.seed)
            obj.fit(x, y)
            self.coef, self.intercept = obj.coef_, obj.intercept_
        return self

    def predict_proba(self, outputs):
        x = four_outputs(outputs).reshape(len(outputs), 400)
        if self.coef is None:
            raw = np.ones((len(x), 1))
        else:
            z = x @ self.coef.T + self.intercept
            if z.shape[1] == 1:
                positive = 1 / (1 + np.exp(-z[:, 0]))
                raw = np.column_stack((1 - positive, positive))
            else:
                z -= z.max(axis=1, keepdims=True)
                raw = np.exp(z)
                raw /= raw.sum(axis=1, keepdims=True)
        return align(raw, self.classes, self.shrink)

    def save(self, path):
        with Path(path).open("x", encoding="utf-8") as stream:
            json.dump({"regularization": self.regularization, "shrink": self.shrink, "seed": self.seed,
                       "classes": self.classes.tolist(), "coef": None if self.coef is None else self.coef.tolist(),
                       "intercept": None if self.intercept is None else self.intercept.tolist()}, stream)

    @classmethod
    def load(cls, path):
        d = json.loads(Path(path).read_text(encoding="utf-8"))
        obj = cls(d["regularization"], d["shrink"], d["seed"])
        obj.classes = np.asarray(d["classes"])
        obj.coef = None if d["coef"] is None else np.asarray(d["coef"])
        obj.intercept = None if d["intercept"] is None else np.asarray(d["intercept"])
        return obj
