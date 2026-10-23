# Training recovery and GPU readiness

For the no-sudo offline server bundle and simpler launch commands, see [SERVER.md](SERVER.md). Its detached launcher preserves STOP requests, refuses duplicate writers, checks the actual allocated CUDA/OpenCL GPU, and grants a new bounded retry allowance only on explicit resume. It survives an ordinary terminal disconnection; automatic boot startup still needs an allowed scheduler/user-service policy.

Use one immutable modeling snapshot per run and a local persistent filesystem with atomic rename and kernel locks. Archive checkpoints and model-training checkpoints are separate. These commands never start or restart a collector. No full server training or automatic reboot was performed. The owner-approved NVIDIA installation and subsequent local GPU acceptance are recorded in `reports/gpu-pilot.md`.

## Inspect CUDA before a GPU pilot

From the repository root, using the isolated training environment:

```bash
PY=number_prediction/.venv/bin/python
$PY number_prediction/gpu_check.py --require-cuda --out number_prediction/runs/gpu-readiness.json
```

Exit 2 means CUDA is unavailable; it does not fall back and label a CPU fit as GPU. The development laptop now runs NVIDIA driver 595.99.02 on its RTX 2000 Ada Generation Laptop GPU (8 GB), with Secure Boot enabled. Its separate `.venv-cuda` uses Torch 2.6.0+cu124, full XGBoost 3.0.2, CatBoost 1.2.8 and LightGBM 4.6.0. The original `.venv` remains CPU-only. All four learned families passed local GPU checks; LightGBM uses NVIDIA OpenCL. CatBoost, full XGBoost, LightGBM and Torch have different GPU build requirements; one successful Torch kernel alone does not establish all-library GPU compatibility. The agent sandbox hid GPU device nodes, so actual GPU jobs used approved host execution; an unavailable sandbox device does not prove a host driver failure.

A GPU pilot must use the small 2007 split and tiny settings from `pilot.json`, with explicit `device: "cuda"` in a copied model configuration. Do not change the original pilot settings or start the default full grid to test the GPU. The accepted local pilot is `runs/gpu-2007-20261022`: eight tree rounds, one tiny Transformer epoch, both regions and both prizes. All 22 predictor/prize packages passed, including original-CPU-environment inference agreement (atol 1e-6, rtol 1e-5). No actual Windows or training-server acceptance is implied.

GPU regressions are opt-in and bounded. With the CUDA environment prepared, run:

```bash
env CUDA_VISIBLE_DEVICES=0 CUBLAS_WORKSPACE_CONFIG=:4096:8 \
  OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 MKL_NUM_THREADS=2 NUMEXPR_NUM_THREADS=2 \
  LOTO_GPU_TESTS=1 number_prediction/.venv-cuda/bin/python \
  -m unittest number_prediction.tests.test_gpu -v
```

These checks measure Transformer AMP batch interruption/resume, XGBoost and LightGBM GPU round interruption/resume, completed CatBoost GPU native-snapshot reload, and GPU-trained packages loaded for CPU inference. CatBoost mid-fit GPU interruption remains unmeasured. CPU-only runs skip these four tests unless explicitly enabled; requested GPU tests fail if CUDA is missing. XGBoost's actual training device is checked to reject silent CPU fallback. Tree metadata and round checkpoints retain the observed training device.

## Resume an interrupted training command

Repeat the original command, adding `--resume`. Keep its data, settings, dates, prize/family choices, source code and installed versions identical. Repeat its thread-limit and visible-GPU environment variables as well; the tested local pilot sets OMP_NUM_THREADS, OPENBLAS_NUM_THREADS, MKL_NUM_THREADS and NUMEXPR_NUM_THREADS to 2. GPU runtime, device identities and driver are fingerprinted when CUDA is available. Output and source locations can move; pinned platform/dependency context must still match. Rebooting the same environment is supported; migrating an in-progress fit to different hardware, drivers, OS or package versions is not an acceptance claim. A context mismatch fails rather than silently mixing models.

```bash
$PY number_prediction/train.py --data SNAPSHOT --out RUN --params SETTINGS \
  --family transformer --prize both --train-end 2007-10-15 \
  --calibration-end 2007-11-15 --validation-end 2007-12-31 \
  --checkpoint-every 100 --resume
```

For a new run omit `--resume` and choose a new RUN. `--checkpoint-every` is a positive number of Transformer batches or XGBoost/LightGBM boosting rounds. Smaller intervals reduce lost work but increase disk writes. It defaults to 100 and can change on resume. CatBoost uses its own native snapshot every second, including its internal training state. CPU CatBoost honors STOP at iteration boundaries; its GPU backend does not support callbacks, so STOP may wait until the fit returns. A supervisor can terminate it after a 30-second grace period; recovery then uses the last native snapshot.

Transformer checkpoints include model weights, optimizer, scheduler, AMP scaler, best validation weights, early-stop history/counter, current shuffled order and batch cursor, and Python, NumPy, Torch CPU and CUDA random states. A saved batch resumes after its optimizer step. Work after the last committed checkpoint is replayed. Validation is recomputed if interrupted before its epoch commit. CPU dropout recovery matched exactly; local GPU AMP/dropout recovery passed at atol 1e-6 / rtol 1e-5 for weights/probabilities and 1e-5 for validation losses. PyTorch warned that memory-efficient CUDA attention can be nondeterministic in warning-only mode, so these results do not promise a bitwise-identical GPU trajectory or cross-hardware recovery.

XGBoost and LightGBM continue their native boosting model at recorded round boundaries. Completed base fits and chronological stacking folds are cached separately. The small logistic stacking fit, calibration, feature construction and prediction can be recomputed from committed earlier stages. Native CatBoost snapshots are library-managed; other checkpoint payloads are hashed, flushed, then published through an atomic pointer. Two committed generations are retained per checkpoint stream. Uncommitted crash debris is ignored and preserved for inspection. Damage to the latest committed checkpoint raises an error; it never silently retrains from zero.

Final packages, validation probabilities and the report are committed before a family is considered finished. A crash between result commit and publication reuses the committed result. An existing published artifact with a different hash is refused. Baselines, four learned families and two ensembles share the same run journal. The reserved 2025-01-01–2026-10-21 final test remains outside this training/selection CLI.

The grid handles partial runs automatically: repeat the same `experiments.py` command with `--execute --max-jobs N`. A completed job is skipped only after verifying the report, model packages and validation files. The grid has a separate exclusive lock; every training run also holds its own kernel lock. Lock filenames remain after exit. Never delete them to force a second worker. Process death and reboot release the actual kernel lock.

Optuna's trial count and timeout are fixed total budgets for that study, not additional budgets per restart. Interrupted RUNNING trials consume their slots and become FAIL under the owning run lock. Completed tuning selection is cached. A crashed trial may have no completed candidate to select; inspect the failure rather than increasing the budget silently. The small stack optimizer and individual trial refits can restart; TPE sampling across restarts is not promised to be bitwise identical.

## Stop deliberately

Create RUN/STOP or GRID/STOP, or send SIGINT/SIGTERM. A STOP file remains until the owner explicitly removes it. STOP is separate from the collectors' STOP files. Exit status 75 means intentionally stopped; it is not completion. SIGTERM alone does not create STOP, allowing recovery after normal system shutdown. Check `run-status.json`, `development-report.json`, the process log, and `.recovery/` before resuming. Never delete state to repair a run.

## Bounded restart and reboot setup

`supervise.py` launches a JSON argument array without a shell, appends `--resume` for an initialized single run, and persists a retry budget across restarts. Its state directory has its own STOP and kernel lock. A child STOP or exit 75 prevents automatic retry. Default allowance is the initial attempt plus three retries, 60 seconds apart. Exhaustion exits 78 and requires inspection. A failed GPU/library configuration therefore cannot loop forever.

On the target server create `command.json` containing the exact absolute Python, training script, snapshot, output and settings arguments for the approved run. Use a distinct persistent supervisor state directory. The same wrapper can supervise `experiments.py`; `--max-jobs` still bounds that invocation, so one successful invocation does not silently dispatch the rest of a grid.

```bash
$PY number_prediction/supervise.py --command command.json --state SUPERVISOR \
  --max-retries 3 --retry-seconds 60 --write-unit loto-prediction.service
# Explicit foreground launch, only when that training run is authorized:
$PY number_prediction/supervise.py --command command.json --state SUPERVISOR \
  --max-retries 3 --retry-seconds 60 --execute
```

Generating the unit only writes a reviewable file; it does not install, enable or start anything. It sets a 40-second shutdown timeout, bounded failure restart, and prevents restarts for exit 75/78. Generate it on the server using its real interpreter/paths. After reviewing the approved command, install the user unit under `~/.config/systemd/user/`, reload systemd, and enable it deliberately. A user service normally starts with the user session; pre-login startup needs the administrator's linger configuration. No live service or reboot recovery has been accepted on the local laptop or a server.

## Transfer and backups

Git excludes `datasets/`, `runs/`, `.recovery/` inside runs, model weights, SQLite studies and environments. Cloning source alone does not transfer the modeling snapshot or recoverable run. Transfer the complete immutable snapshot and, for recovery, the entire stopped run/grid directory including hidden `.recovery/`, contexts, studies, result packages and journals. Transfer supervisor state as well if preserving the retry budget. Stop and confirm the worker lock is free before a consistent backup, especially for SQLite/WAL study files. Keep old copies; do not merge competing writers. Create the Python environment anew on the server. Source-only deliverable ZIPs do not contain the archive, snapshot, fitted models or training recovery state.
