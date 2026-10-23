"""Bounded inner chronological search; final test rows are rejected at entry."""
import json
from pathlib import Path
import numpy as np
from .baselines import probabilities
from .evaluation import chronological_folds, metrics
from .data import canonical, digest


def check_development(queries, final_test_start):
    if not queries or any(q["date"] >= final_test_start for q in queries):
        raise ValueError("Tuning/selection input includes reserved final-test outcomes")


def tune(queries, y, evaluate, storage, study_name, final_test_start="2025-01-01", trials=12,
         timeout=3600, seed=1729, family="all"):
    """evaluate(params, train_indices, validation_indices) returns aligned probabilities.

    The outer last date block estimates selection performance. Each trial uses only
    earlier inner expanding-window folds. No outer scores are returned to Optuna.
    """
    import optuna
    check_development(queries, final_test_start)
    outer_train, outer_valid = list(chronological_folds(queries, 4))[-1]
    inner_q = [queries[i] for i in outer_train]
    context = digest(canonical({"queries": queries, "labels": np.asarray(y).tolist(), "family": family,
                                "seed": seed, "final_test_start": final_test_start}))
    study = optuna.create_study(direction="minimize", storage=storage, study_name=study_name,
        load_if_exists=True, sampler=optuna.samplers.TPESampler(seed=seed), pruner=optuna.pruners.MedianPruner())
    if study.user_attrs.get("context", context) != context:
        raise ValueError("Existing study belongs to different data/configuration")
    study.set_user_attr("context", context)
    study.set_user_attr("seed", seed)
    # The caller owns the run lock. A dead worker's trials consume their original
    # slots, rather than expanding the budget every time the command is resumed.
    budget = {"total_trials": trials, "timeout_seconds": timeout}
    if study.user_attrs.get("budgets", budget) != budget:
        raise ValueError("Existing study has another fixed search budget")
    study.set_user_attr("budgets", budget)
    for trial in study.get_trials(states=(optuna.trial.TrialState.RUNNING,)):
        study.tell(trial.number, state=optuna.trial.TrialState.FAIL)

    def objective(trial):
        params = {}
        if family in ("all", "tree"):
            params.update(iterations=trial.suggest_int("iterations", 20, 200), depth=trial.suggest_int("depth", 2, 7),
                          learning_rate=trial.suggest_float("learning_rate", .01, .2, log=True))
        if family in ("all", "transformer"):
            params.update(sequence_length=trial.suggest_categorical("sequence_length", [32, 64, 128]),
                          d_model=trial.suggest_categorical("d_model", [64, 128, 256]),
                          dropout=trial.suggest_float("dropout", 0., .3))
        if family in ("all", "ensemble"):
            weights = np.asarray([trial.suggest_float(f"weight_{i}", .001, 1.) for i in range(4)])
            params["weights"] = (weights / weights.sum()).tolist()
            params["regularization"] = trial.suggest_float("regularization", .001, 100., log=True)
        params["shrink"] = trial.suggest_float("shrink", .001, .8, log=True)
        scores = []
        for step, (tr, va) in enumerate(chronological_folds(inner_q, 3)):
            train, valid = outer_train[tr], outer_train[va]
            p = probabilities(evaluate(params, train, valid))
            scores.append(metrics(np.asarray(y)[valid], p)["log_loss"])
            trial.report(float(np.mean(scores)), step)
            if trial.should_prune():
                raise optuna.TrialPruned()
        trial.set_user_attr("resolved", params)
        return float(np.mean(scores))

    spent = sum((t.datetime_complete - t.datetime_start).total_seconds() for t in study.trials
                if t.datetime_complete and t.datetime_start)
    remaining = max(0, trials - len(study.trials))
    if remaining and spent < timeout:
        study.optimize(objective, n_trials=remaining, timeout=timeout - spent, n_jobs=1)
    params = study.best_trial.user_attrs["resolved"]
    outer = evaluate(params, outer_train, outer_valid)
    return {"params": params, "inner_log_loss": study.best_value,
            "outer_metrics": metrics(np.asarray(y)[outer_valid], outer), "study": study_name,
            "trials": len(study.trials), "context": context,
            "outer_first_date": min(queries[i].get("origin", queries[i]["date"]) for i in outer_valid)}


class TemperatureCalibration:
    def __init__(self, temperature=1.):
        self.temperature = temperature

    def transform(self, p):
        p = probabilities(p)
        z = np.log(np.clip(p, 1e-15, 1)) / self.temperature
        z -= z.max(axis=1, keepdims=True)
        result = np.exp(z)
        return probabilities(result / result.sum(axis=1, keepdims=True))

    def fit(self, p, y, calibration_queries, base_training_end, final_test_start="2025-01-01"):
        check_development(calibration_queries, final_test_start)
        if min(q.get("origin", q["date"]) for q in calibration_queries) <= base_training_end:
            raise ValueError("Calibration overlaps fitted predictor's training period")
        from scipy.optimize import minimize_scalar
        result = minimize_scalar(lambda t: metrics(y, TemperatureCalibration(t).transform(p))["log_loss"],
                                 bounds=(.1, 20.), method="bounded")
        self.temperature = float(result.x)
        self.last_date = max(q["date"] for q in calibration_queries)
        self.base_training_end = base_training_end
        return self


def freeze_policy(path, policy):
    """Create the immutable selection contract before final-test evaluation."""
    if policy["selection_end"] >= policy["final_test_start"]:
        raise ValueError("Selection crosses final test")
    payload = {**policy, "policy_hash": digest(canonical(policy))}
    with Path(path).open("x", encoding="utf-8") as stream:
        json.dump(payload, stream, sort_keys=True, indent=2)
    return payload
