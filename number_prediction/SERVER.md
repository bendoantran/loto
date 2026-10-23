# Offline server transfer (no sudo)

This bundle contains the current prediction source, the immutable completed XSMN/XSMT modeling snapshot (75,424 eligible targets), Python 3.12, and pinned binary wheels. It does not contain the raw collector HTML/SQLite archives, previous training runs, credentials, or a live service. Keep the original archives backed up separately. No rescraping is needed for training. The snapshot retains its copied source exports, eligibility decisions, region/province/prize identities, leading zeros and original quality states.

Supported bundle target: Linux x86_64 with glibc (Ubuntu 24.04/26.04 is the intended server family), a writable executable persistent directory, and at least 20 GiB free for copying/extracting/installing plus space for training outputs and backups. No root, system Python, internet, CUDA toolkit, compiler, systemd or package-manager access is needed by setup. The exact server must still pass the checks below. An ARM server, Alpine/musl system, incompatible native libraries, a `noexec` mount, read-only storage or blocked GPU devices needs a different location/build or administrator help.

Copy the `.tar.gz` and its `.sha256` file together. Run these commands from their directory, then keep the extracted folder at its final path:

```bash
sha256sum -c loto-server-offline-linux-x86_64.tar.gz.sha256
tar -xzf loto-server-offline-linux-x86_64.tar.gz
cd loto-server-offline-linux-x86_64
bash setup.sh
./loto doctor --device cuda
./loto pilot --device cuda
```

`setup.sh` checks every bundled file, creates a local `.venv`, installs only the included wheels with SHA-256 verification, and runs `pip check`. It never starts training. It is safe to run again after a completed setup. If interrupted during setup, rename the incomplete `.venv` to retain evidence and rerun setup. Do not copy an existing virtual environment from the laptop. After setup, do not move the folder: virtual-environment entry points and prepared commands use absolute paths. To relocate, copy the immutable bundle into its final location and run setup there again; preserve existing run directories separately.

Both launch scripts force UTF-8 for their Python processes, so a server's legacy `C` locale does not break Vietnamese names or paths. This does not require changing the system locale.

The GPU doctor allocates CUDA memory and executes a small matrix multiplication, checks XGBoost's CUDA build, independently enumerates the OpenCL GPU used by LightGBM, imports all dependencies, verifies snapshot records, and tests atomic writes/fsync and cross-process filesystem locking. It does not fit a model. The bundle includes a user-space OpenCL loader and NVIDIA ICD entry. The **server must already supply a working NVIDIA kernel driver, its OpenCL library, and access to the allocated GPU devices**. A Python package cannot install those without administrator support. Keep the server's `CUDA_VISIBLE_DEVICES` allocation unchanged. All CUDA families select logical device zero. LightGBM's OpenCL indices are matched to that CUDA device by UUID and saved in the plan; this prevents accidentally using a different GPU on a shared server. If automatic matching is unavailable, set both `LOTO_OPENCL_PLATFORM` and `LOTO_OPENCL_DEVICE` to the reported allocated device indices before doctor/preparation/launch. A known UUID mismatch is refused. If CUDA/OpenCL is unavailable, request the driver/allocation fix or explicitly use `--device cpu` for both doctor and pilot. There is no silent CPU fallback for a CUDA request.

The pilot fits only the 2007 development subset, both regions and prizes, all four learned families, both ensembles and five baselines. It uses eight tree rounds, one Transformer epoch, sequence length eight, two threads, no hyperparameter search, and no final-test scoring. Each invocation uses a new destination. A pass demonstrates integration, not a predictive advantage or full-size memory/speed acceptance. The reserved final test remains 2025-01-01 through 2026-10-21.

## Prepare and run a longer development job

Only do this when ready to authorize the longer training on the server. Preparing writes reviewable commands/settings; it does not fit anything:

```bash
./loto prepare --name development-001 --profile development --device cuda
cat number_prediction/runs/development-001.launch/command.json
cat number_prediction/runs/development-001.launch/params.json
./loto start development-001
./loto status development-001
tail -f number_prediction/runs/development-001.launch/process.log
```

The development profile uses `train.py`'s existing training/calibration/validation boundaries ending in 2024 and its reference/default model settings. It is one comparison run, not the full experiment grid. The launcher does not estimate full-run resource requirements. Review settings before starting; select CPU explicitly if required. For a foreground command use `./loto start development-001 --foreground`. This does not use multiple GPUs or automatically scale to all server CPUs; conservative settings avoid oversubscribing shared resources. Use the server scheduler instead of detached mode when required by server policy; `./loto python number_prediction/supervise.py --help` describes the supervisor entry point.

## Stop, disconnect, crash and resume

```bash
./loto stop development-001
./loto status development-001
# Wait for worker_running and supervisor_running to become false, inspect the log.
./loto resume development-001
```

Detached mode starts a separate session, logs to disk and takes no terminal input, so an ordinary SSH disconnection does not end the process. It cannot override a cluster policy that kills all user jobs at logout. Check with the server owner whether detached jobs are allowed; use its scheduler if necessary. No service is installed or enabled by these commands.

STOP is durable and stops automatic retries. XGBoost/LightGBM save at round boundaries; Transformer saves batches including optimizer/scheduler/AMP/RNG state. CatBoost GPU uses its native timed snapshot because GPU callbacks are unsupported; an intentional STOP can take until the current CatBoost fit returns. Hard interruptions may lose work since the last committed snapshot. An explicit `resume` clears this launch's STOP requests and grants a new bounded supervisor allowance, while keeping previous journals and checkpoints. Each supervisor allows the initial attempt plus at most three retries, 60 seconds apart. Inspect failures instead of repeatedly granting retries to a bad environment. A finished, intact run verifies and returns without fitting again.

CatBoost snapshot loading runs in an isolated child with its own kernel lock. Before loading, it preserves a checksummed snapshot copy under `resume-evidence`. Native load-failure warnings stop that child and create `invalid-snapshot.json`, which blocks silent retraining and later automatic retries from resetting progress. Preserve these files and inspect the failure; choose a new run only deliberately. A resumed CatBoost fit temporarily writes its numeric input matrix beside the checkpoint, so allow additional scratch space proportional to that matrix. A surviving child after parent death retains its native-worker lock; wait for it to finish or stop it deliberately before retrying.

After a power failure or server reboot, rerun `./loto resume NAME` in the same folder and environment. Automatic startup before login depends on the server scheduler or an administrator's systemd user-linger policy; the no-sudo bundle does not promise automatic reboot launch. Use `RECOVERY.md` for optional user-service generation. File locks release when a process dies; never delete a lock file. The launcher refuses a second live supervisor or training writer. A live writer may survive its supervisor's crash: stop and wait for that writer before relaunching.

Recovery requires the same source, data, parameters, environment and device fingerprint. Driver/package changes or switching GPUs can deliberately reject a pending run. Native completed model packages remain separately usable for CPU inference; restart a new run when the safe-recovery context differs. CUDA repeatability is tested to tolerances; cross-hardware bitwise identity is not promised.

Back up the **entire stopped** `runs/NAME` and `runs/NAME.launch` directories, including hidden `.recovery`, Optuna SQLite/WAL state and supervisor journals, to separate persistent storage. Wait for both locks to be free first. Code and checksums cannot recover a failed disk containing the only copy. Do not place long-run recovery state on temporary/job-local scratch that the server deletes at reboot.

## Extra explicit verification

```bash
./loto python verify_bundle.py
./loto python -m unittest discover -s number_prediction/tests -v
# Actual CUDA recovery tests, only after the GPU doctor passes:
LOTO_GPU_TESTS=1 ./loto python -m unittest discover -s number_prediction/tests -p test_gpu.py -v
```

These regression tests include tiny model fits and deliberately killed test subprocesses. They use temporary destinations and do not train the full dataset. Local acceptance does not substitute for running doctor/pilot on the real server. Windows inference needs separate Windows acceptance; this Linux bundle does not install Windows dependencies.
