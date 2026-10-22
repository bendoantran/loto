"""Unified training and portable CPU prediction over versioned feature state."""
import importlib.metadata
import json
import platform
from pathlib import Path
import numpy as np
from .data import PRIZES, canonical, digest
from .features import FeatureBuilder
from .baselines import Baseline
from .trees import TreeModel
from .ensemble import ProbabilityStack, chronological_oof, weighted_average

FAMILIES = ("catboost", "xgboost", "lightgbm", "transformer")


def environment():
    packages = {}
    for name in ("numpy", "pandas", "scikit-learn", "catboost", "xgboost-cpu", "xgboost", "lightgbm", "torch", "optuna", "openpyxl"):
        try:
            packages[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            pass
    return {"python": platform.python_version(), "platform": platform.platform(), "packages": packages}


class Predictor:
    def __init__(self, family, builder, prize="G.ĐB", params=None):
        self.family, self.builder, self.prize = family, builder, prize
        self.params = params or {}
        self.model = None
        self.children = []
        self.calibration = 1.

    def fit(self, queries, y):
        if not queries or self.prize not in PRIZES:
            raise ValueError("Training needs eligible examples and an explicit prize")
        self.training_end = max(q["date"] for q in queries)
        if self.family in ("uniform", "frequency", "smoothed", "province", "markov"):
            self.model = Baseline(self.family, **{k: v for k, v in self.params.items() if k in ("alpha", "min_history", "backoff")})
        elif self.family in FAMILIES[:3]:
            self.model = TreeModel(self.family, **{k: v for k, v in self.params.items() if k in
                ("seed", "iterations", "depth", "learning_rate", "threads", "shrink", "device")})
            self.model.fit(self.builder.transform(queries), y)
        elif self.family == "transformer":
            from .transformer import TransformerModel, sequence_inputs
            dates = sorted({q.get("origin", q["date"]) for q in queries})
            if len(dates) < 5:
                raise ValueError("Transformer needs at least five training dates including later early-stop validation")
            boundary = dates[max(1, int(len(dates) * .85))]
            tr = [i for i, q in enumerate(queries) if q["date"] < boundary]
            va = [i for i, q in enumerate(queries) if q.get("origin", q["date"]) >= boundary]
            if not tr or not va:
                raise ValueError("Insufficient chronological early-stop split")
            self.model = TransformerModel(len(self.builder.identities), **{k: v for k, v in self.params.items() if k in
                ("seed", "device", "shrink", "d_model", "nhead", "layers", "dropout", "sequence_length")})
            length = self.model.model.config["sequence_length"]
            all_inputs = sequence_inputs(self.builder, queries, length)
            targets = np.full((len(queries), 2), -1)
            targets[:, PRIZES.index(self.prize)] = y
            self.model.fit([x[tr] for x in all_inputs], targets[tr],
                ([x[va] for x in all_inputs], targets[va]), epochs=self.params.get("epochs", 30),
                batch_size=self.params.get("batch_size", 64), learning_rate=self.params.get("learning_rate", .001))
        elif self.family in ("average", "stack"):
            base_params = self.params.get("base_models", self.params)
            # Each OOF child fit has its own strictly earlier internal early-stop split.
            if self.family == "stack":
                def callback(train, valid):
                    tq, vq = [queries[i] for i in train], [queries[i] for i in valid]
                    children = [Predictor(f, self.builder, self.prize, base_params).fit(tq, np.asarray(y)[train]) for f in FAMILIES]
                    return np.stack([c.predict(vq) for c in children], axis=1)
                indices, oof, self.fold_evidence = chronological_oof(queries, callback, self.params.get("folds", 4))
                self.model = ProbabilityStack(self.params.get("regularization", 1.), self.params.get("shrink", .01))
                self.model.fit(oof, np.asarray(y)[indices])
            self.children = [Predictor(f, self.builder, self.prize, base_params).fit(queries, y) for f in FAMILIES]
        else:
            raise ValueError("Unsupported model family")
        return self

    def predict(self, queries):
        if getattr(self, "metadata", {}).get("selection_end") and any(q.get("origin", q["date"]) <= self.metadata["selection_end"] for q in queries):
            raise ValueError("Forecast precedes the saved model's development selection cutoff")
        # Baselines have no fitted learned parameters and update only strict past history.
        if self.family in FAMILIES or self.family in ("average", "stack"):
            if any(q.get("origin", q["date"]) <= self.training_end for q in queries):
                raise ValueError("Model was fit/selected using information from the forecast origin or later")
        if self.family in FAMILIES[:3]:
            p = self.model.predict_proba(self.builder.transform(queries))
        elif self.family == "transformer":
            from .transformer import sequence_inputs
            p = self.model.predict_proba(sequence_inputs(self.builder, queries, self.model.model.config["sequence_length"]), PRIZES.index(self.prize))
        elif self.children:
            outputs = np.stack([c.predict(queries) for c in self.children], axis=1)
            p = self.model.predict_proba(outputs) if self.family == "stack" else weighted_average(outputs,
                self.params.get("weights", [.25] * 4), self.params.get("shrink", .01))
        else:
            regions = self.params.get("training_regions", "both")
            history = self.builder.history if regions == "both" else [r for r in self.builder.history if r["region"] == regions]
            p = self.model.predict(history, queries, self.prize)
        if self.calibration != 1.:
            from .optimization import TemperatureCalibration
            p = TemperatureCalibration(self.calibration).transform(p)
        return p

    def save(self, folder, metadata):
        folder = Path(folder)
        folder.mkdir(parents=True, exist_ok=False)
        state = {"family": self.family, "prize": self.prize, "params": self.params, "training_end": self.training_end,
            "calibration": self.calibration, "feature": {"identities": self.builder.identities,
            "windows": self.builder.windows, "lags": self.builder.lags, "inputs": self.builder.inputs},
            "history": self.builder.history, "environment": environment(), "metadata": metadata,
            "fold_evidence": getattr(self, "fold_evidence", [])}
        state["source_sha256"] = {p.name: digest(p.read_bytes()) for p in Path(__file__).parent.glob("*.py")}
        (folder / "state.json").write_bytes(canonical(state))
        if self.family in FAMILIES:
            self.model.save(folder / "model")
        elif self.family == "stack":
            self.model.save(folder / "stack.json")
        for i, child in enumerate(self.children):
            child.save(folder / f"base_{i}", metadata)
        hashes = {str(p.relative_to(folder)): digest(p.read_bytes()) for p in folder.rglob("*") if p.is_file()}
        (folder / "manifest.json").write_bytes(canonical({"schema": 1, "files": hashes,
            "model_version": digest(canonical(hashes)), "classes": [f"{i:02d}" for i in range(100)]}))

    @classmethod
    def load(cls, folder, updated_history=None):
        folder = Path(folder)
        manifest = json.loads((folder / "manifest.json").read_text())
        if manifest["model_version"] != digest(canonical(manifest["files"])):
            raise ValueError("Model manifest changed")
        for name, expected in manifest["files"].items():
            file = (folder / name).resolve()
            if not file.is_relative_to(folder.resolve()) or digest(file.read_bytes()) != expected:
                raise ValueError("Model package hash mismatch/unsafe path")
        state = json.loads((folder / "state.json").read_text())
        history = state["history"] if updated_history is None else updated_history
        builder = FeatureBuilder(history, **state["feature"])
        obj = cls(state["family"], builder, state["prize"], state["params"])
        obj.training_end, obj.calibration = state["training_end"], state["calibration"]
        obj.metadata, obj.model_version, obj.manifest = state["metadata"], manifest["model_version"], manifest
        if obj.family in FAMILIES[:3]:
            obj.model = TreeModel.load(folder / "model")
        elif obj.family == "transformer":
            from .transformer import TransformerModel
            obj.model = TransformerModel.load(folder / "model", device="cpu")
        elif obj.family == "stack":
            obj.model = ProbabilityStack.load(folder / "stack.json")
        elif obj.family not in ("average",):
            obj.model = Baseline(obj.family, **{k: v for k, v in obj.params.items() if k in ("alpha", "min_history", "backoff")})
        if obj.family in ("average", "stack"):
            obj.children = [cls.load(folder / f"base_{i}", updated_history) for i in range(4)]
        return obj
