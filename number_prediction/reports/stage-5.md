# Stage 5: Hyperparameter optimization and probability calibration

Status: implementation and local pilot verified; full stage acceptance remains pending the work below.

Optuna studies persist seeds, budgets, pruning state and parameters. Inner expanding-window scores choose settings; a later outer block estimates selection. Calibration fits on a separate later chronological segment and is evaluated afterward. The default final policy freezes model weights and updates past-only history. Final scoring needs a matching frozen policy.

## Actual validation

One real CatBoost Optuna trial completed on 2007 development data, with a 60-second cap; the synthetic study/final-test/calibration-boundary tests pass. Calibration selection was exercised for all 22 real pilot candidates. Final period was not scored.

## Remaining acceptance

Run the agreed bounded server search, compare daily/weekly/monthly retraining in development, predeclare resources and comparison counts, then freeze the selected methods. The daily/weekly/monthly comparison tool ran a seven-day 2007 development pilot: seven daily refits and one each for weekly/monthly. This is not a full server policy-selection experiment.

Code and data hashes, measured metrics, environment and limitations are recorded in `local-evidence.json`. No GPU, Windows, final-test or future result is claimed.
