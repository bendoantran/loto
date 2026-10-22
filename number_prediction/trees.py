"""Native tree persistence with explicit missing-class alignment; no fake labels."""
import json
from pathlib import Path
import numpy as np
from .baselines import align


class TreeModel:
    def __init__(self, family, seed=1729, iterations=100, depth=5, learning_rate=.05, threads=2,
                 shrink=.01, device="cpu"):
        if family not in ("catboost", "xgboost", "lightgbm"):
            raise ValueError("Unknown learned family")
        if device not in ("cpu", "cuda"):
            raise ValueError("Device must be cpu or cuda")
        self.params = dict(family=family, seed=seed, iterations=iterations, depth=depth,
                           learning_rate=learning_rate, threads=threads, shrink=shrink, device=device)
        self.model = None

    def fit(self, x, y):
        p = self.params
        self.classes, encoded = np.unique(y, return_inverse=True)
        if not len(self.classes):
            raise ValueError("Cannot train on empty labels")
        if len(self.classes) == 1:
            return self
        common = {"learning_rate": p["learning_rate"]}
        if p["family"] == "catboost":
            from catboost import CatBoostClassifier
            self.model = CatBoostClassifier(iterations=p["iterations"], depth=p["depth"],
                random_seed=p["seed"], thread_count=p["threads"], task_type="GPU" if p["device"] == "cuda" else "CPU",
                loss_function="MultiClass", verbose=False, allow_writing_files=False, **common)
            self.model.fit(x, encoded)
        elif p["family"] == "xgboost":
            import xgboost as xgb
            if p["device"] == "cuda" and not xgb.build_info().get("USE_CUDA", False):
                raise RuntimeError("This XGBoost build has no CUDA support; install the server build or select CPU")
            self.model = xgb.train({"objective": "multi:softprob", "num_class": len(self.classes),
                "seed": p["seed"], "max_depth": p["depth"], "nthread": p["threads"],
                "device": p["device"], "tree_method": "hist", **common},
                xgb.DMatrix(x, label=encoded), num_boost_round=p["iterations"])
        else:
            import lightgbm as lgb
            self.model = lgb.train({"objective": "multiclass", "num_class": len(self.classes),
                "seed": p["seed"], "max_depth": p["depth"], "num_leaves": min(31, 2 ** p["depth"]),
                "num_threads": p["threads"], "device_type": "gpu" if p["device"] == "cuda" else "cpu",
                "verbosity": -1, "deterministic": p["device"] == "cpu", "force_col_wise": True, **common},
                lgb.Dataset(x, label=encoded), num_boost_round=p["iterations"])
        return self

    def predict_proba(self, x):
        if len(self.classes) == 1:
            raw = np.ones((len(x), 1))
        elif self.params["family"] == "catboost":
            raw = self.model.predict_proba(x)
        elif self.params["family"] == "xgboost":
            import xgboost as xgb
            raw = self.model.predict(xgb.DMatrix(x))
        else:
            raw = self.model.predict(x)
        return align(raw, self.classes, self.params["shrink"])

    def save(self, folder):
        folder = Path(folder)
        folder.mkdir(parents=True, exist_ok=False)
        (folder / "metadata.json").write_text(json.dumps({"params": self.params, "classes": self.classes.tolist()}))
        if self.model is not None:
            name = {"catboost": "model.cbm", "xgboost": "model.ubj", "lightgbm": "model.txt"}[self.params["family"]]
            self.model.save_model(str(folder / name))

    @classmethod
    def load(cls, folder):
        folder = Path(folder)
        meta = json.loads((folder / "metadata.json").read_text())
        obj = cls(**meta["params"])
        obj.classes = np.asarray(meta["classes"])
        if len(obj.classes) > 1:
            if obj.params["family"] == "catboost":
                from catboost import CatBoostClassifier
                obj.model = CatBoostClassifier()
                obj.model.load_model(str(folder / "model.cbm"))
            elif obj.params["family"] == "xgboost":
                import xgboost as xgb
                obj.model = xgb.Booster()
                obj.model.load_model(str(folder / "model.ubj"))
                obj.model.set_param({"device": "cpu", "nthread": obj.params["threads"]})
            else:
                import lightgbm as lgb
                obj.model = lgb.Booster(model_file=str(folder / "model.txt"))
        return obj
