# Prediction implementation progress — 2026-10-22

Implementation lives in `number_prediction/`; collector code, fixed ranges, checkpoints and progress displays were preserved. No subagents were used. The existing checkout contains prior uncommitted XSMT implementation work, which was reused without resetting it.

| Original stage | Implementation and local verification | Acceptance still requiring measured work |
|---|---|---|
| 1. Data loading, validation, feature engineering, baselines | Read-only verified snapshots; both-region schemas; quality decisions; calendar indices; causal features; five baselines; initial snapshot and tests | XSMT collection and full audit completed; verify aliases before any merge; full model comparisons pending |
| 2. CatBoost, XGBoost, LightGBM | Native wrappers, missing-class alignment, CPU save/load, synthetic dependency tests and real development pilot | Full region/province/input comparisons and server GPU compatibility |
| 3. PyTorch causal Transformer | Configurable reference architecture and two masked heads; CPU training/persistence; causal/padding tests; small real pilot | Reference-size server training, GPU/mixed-precision measurements |
| 4. Weighted ensemble and leakage-free stacking | Constrained averaging; four-model chronological OOF stack; fold evidence; real pilot | Full-scale development comparisons and sensitivity |
| 5. Optimization and calibration | Bounded nested chronological Optuna; persistent studies; separate later calibration; conservative selection policy | Full bounded searches, resource/retraining-policy selection; untouched final assessment |
| 6. Backtesting, inference, tests, documentation | Historical record-before-score backtester; append-only prospective ledger; schedule/horizon checks; exports; portable ZIP and CPU benchmark tools | Final reserved test after full method freeze; actual server/Windows acceptance; future prospective scoring |

All six stages have implementation and local pilot coverage. This is **not full project acceptance**. Full experiments, final-test results, GPU training, Windows benchmarks and prospective outcomes are not fabricated or marked completed.

## Fixed data snapshot

`datasets/initial/manifest.json` version: `e0b42c7b43cc075a622b9fa67045d6bfa9d307e385f8966d65c65f68ae10742c`.

- XSMN: all 7,005 exported dates; 43,098 accepted prize targets.
- XSMT: 690 exported dates at capture; 3,144 accepted prize targets; collection was incomplete at that initial capture.
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

Focused evidence and command details are under `reports/`. Generated snapshots, weights, studies, runs and ledgers remain local/ignored. XSMT collection and full audit have since completed; see the completion report below. Remaining acceptance work is authorized full server comparisons, method freeze/final-test scoring, and actual Windows measurement. Access to those target machines was not supplied.

## Post-XSMT completion verification

See [reports/post-xsmt-completion.md](reports/post-xsmt-completion.md). Both full archives passed audit; the new immutable snapshot has 75,424 eligible prize targets and complete export coverage. The bounded 2007 CPU pilot ran all 11 predictors for both prizes; all 22 packages passed probability/persistence checks. There are now 22 prediction tests plus 36 archive tests passing locally. Explicit UTF-8 persistence/CLI handling and restoration of stacking audit metadata were repaired. Full training, tuning and final-test scoring remain unstarted.

## Small GPU request and long-run recovery — 2026-10-22

Implemented atomic checksummed checkpoint generations, complete Transformer batch/optimizer/scheduler/scaler/RNG/early-stop recovery, native tree continuation, cached ensemble/fold fits, guarded `train.py --resume`, verified serial grid continuation, fixed total Optuna budgets, exclusive locks, durable STOP and a bounded persistent supervisor. Added GPU readiness inspection and a reviewable systemd user-unit generator. Unit verification caught and repaired service ordering/path quoting; final read-only validation passed. No service was installed or enabled.

Final measured evidence: 29 prediction and 36 archive regressions passed. Abrupt-death recovery passed for all four learned families; CPU Transformer dropout recovery was exact. The accepted 2007 pilot is `runs/recovery-2007-accepted-20261022`, using the full post-XSMT snapshot and the original tiny settings/split. All 22 predictor/prize results passed. Its 48 underlying tiny fits comprise 12 per learned family, including ensembles and stacking folds. A subsequent resume reused all results with 288 native/checkpoint files unchanged; the real supervisor then reused that completed run successfully. Earlier tiny pilot destinations are preserved.

GPU hardware is an RTX 2000 Ada Generation Laptop GPU, but the active Nouveau driver and Torch 2.6.0+cpu provide no CUDA. No GPU fit ran. Driver installation was only simulated; approval to install and an owner-controlled reboot are still pending. Actual GPU/AMP recovery, server/Windows inference and live reboot service acceptance remain outstanding. No full experiment grid, archive hyperparameter search or final-test scoring ran. See `RECOVERY.md` and `reports/gpu-recovery.md`/`.json`. A persistent restart handoff and source-only ZIP are saved in the chat's outputs directory. All work remains local.

The owner subsequently approved NVIDIA installation. Ubuntu driver installation exited 0; driver 595.99.02 and Canonical-signed kernel modules are installed, with a clean dpkg audit. Secure Boot remains enabled. Nouveau remains active until the owner restarts. No GPU fit or reboot has occurred. Continuation state and the restart handoff have been updated; no additional installation approval is needed.

## Local GPU pilot acceptance — 2026-10-22

After the owner's restart, NVIDIA 595.99.02 is active on the RTX 2000 Ada laptop GPU (8 GB), with Secure Boot enabled. A separate ignored `.venv-cuda` was prepared with Torch 2.6.0+cu124, full XGBoost 3.0.2, CatBoost 1.2.8 and LightGBM 4.6.0; the CPU environment was preserved. CUDA tensor execution and the NVIDIA OpenCL device were verified. Actual GPU jobs used approved host execution because the agent sandbox hid GPU device nodes.

The bounded 2007 pilot `runs/gpu-2007-20261022` passed all 22 predictor/prize comparisons using both canonical regions. It used at most eight tree iterations, one tiny Transformer epoch, dimensions 16, two heads, one layer, sequence length eight and two CPU threads. Its 48 underlying fits comprise 12 per learned family including ensembles and chronological folds. Native training-device metadata is persisted, and XGBoost silent CPU fallback is rejected. All outputs have finite normalized 100-class probabilities and stable leading-zero class order.

Four explicit GPU regression tests passed: Transformer AMP/dropout batch interruption/resume; XGBoost and LightGBM GPU round interruption/resume; completed CatBoost GPU native-snapshot reload; and native CPU inference loading. CPU prediction regressions passed 29 tests (4 opt-in GPU skips in that invocation); archive regressions passed 36. All 22 GPU-trained packages loaded and matched in the original CPU environment at atol 1e-6 / rtol 1e-5 (largest observed absolute difference 5.64e-10). Completed-run resume reused all results and left 300 native/checkpoint files unchanged.

CatBoost mid-fit GPU interruption is not accepted by these tests. PyTorch warned about nondeterministic memory-efficient attention backward execution; GPU state recovery passed numerical tolerances, not a bitwise reproducibility guarantee. Actual server, Windows, multi-GPU and unattended reboot acceptance remain outstanding. No full grid, archive tuning or final-test scoring ran. See `reports/gpu-pilot.md`/`.json`, `RECOVERY.md`, and `requirements-tested-cuda-linux.txt`. Persistent follow-up state marks this small GPU request complete, so it must not repeat automatically.

## No-sudo server transfer acceptance — 2026-10-22

78 distinct regressions passed (36 CPU prediction, six GPU, 36 archive), plus a fresh offline installation under ASCII locale in a Unicode/spaced path and all 22 small 2007 predictor/prize checks. The final bundle contains Python 3.12.15, 58 pinned binary wheels and the completed 75,424-target modeling snapshot. A detached real-data pilot stopped/resumed with 18 committed CatBoost files unchanged; completed resume preserved 300 native/checkpoint files. All 22 packages matched separate CPU inference. CatBoost mid-fit GPU recovery and corruption refusal are now tested; native snapshot load failures are isolated, backed up and blocked from silent retraining. Strict Transformer determinism, allocated CUDA/OpenCL UUID matching, full source/eligibility hash verification and UTF-8 launcher handling are implemented. See SERVER.md and the chat output loto-server-transfer-results.md/.json. Actual server/Windows/full-size resource acceptance and predictive advantage remain unestablished. No full training or reserved final-test scoring ran; GitHub was not updated.
