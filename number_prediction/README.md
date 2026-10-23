# Past-only G.ĐB / G.8 probability experiments

This isolated subproject implements the six stages in `../PREDICTION_IMPLEMENTATION_PLAN.md`. The existing archive tools remain standard-library-only. Read `IMPLEMENTATION_PROGRESS.md` and `reports/` for measured results and remaining acceptance work. A working pilot is not a completed server experiment or a demonstrated prediction advantage. The post-XSMT full-archive audit and bounded integration results are recorded in [reports/post-xsmt-completion.md](reports/post-xsmt-completion.md).

## Data handling

The primary inputs are each canonical region root's `years/YYYY/prizes.csv`, checked against its corresponding `results.jsonl`, source URLs, checkpoint region/range, and original decompressed HTML hashes. `snapshot.py` reads the active collector without modifying it. It retries changing/inconsistent CSV/JSON pairs and refuses a capture that cannot be verified. It copies stable yearly exports into a new snapshot directory, writes accepted target rows and every inclusion/exclusion decision, and hashes the manifest and data. It does not merge, reset, stop or repair collector databases. An incomplete XSMT export is disclosed as incomplete; capture it again into a new directory when more history becomes available.

Source numbers and endings remain strings, including `00`, `09` and `044743`. Modeling classes alone are integers 0–99. G.8 requires two source digits; G.ĐB accepts historical number widths when the ending is valid. Target-specific or unexplained quality flags exclude the target; a documented anomaly in another prize does not automatically exclude it. Review/no-draw/unavailable dates are not invented as labels. Source flags and raw values remain available in `eligibility.jsonl` and copied exports.

The normalized key is region/province/date/prize. Identical duplicates count once; conflicting duplicates fail. Every province/date observation contains separate G.8 and G.ĐB masks. Historical identities `TPHCM` and `TP.HCM` remain separate pending a verified alias mapping. Region is verified from the configured root/checkpoint and daily source URL. Pilot/fixture/rolling-page directories are never combined with the full canonical root.

Calendar day 1 is 2007-08-18. Gaps retain calendar positions. Province draw order and elapsed province draws are separate features. Features include categorical lags, province/region identity, smoothed rolling windows, entropy, time since appearance, and separately identified regional history. Mean numeric label identity is not used as similarity.

All inputs have dates strictly before forecast `origin` across both regions. Horizon 1 means the origin date before its draw; horizon 5 means origin + 4 calendar days. Later horizons are trained directly with exactly that earlier information boundary. No intermediate actual future outcomes or target-day G.8 enter G.ĐB inputs. `FeatureBuilder` may hold a complete snapshot but only exposes the strict prefix for each query. Training, early stopping, chronological OOF stacking, tuning and calibration have their own past-only boundaries.

`config.json` reserves 2025-01-01–2026-10-21 before development. Default training ends 2021-12-31, calibration ends 2023-06-30, and comparison ends 2024-12-31. All rows from a date stay together. Final scoring requires a matching immutable selection policy. The predefined final policy freezes model weights and updates only earlier eligible feature history. `cadence.py` supports separate daily/weekly/monthly refit comparisons entirely within development, rebuilding compatible calibration from later past data at every refit. Full-scale cadence selection remains server experiment work.

## Installation

For a server without sudo or package-download access, use the self-contained offline bundle described in [SERVER.md](SERVER.md). It includes a separate Python runtime, pinned binary wheels and the frozen completed modeling snapshot. `setup.sh` installs only into the extracted directory, and `loto` provides explicit doctor/pilot/prepare/start/status/stop/resume commands. A Git clone alone still excludes data, environments and recoverable runs.

The local tested interpreter is Python 3.12.9 on Ubuntu 26.04.1. Use Python 3.12 for these pins; do not replace system Python. Run from the repository root:

```bash
python3.12 -m venv number_prediction/.venv
number_prediction/.venv/bin/python -m pip install -r number_prediction/requirements-cpu-linux.txt
number_prediction/.venv/bin/python -m pip install torch==2.6.0 --index-url https://download.pytorch.org/whl/cpu
number_prediction/.venv/bin/python -m unittest discover -s number_prediction/tests -v
```

`requirements-tested-linux.txt` captures the complete actual development environment. Direct dependency pins are in `requirements.txt`. Windows uses `requirements-cpu-windows.txt` and the same CPU Torch index, from a separate Windows virtual environment. CPU XGBoost is a separate Linux distribution; do not install it alongside the server/full XGBoost distribution.

For the training server, first inspect OS, Python, NVIDIA driver, CUDA compatibility, disk, GPU identities and available memory. In a separate environment install `requirements-server.txt` and `torch==2.6.0` using the official CUDA 12.4 wheel index if the verified driver supports it. CatBoost, XGBoost, LightGBM and Torch have different GPU build requirements. Unsupported CUDA is reported; select CPU explicitly when necessary. Use separate jobs on the two GPUs first, with bounded CPU threads and no concurrent trials by default. The local CPU pilot provides no server GPU acceptance evidence.

## Snapshot and train

Update the two root paths in a copy of `config.json` for another computer. They are resolved relative to that configuration file. Both roots must be independently established canonical archives. The default local paths match this checkout's existing roots.

```bash
PY=number_prediction/.venv/bin/python
$PY number_prediction/snapshot.py --out number_prediction/datasets/run-001
$PY number_prediction/train.py --data number_prediction/datasets/run-001 --out number_prediction/runs/development-001 --family all --prize both
```

Every output directory must be new. Snapshot and package loaders verify hashes. Never edit an existing snapshot to add results. A failed capture retains a `FAILED` marker; inspect the error and choose a new destination. CSV/Excel adapters support explicit column mappings; Excel number/loto cells must be text because numeric cells may already have lost zeros. The canonical training CLI deliberately reads verified snapshots, not unverified arbitrary spreadsheets. Use `data.read_external` and `validate_row` in an explicit audited import rather than silently treating external rows as validated archive data.

`--family` supports uniform, frequency, smoothed, province, markov, catboost, xgboost, lightgbm, transformer, average, stack, and all. `--prize` supports G.ĐB, G.8, or both. Independent requested prizes have independent distributions. The Transformer implementation also supports two masked target heads through its direct API; the CLI trains prize-specific models to support paired comparisons.

`--training-region both|xsmn|xsmt`, `--input-prizes both|G.8|G.ĐB`, and optional `--province` define matched regional/input/province comparisons. `--horizons 1,2,3,4,5` constructs direct horizon examples. Unknown/unsupported identities fail rather than being merged. Models needing history use uniform/smoothed baselines during warm-up; the operational baseline backtester starts on day 1.

The reference Transformer is 256 dimensions, 8 heads, 6 layers, dropout .1, sequence length 128, and 100 classes. `pilot.json` is an explicitly smaller integration configuration. Fixed settings can be supplied through `--params`. `--tune-trials N --tune-seconds S` runs bounded Optuna search using inner expanding-window folds and a later outer selection segment. Study state, seeds, parameters, pruning and budgets are persisted. In stacking, base-model parameters are fixed separately from stack parameters; each OOF fit has its own earlier early-stop segment. Stack inputs never use in-sample base predictions. TPE resume preserves trials but does not promise bitwise-identical sampling across restarts/hardware.

Tree packages use native persistence and explicit observed-class mappings, with documented default .01 uniform mixing. No labeled examples are fabricated for absent classes. The Transformer uses masked missing targets, causal attention, start/padding/missing tokens, early stopping, clipped gradients, learning-rate scheduling, native weights and optional CUDA mixed precision. Logistic stack coefficients persist as JSON. Calibration temperature is fitted after the frozen predictor's training segment, tested in a subsequent segment, and retained only when that development comparison improves log loss. Refit models need new compatible calibration; old calibration is not automatically reused.

Prepare a serial server grid without running it:

```bash
$PY number_prediction/experiments.py --data number_prediction/datasets/run-001 --out number_prediction/runs/server-grid
# Explicit bounded execution, resumable by completed job markers:
$PY number_prediction/experiments.py --data number_prediction/datasets/run-001 --out number_prediction/runs/server-grid --execute --max-jobs 1
```

The grid covers three training-region choices and three history-input choices, both prizes, all 11 predictors, and horizons 1–5. Add explicit `--province` comparisons if sample support allows. The grid automatically resumes a partial job under a process lock and verifies completed artifacts before skipping a job. A changed snapshot, source, environment or configuration requires a new destination. Collection can continue while this grid uses its fixed snapshot. Actual XSMT coverage may be insufficient in later development/test periods; absent coverage cannot establish regional performance. See [RECOVERY.md](RECOVERY.md) for interrupted fits, durable stops, bounded restart supervision and reboot setup.

For bounded development comparisons of weight-refit policy, run `cadence.py --data DATA_SNAPSHOT --start DEVELOPMENT_START --end DEVELOPMENT_END --family catboost --out NEW_CADENCE_REPORT.json`. It reports daily/weekly/monthly refits, cost and accuracy on the same eligible targets. Its default 30-day past calibration window is fixed for all policies; fit and calibration outcomes both precede each forecast origin. Feature history updates are independent of the weight-refit cadence. Small-history origins use uniform warm-up. Predeclare parameters and compare policies over adequate development periods before changing the final evaluation contract.

## Comparison, final evaluation and forecasts

Every development run retains matching queries, labels and full probabilities. `compare.py` compares the same family across two runs on identical eligible draws, including within-/combined-region comparisons, date-block intervals, and region/province-balanced scores. Predeclare the comparison count for Bonferroni-adjusted uncertainty; do not choose it after observing results.

```bash
$PY number_prediction/compare.py --reference RUN_XSMN --candidate RUN_BOTH --family transformer --prize-index 1 --comparison-count 11 --out comparison.json
$PY number_prediction/select_model.py --run RUN_BOTH --data DATA_SNAPSHOT --prize-index 1 --minimum-gain .001 --out frozen-policy.json
$PY number_prediction/backtest.py --data DATA_SNAPSHOT --model SELECTED_PACKAGE --prize 'G.ĐB' --start 2025-01-01 --end 2026-10-21 --final-policy frozen-policy.json --out NEW_FINAL_RUN
```

Selection begins with uniform, requires practical and date-block evidence for a more complex baseline or learned predictor, and records all candidates. Complete the required development comparisons and hardware cost checks before treating a selected candidate as a deployment acceptance. The final test is never passed to the selection/tuning CLI. An honest baseline/no-advantage finding is a valid result.

Historical backtests commit forecasts for the target date before revealing/scoring its labels. They are labeled simulated historical evidence. Log loss uses natural logarithms and a common scoring clip of 1e-15; Brier sums over the 100 classes then averages over draws. Ties favor the smaller class. Outputs include top-1/3/5/10, calibration bins, province/region/prize/horizon/year groups, coverage, balanced summaries and paired block uncertainty. A single short development fluctuation does not establish an edge.

```bash
$PY number_prediction/predict.py --model SELECTED_PACKAGE --data NEW_VALIDATED_SNAPSHOT --province 'Huế' --region xsmt --prize 'G.ĐB' --scope five-day --ledger PRIVATE_LEDGER.sqlite3 --out NEW_FORECAST_FOLDER
```

Supply one `--model` per prize when requesting both. Forecasts include all 100 probabilities, ranks, source/model versions, cutoff, day index, horizon and latest input date. `--top-k` accepts 1–100. The append-only ledger refuses replacement forecasts and keeps separate outcome revisions without changing original predictions. Prospective forecasts use the actual timezone-aware timestamp and must precede draw start.

`schedules.json` records the two source pages checked on 2026-10-22, Asia/Ho_Chi_Minh draw starts, and a deliberately restricted current-week validity interval. It makes no historical schedule claim. Refresh and version the evidence when dates fall outside its interval. The five-day outlook contains scheduled dates only. A learned horizon absent from the trained package is explicitly unavailable; later actual outcomes never fill intermediate unknowns. The saved latest-history date is disclosed; automatic result fetching is not enabled.

## Portable deployment and limits

```bash
$PY number_prediction/package.py --model SELECTED_PACKAGE --out private-model.zip
$PY number_prediction/benchmark.py --model SELECTED_PACKAGE --queries probes.json --out linux-reference.json
# Run the same model/probes on Windows, using its environment:
python number_prediction/benchmark.py --model SELECTED_PACKAGE --queries probes.json --reference linux-reference.json --out windows-benchmark.json
```

The ZIP contains Python inference sources, schedule/configuration, dependencies, native weights, mappings, calibration/ensemble settings, necessary history and file hashes. Keep it private. The server need not stay online for CPU predictions. Load candidates and run identical probes before replacing a working model; preserve the old deployment on failure. Default cross-machine tolerance is atol 1e-6, rtol 1e-5. Benchmarks measure actual load/inference time and whole-process peak memory; results describe the machine that ran them. GPU/CPU and Windows agreement must be measured, never inferred from Linux save/load tests. Large datasets, ZIPs, model weights, caches, ledgers and studies are ignored by Git.

Full server optimization, retraining-cadence comparisons, final model selection/testing, Windows measurements and future prospective scoring remain distinct acceptance tasks. No remote server or Windows session was provided in this implementation chat. See the stage reports for exact evidence.
