"""Native tree persistence with explicit missing-class alignment; no fake labels."""
import json
from pathlib import Path
import numpy as np
from .baselines import align


class TreeModel:
    def __init__(self, family, seed=1729, iterations=100, depth=5, learning_rate=.05, threads=2,
                 shrink=.01, device="cpu", gpu_platform_id=None, gpu_device_id=None, catboost_logging_level="Silent"):
        if family not in ("catboost", "xgboost", "lightgbm"):
            raise ValueError("Unknown learned family")
        if device not in ("cpu", "cuda"):
            raise ValueError("Device must be cpu or cuda")
        self.params = dict(family=family, seed=seed, iterations=iterations, depth=depth,
                           learning_rate=learning_rate, threads=threads, shrink=shrink, device=device,
                           gpu_platform_id=gpu_platform_id, gpu_device_id=gpu_device_id,
                           catboost_logging_level=catboost_logging_level)
        self.model = None

    def fit(self, x, y, checkpoint=None, checkpoint_every=100, stop_check=None, after_checkpoint=None,
            _catboost_resume_child=False):
        from .recovery import CheckpointStore, StopRequested, array_signature, ensure_context
        import importlib.metadata
        p = self.params
        if p["iterations"] < 1 or checkpoint_every < 1:
            raise ValueError("Iterations and checkpoint interval must be positive")
        self.classes, encoded = np.unique(y, return_inverse=True)
        if not len(self.classes):
            raise ValueError("Cannot train on empty labels")
        store, saved, completed = None, None, 0
        if checkpoint is not None:
            package = "xgboost" if p["family"] == "xgboost" else p["family"]
            try:
                version = importlib.metadata.version(package)
            except importlib.metadata.PackageNotFoundError:
                version = importlib.metadata.version("xgboost-cpu")
            checkpoint = ensure_context(checkpoint, {"params": p, "version": version,
                "arrays": array_signature([x, y])})
            store = CheckpointStore(checkpoint / "rounds")
            saved = store.load()
            completed = saved[1]["rounds"] if saved else 0
        self.resumed_from_round = completed
        if stop_check:
            stop_check()
        if len(self.classes) == 1:
            return self
        common = {"learning_rate": p["learning_rate"]}

        def commit(model, rounds, suffix):
            actual = (json.loads(model.save_config())["learner"]["generic_param"]["device"]
                      if p["family"] == "xgboost" else model.params["device_type"])
            if p["family"] == "xgboost" and p["device"] == "cuda" and not actual.startswith("cuda"):
                raise RuntimeError("XGBoost fell back to CPU despite a CUDA request; GPU acceptance failed")
            if store:
                store.commit(lambda path: model.save_model(str(path)), suffix,
                             {"rounds": rounds, "training_device": actual}, after_checkpoint)
            if stop_check:
                stop_check()

        def needs_checkpoint(rounds):
            required = rounds % checkpoint_every == 0 or rounds == p["iterations"]
            if stop_check:
                try:
                    stop_check()
                except StopRequested:
                    required = True
            return required

        if p["family"] == "catboost":
            if checkpoint is not None and (checkpoint / "invalid-snapshot.json").exists():
                raise ValueError("CatBoost rejected its native snapshot; preserve invalid-snapshot.json and inspect its backup")
            if checkpoint is not None and not _catboost_resume_child and (checkpoint / "native.snapshot").exists():
                from .catboost_recovery import resume
                return resume(self, x, y, checkpoint, stop_check, after_checkpoint)
            from catboost import CatBoostClassifier
            options = {}
            if p["device"] == "cuda":
                options["devices"] = "0"  # logical device zero within CUDA_VISIBLE_DEVICES
            if checkpoint is not None:
                options.update(save_snapshot=True, snapshot_file=str((checkpoint / "native.snapshot").resolve()),
                           snapshot_interval=1, train_dir=str((checkpoint / "native-log").resolve()))
            self.model = CatBoostClassifier(iterations=p["iterations"], depth=p["depth"],
                random_seed=p["seed"], thread_count=p["threads"], task_type="GPU" if p["device"] == "cuda" else "CPU",
                loss_function="MultiClass", logging_level=p["catboost_logging_level"], allow_writing_files=checkpoint is not None, **common, **options)
            # CatBoost's own snapshot retains its internal random/boosting state.
            # GPU callbacks are unsupported: native timed snapshots still protect hard interruptions.
            callbacks = []
            if p["device"] == "cpu":
                class Progress:
                    def after_iteration(inner, info):
                        if after_checkpoint:
                            after_checkpoint({"rounds": info.iteration,
                                "native_snapshot": bool(checkpoint and (checkpoint / "native.snapshot").exists())})
                        if stop_check:
                            try:
                                stop_check()
                            except StopRequested:
                                return False
                        return True
                callbacks = [Progress()]
            self.model.fit(x, encoded, callbacks=callbacks or None)
            if stop_check:
                stop_check()
        elif p["family"] == "xgboost":
            import xgboost as xgb
            if p["device"] == "cuda" and not xgb.build_info().get("USE_CUDA", False):
                raise RuntimeError("This XGBoost build has no CUDA support; install the server build or select CPU")
            initial = xgb.Booster(model_file=str(saved[0])) if saved else None
            if completed >= p["iterations"]:
                self.model = initial
                self.training_device = saved[1].get("training_device")
                return self
            class Progress(xgb.callback.TrainingCallback):
                def after_iteration(inner, model, epoch, evals_log):
                    rounds = completed + epoch + 1
                    if needs_checkpoint(rounds):
                        commit(model, rounds, ".ubj")
                    return False
            self.model = xgb.train({"objective": "multi:softprob", "num_class": len(self.classes),
                "seed": p["seed"], "max_depth": p["depth"], "nthread": p["threads"],
                "device": p["device"], "tree_method": "hist", **common},
                xgb.DMatrix(x, label=encoded), num_boost_round=p["iterations"] - completed,
                xgb_model=initial, callbacks=[Progress()] if store or stop_check else None)
            actual = json.loads(self.model.save_config())["learner"]["generic_param"]["device"]
            if p["device"] == "cuda" and not actual.startswith("cuda"):
                raise RuntimeError("XGBoost fell back to CPU despite a CUDA request; GPU acceptance failed")
            self.training_device = actual
        else:
            import lightgbm as lgb
            if completed >= p["iterations"]:
                self.model = lgb.Booster(model_file=str(saved[0]))
                self.training_device = saved[1].get("training_device")
                return self
            def progress(env):
                rounds = completed + env.iteration - env.begin_iteration + 1
                if needs_checkpoint(rounds):
                    commit(env.model, rounds, ".txt")
            gpu_options = {k: p[k] for k in ("gpu_platform_id", "gpu_device_id") if p[k] is not None} if p["device"] == "cuda" else {}
            self.model = lgb.train({"objective": "multiclass", "num_class": len(self.classes),
                "seed": p["seed"], "max_depth": p["depth"], "num_leaves": min(31, 2 ** p["depth"]),
                "num_threads": p["threads"], "device_type": "gpu" if p["device"] == "cuda" else "cpu",
                "verbosity": -1, "deterministic": p["device"] == "cpu", "force_col_wise": True, **common, **gpu_options},
                lgb.Dataset(x, label=encoded), num_boost_round=p["iterations"] - completed,
                init_model=str(saved[0]) if saved else None, callbacks=[progress] if store or stop_check else None)
        if p["family"] == "catboost":
            self.training_device = self.model.get_all_params()["task_type"].lower()
        elif p["family"] == "lightgbm":
            self.training_device = self.model.params["device_type"]
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
        (folder / "metadata.json").write_text(json.dumps({"params": self.params, "classes": self.classes.tolist(),
            "training_device": getattr(self, "training_device", None)}), encoding="utf-8")
        if self.model is not None:
            name = {"catboost": "model.cbm", "xgboost": "model.ubj", "lightgbm": "model.txt"}[self.params["family"]]
            self.model.save_model(str(folder / name))

    @classmethod
    def load(cls, folder):
        folder = Path(folder)
        meta = json.loads((folder / "metadata.json").read_text(encoding="utf-8"))
        obj = cls(**meta["params"])
        obj.classes = np.asarray(meta["classes"])
        obj.training_device = meta.get("training_device")
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
