# Small GPU pilot passed

The local RTX 2000 Ada Generation Laptop GPU (8 GB) is working with NVIDIA driver 595.99.02 and Secure Boot enabled. The new isolated `.venv-cuda` uses Torch 2.6.0+cu124 / CUDA 12.4, CatBoost 1.2.8, full XGBoost 3.0.2 and LightGBM 4.6.0. The original CPU environment is preserved. LightGBM uses the NVIDIA OpenCL device; the other learned backends use CUDA. A real CUDA tensor computation passed before model fitting, and `pip check` found no broken requirements.

## Measured outcomes

| Check | Result |
|---|---|
| GPU recovery/native-load regressions | 4 passed, 0 failed |
| CPU prediction regressions | 29 passed, 0 failed; the 4 opt-in GPU tests were skipped in this CPU invocation |
| Standard-library archive regressions | 36 passed, 0 failed |
| Real pilot | All 11 predictors × both prizes = 22 results passed |
| Probabilities and class mapping | Finite, nonnegative, normalized 100-class outputs, ordered 00–99 |
| Original CPU environment loading GPU-trained packages | All 22 matched reference probabilities at atol 1e-6 / rtol 1e-5; largest observed absolute difference 5.64e-10 |
| Resume completed GPU pilot | All 22 results reused; 300 native model/checkpoint files unchanged in size, timestamp and SHA-256 |
| Actual native training device | Recorded for all tree fits; silent XGBoost CPU fallback is rejected |

The accepted run is `number_prediction/runs/gpu-2007-20261022`. Its immutable snapshot is `post-xsmt-20261022T1936`, version `2c1037f153a3818ae1272614239bb85b7c9c82cac9a56cf8a3a3ac4fd9844a58`, containing both canonical regions.

Training used 2007-08-18–2007-10-15, calibration through 2007-11-15 and validation through 2007-12-31. G.8 had 312 / 164 / 243 examples in those segments; G.ĐB had 321 / 168 / 250. Development inference probes used 2008-01-01–2008-01-07 without scoring those outcomes.

Each learned family fitted 12 tiny models, including standalone predictors, ensemble bases and chronological stacking folds: 48 underlying GPU fits. Every tree fit was configured for at most eight iterations; every Transformer fit used one epoch, dimensions 16, two heads, one layer and sequence length eight. CPU threads were limited to two per process. Separate synthetic recovery probes also stayed within eight rounds or one tiny GPU epoch per fit. Per-family fit/calibration/evaluation time summed to approximately 46.10 seconds; package writes, setup and verification are separate. This is an integration check, not a speed benchmark or server runtime estimate.

## Recovery and remaining limits

Transformer AMP/dropout resumed after an abrupt process exit at saved batch 2, including optimizer, scheduler, scaler and random states. XGBoost and LightGBM resumed their native GPU models after saved boosting round 3. Resumed results matched uninterrupted results within documented tolerances. GPU-trained native models from all four learned families loaded for CPU inference.

CatBoost passed completed GPU native-snapshot reload. **Mid-fit CatBoost GPU interruption remains untested**; GPU callbacks are unavailable, and this result must not be described as a mid-fit GPU recovery acceptance. Native timed snapshots are implemented, with separate process/STOP handling documented in the recovery guide.

PyTorch warned that memory-efficient CUDA attention can use nondeterministic backward execution in warning-only mode. The measured GPU recovery tolerances passed; bitwise-identical trajectories are not promised. NVIDIA OpenCL emitted generic kernel-compiler warning lines, but backend, probability, native persistence and recovery checks passed.

These checks ran locally through approved host execution because the agent sandbox did not expose GPU devices. Actual training-server, Windows, multi-GPU, unattended reboot and pre-login service acceptance remain separate work. No training service was enabled. CPU inference agreement here is Linux-to-Linux; it does not establish Windows acceptance.

Only small development fits ran. No full experiment grid, archive hyperparameter search, full server training or reserved final-test scoring occurred. The 2025-01-01–2026-10-21 final test remains untouched. A small integration pass does not establish predictive advantage. Raw archives, canonical snapshots and prior runs were preserved. Source changes remain local and have not been published to GitHub.

## Reuse and transfer

The source-only deliverable is `loto-prediction-source-gpu-tested.zip`. It excludes datasets, fitted models, checkpoints and environments. Transfer the immutable snapshot and complete stopped run directory, including hidden `.recovery/`, separately to the server. Recreate the environment there; do not copy this laptop's virtual environment. GPU builds, device identities and driver compatibility must be checked on the actual server before training.

The tested dependency freeze is `number_prediction/requirements-tested-cuda-linux.txt`; install the pinned Torch CUDA wheel from the official index and the server requirements in a fresh environment. Follow `number_prediction/RECOVERY.md` for explicit opt-in GPU tests, identical-context resume, STOP, locks and bounded restart supervision.
