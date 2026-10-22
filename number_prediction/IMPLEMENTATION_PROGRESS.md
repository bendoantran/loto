# Prediction implementation progress — 2026-10-22

Implementation lives in `number_prediction/`; collector code, fixed ranges, checkpoints and progress displays were preserved. No subagents were used. The existing checkout contains prior uncommitted XSMT implementation work, which was reused without resetting it.

| Original stage | Implementation and local verification | Acceptance still requiring measured work |
|---|---|---|
| 1. Data loading, validation, feature engineering, baselines | Read-only verified snapshots; both-region schemas; quality decisions; calendar indices; causal features; five baselines; initial snapshot and tests | Finish/audit XSMT full collection; verify aliases before any merge; later-period XSMT coverage |
| 2. CatBoost, XGBoost, LightGBM | Native wrappers, missing-class alignment, CPU save/load, synthetic dependency tests and real development pilot | Full region/province/input comparisons and server GPU compatibility |
| 3. PyTorch causal Transformer | Configurable reference architecture and two masked heads; CPU training/persistence; causal/padding tests; small real pilot | Reference-size server training, GPU/mixed-precision measurements |
| 4. Weighted ensemble and leakage-free stacking | Constrained averaging; four-model chronological OOF stack; fold evidence; real pilot | Full-scale development comparisons and sensitivity |
| 5. Optimization and calibration | Bounded nested chronological Optuna; persistent studies; separate later calibration; conservative selection policy | Full bounded searches, resource/retraining-policy selection; untouched final assessment |
| 6. Backtesting, inference, tests, documentation | Historical record-before-score backtester; append-only prospective ledger; schedule/horizon checks; exports; portable ZIP and CPU benchmark tools | Final reserved test after full method freeze; actual server/Windows acceptance; future prospective scoring |

All six stages have implementation and local pilot coverage. This is **not full project acceptance**. Full experiments, final-test results, GPU training, Windows benchmarks and prospective outcomes are not fabricated or marked completed.

## Fixed data snapshot

`datasets/initial/manifest.json` version: `e0b42c7b43cc075a622b9fa67045d6bfa9d307e385f8966d65c65f68ae10742c`.

- XSMN: all 7,005 exported dates; 43,098 accepted prize targets.
- XSMT: 690 exported dates at capture; 3,144 accepted prize targets; full collection remains incomplete.
- Total accepted targets: 46,242. Targets remain grouped into province/date observations with separate prize masks.
- Exclusions: 82 invalid-width G.8 targets and four target/unresolved-quality cases. 104 targets with documented unrelated-tier anomalies remain eligible. Review/no-draw dates retain their source states and do not become invented labels.
- Final test reserved before modeling: 2025-01-01 through 2026-10-21. No final-test scores were computed.

## Actual local evidence

- Ubuntu 26.04.1 LTS, Python 3.12.9; isolated CPU environment.
- Original full XSMN baseline audit passed: 7,005 dates, 21,592 draws, 388,656 number appearances; 95 flagged dates, 133 no-draw dates, two review gaps preserved.
- `tools/restore_snapshot.py --verify-files`: `existing_checkpoint_preserved`.
- Original archive/region regression suite: 36 tests passed before and after implementation.
- New prediction suite: 20 tests passed, including CLI entrypoints, source/Excel/quality validation, future-date invariance, causal attention, chronological folds, all model/package round trips, immutable ledger and injected dependencies.
- Real-data pilot: train 2007-08-18–2007-10-15, calibration through 2007-11-15, comparison through 2007-12-31. All 11 predictors ran for each prize using the smaller `pilot.json`; this is 22 pilot fits/comparisons, not the full reference experiment.
- A real CatBoost Optuna trial ran with inner/outer chronological separation and a persisted study. A small seven-day development comparison exercised daily/weekly/monthly refits.
- Development historical backtests and prospective uniform forecast recording ran. Prospective outcomes have not arrived/scored.
- Private GitHub metadata confirmed repository visibility `private`. No data/credentials were sent to a public host.

Focused evidence and command details are under `reports/`. Generated snapshots, weights, studies, runs and ledgers remain local/ignored. The next acceptance work is to complete XSMT collection, run bounded server comparisons with a fixed complete-enough snapshot, freeze a method, score the reserved test once under that policy, and measure the CPU package on the actual Windows computer. Access to those target machines was not supplied.
