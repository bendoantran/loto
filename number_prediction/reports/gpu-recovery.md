# Loto GPU readiness and training recovery

Recovery is implemented and tested locally. The owner subsequently approved NVIDIA driver installation, which completed successfully at version 595.99.02 with Canonical-signed kernel modules and a clean package audit. The laptop still uses Nouveau until restart; the owner-controlled restart is pending. The working environment remains Torch 2.6.0+cpu. No GPU training occurred.

## Measured checks

| Check | Result |
|---|---|
| Prediction regression suite | 29 passed, 0 failed |
| Standard-library archive suite | 36 passed, 0 failed |
| Forced worker death and native tree recovery | CatBoost, XGBoost and LightGBM passed; resumed probabilities matched uninterrupted CPU fits within 1e-12 |
| Transformer interrupted mid-epoch with dropout | Passed; resumed weights, validation losses and probabilities matched exactly on CPU |
| Interrupted package publication | Passed; committed results were reused after a crash before publication |
| Ensemble continuation, corruption, changed context, locks, STOP, retry limits | Passed |
| Final real-data pilot | All 11 predictors × both prizes = 22 results passed |
| Completed pilot resumed | 22 results reused; 288 native/checkpoint files unchanged in size, timestamp and hash |
| Actual bounded supervisor execution | Passed; one successful attempt reused the completed pilot |
| Generated systemd user unit | Read-only systemd validation exited 0; not installed, enabled or reboot-tested |

The accepted pilot uses `number_prediction/runs/recovery-2007-accepted-20261022` and snapshot `post-xsmt-20261022T1936`, version `2c1037f153a3818ae1272614239bb85b7c9c82cac9a56cf8a3a3ac4fd9844a58`. It draws from both complete canonical regions and preserves leading-zero/quality/chronology policies. Train: 2007-08-18–2007-10-15; calibration through 2007-11-15; validation through 2007-12-31. G.8 has 312/164/243 targets across those segments; G.ĐB has 321/168/250.

Each learned family fitted 12 tiny models in the accepted pilot, including its individual predictor, ensemble bases and chronological stacking folds: 48 underlying fits total. Trees used eight iterations; Transformers used one epoch, 16 dimensions, two heads, one layer and sequence length eight. CPU threads were limited to two per process. Two earlier tiny pilot destinations were retained while refining recovery/service generation; none was overwritten. The final accepted pilot has about 28.68 seconds summed per-family fitting/report time. Resuming and supervising its completed results added no fits.

The five baselines, four learned families and two ensemble methods produced finite, nonnegative, normalized 100-class probabilities. Native packages loaded and produced normalized development probes after the selection cutoff. Regression checks still enforce strict predict-before-reveal, target quality, leading zeros and the reserved final-test boundary. Small integration success does not establish predictive advantage.

## Recovery behavior

`train.py --resume` checks the snapshot, settings, code, package/runtime versions, thread limits and visible GPUs before continuing. Transformer state includes optimizer, scheduler, AMP scaler, early-stop best state/history, shuffle order/cursor and all relevant random generators. XGBoost and LightGBM resume native boosting rounds; CatBoost uses native timed snapshots. Completed ensemble bases and chronological folds are reused. Native CatBoost snapshots are library-managed; other checkpoint generations use checksums, fsync and atomic publication, retaining two committed generations.

Run and grid locks prevent duplicate workers and release after process death. STOP remains durable; deliberate stops are not treated as failures to retry. The supervisor preserves a bounded retry budget across process restarts. Completed results, packages and reports are verified rather than overwritten. Fixed Optuna budgets no longer expand on resume. Expensive feature construction, calibration and the small stack optimizer may recompute from committed stages; latest-checkpoint corruption fails for inspection rather than silently resetting.

The generated user unit and restart instructions are ready for review. No training service starts automatically on this laptop. Actual server, CUDA/AMP, Windows, pre-login startup and reboot acceptance remain unmeasured. Windows-oriented fsync handles and explicit UTF-8 text/config/CLI handling are implemented, but Linux tests do not establish Windows acceptance.

## Restart and transfer

A reboot is a normal full-computer restart. It closes apps and stops processes; saved data/checkpoints in Documents remain. Reopen Codex and this chat afterwards and say “continue the GPU test.” The continuation state, exact run locations and next steps are saved in `loto-reboot-handoff.md`. No work can execute while the computer is off, and this chat requires Codex to be reopened.

Git and the source ZIP exclude modeling snapshots, fitted models, environments and recovery state. Transfer the complete immutable snapshot and stopped run/grid directory, including hidden `.recovery/` and SQLite study files, separately when moving to the server. Preserve old copies and do not merge concurrent writers.

No collector changes, historical rescraping, full experiment grid, expensive archive search, server/GPU full training or final-test scoring occurred. The reserved 2025-01-01–2026-10-21 test remains untouched. All current source changes remain local; they have not been published to GitHub.
