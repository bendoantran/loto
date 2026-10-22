# Kubuntu Codex handoff: G.ĐB and G.8 prediction

The owner will clone this private repository on another Kubuntu computer and use a Codex agent there to implement the prediction project. The full agreed specification is [PREDICTION_IMPLEMENTATION_PLAN.md](PREDICTION_IMPLEMENTATION_PLAN.md). This handoff and the plan are documentation only; no prediction model or training pipeline is implemented by their addition.

## Read first

1. [AGENTS.md](AGENTS.md): repository protections and dependency scope.
2. [KUBUNTU_AGENT_HANDOFF.md](KUBUNTU_AGENT_HANDOFF.md): safe migration, restore, baseline verification, existing controls, and known source gaps.
3. [XSMT_KUBUNTU_CHALLENGE.md](XSMT_KUBUNTU_CHALLENGE.md): the separately authorized Central Vietnam collector, source fixtures, graders, isolation, and recovery requirements.
4. [PREDICTION_IMPLEMENTATION_PLAN.md](PREDICTION_IMPLEMENTATION_PLAN.md): canonical ML requirements and the unchanged six stages.

Treat these as complementary documents. The XSMT challenge's A–G steps belong to data preparation in prediction Stage 1; they do not replace the owner's six ML stages. If an agent has already started work, inspect and preserve it rather than generating a competing collector or resetting a checkpoint.

## Three computer roles

| Role | Environment | Responsibility |
|---|---|---|
| Implementation | Owner's other Kubuntu computer; inspect actual version/hardware | Implement, run offline tests, validate integration, and prepare reproducible training/deployment tools |
| Training | Ubuntu 24.04 or 26.04; Threadripper PRO 5995WX, 1 TB RAM, RTX 6000 Ada, RTX 4090 | Full model fitting, tuning, chronological evaluation, and artifact export |
| Daily inference | Windows 11 Pro, i7-1265U, approximately 32 GB RAM, Intel Iris Xe | Read validated results, update features, load saved models, predict, and score completed draws on CPU |

Do not assume the Kubuntu computer has the server's GPUs or the Windows computer's paths. Access to the training server has not been provided by this handoff. Finish independent implementation and tests if server access is unavailable, and report the exact remaining server-dependent work. Do not fabricate benchmark results or claim GPU training occurred on a machine that was not used.

## Clone or reuse the private repository

Use existing authorized GitHub authentication. For a private-repository authentication failure, let the owner complete browser/device authentication following the existing migration guide. Never request or print a token in chat, embed a token in the Git remote, change repository visibility, or enable GitHub Pages.

For a new destination, after checking it does not contain existing work:

```bash
mkdir -p "$HOME/Documents"
git clone --depth 1 https://github.com/bendoantran/loto.git "$HOME/Documents/xoso"
cd "$HOME/Documents/xoso"
git remote -v
git status --short
```

If this is already the intended clone, inspect its status and preserve local work. Update it using the owner's normal Git workflow; do not delete, reset, or overwrite it to match the example commands.

Follow the existing migration guide to restore and verify the immutable XSMN baseline. On a fresh, untouched clone its documented checks are:

```bash
python3 tools/restore_snapshot.py --verify-files
python3 tools/verify_archive.py --baseline
python3 -m unittest discover -p 'test_*.py' -v
bash status-history.sh
```

These are existing archive commands. Run them with a compatible Python 3.10+ interpreter. An existing live checkpoint must be preserved. Migration acceptance requires actual target results, not copying the documented expected counts. Do not restart historical downloads just to migrate; the XSMN baseline is already complete.

## Data roots and provenance

- XSMN: `<repository-root>/years/YYYY/prizes.csv`.
- XSMT full history: `$HOME/Documents/xoso-xsmt/years/YYYY/prizes.csv`, or an explicitly configured existing XSMT root.
- Keep the challenge's pilot and year-boundary scratch roots separate from both full roots.
- Existing raw CSV columns include `quality_flags`; preserve them and all source strings.
- Derive normalized region metadata from verified source/checkpoint manifests without rewriting frozen exports.
- Never assume XSMT has the same earliest available date as XSMN. Use the challenge's independently established boundary and disclose collection gaps.
- Calendar day 1 is always 2007-08-18 for feature indexing, even when a region's observed coverage starts later.
- Both-region training uses explicit, versioned data manifests. Fixtures, regional pages, daily pages, and province pages must not become duplicate examples of the same draw.

The fixed XSMN archive ends on 2026-10-21. The XSMT challenge freezes its independently researched historical run through 2026-10-22. Do not silently extend either saved checkpoint. Configurable future result updates must use a deliberately designed separate/range-safe mechanism and retain as-of provenance; a stale saved cutoff cannot be described as today's latest results.

## Isolated ML implementation

Implement the prediction system inside `number_prediction/`, preserving the archive tools and their standard-library-only operation. Use Python 3.11+ selected for compatibility and a dedicated virtual environment. Check installed interpreters first. Never replace system Python or upgrade Kubuntu automatically to satisfy a package requirement.

The future subproject should contain configuration, dependency specifications, loading/validation/features, model modules, optimization/stacking/calibration, schedules, evaluation, inference, tests, and its own README. Keep the original proposed `train.py`, `backtest.py`, and `predict.py` interfaces within it. These scripts do not exist merely because this handoff names them; write and test them during the corresponding stages before advertising runnable commands.

Keep large model artifacts, trial databases, caches, and generated data outside normal source commits by default. Document artifact transfer from the server to Windows, including versions, preprocessing, mappings, recent feature state, and cutoffs. Record exact tested dependency versions and distinguish CPU development/inference installation from server GPU training installation.

## Required implementation behavior

- Predict G.ĐB by default; allow G.8 or both with separate aligned 00–99 probability distributions.
- Use G.8/G.ĐB historical inputs from both regions, preserving province and prize identities and each province's draw sequence.
- Predict the next scheduled draw and show the five-calendar-day outlook as informational. Use verified regional schedules, not hardcoded daily draws for every province.
- Predict before revealing each historical target; score it; only then admit the outcome to future history. Without reliable publication times, withhold the entire target date across both regions.
- Start with uniform fallback during warm-up. Preserve missing values, zero padding, quality exclusions, and immutable forecast records.
- Implement and compare all requested model families and ensembles, with chronological stacking/tuning/calibration and a final test period never used for selection.
- Report G.8 and G.ĐB performance separately by province, region, and horizon. Compare within-region and combined-region training on matched eligible dates.
- Allow a baseline to be selected when learned models do not convincingly improve performance. Do not promise a predictive edge.
- Treat weekly retraining, monthly bounded tuning, and an initial 12–24-hour search budget as proposed defaults to validate in development, not measured runtimes or a reason to stop with required stages unfinished.

## Keep the six stages unchanged

1. Data loading, validation, feature engineering, and baseline models.
2. CatBoost, XGBoost, and LightGBM.
3. PyTorch causal Transformer.
4. Weighted ensemble and leakage-free stacking.
5. Hyperparameter optimization and probability calibration.
6. Backtesting, inference, automated testing, and documentation.

Apply the plan's temporal contracts and relevant tests at every stage. The full end-to-end backtesting deliverable remains in Stage 6. Collection can continue against its own checkpoints while fixed validated snapshots support independent development.

## Progress and acceptance evidence

During implementation, maintain `number_prediction/IMPLEMENTATION_PROGRESS.md` and focused stage reports under `number_prediction/reports/`. Record completed work, actual commands and outcomes, code/data versions, known gaps, and the next step. Do not overwrite the collector's canonical `PROGRESS.md` or `progress.json` with ML progress.

Before calling a stage complete, run its relevant tests and address failures. Re-run affected existing archive/region tests after collector changes. Use the full archive verifier when making migration or archive-preservation acceptance claims; do not claim it passed just because documentation lists its command.

Distinguish code implemented, tests passed, XSMT pilot accepted, historical collection progress, server training performed, held-out results measured, and Windows inference actually benchmarked. Incomplete server access or future prospective evaluation must remain explicit. Log-loss improvements, top-k accuracy, training times, and memory use require measured evidence.

## Paste this into the Kubuntu Codex agent

```text
Implement the finalized prediction project from my private repository https://github.com/bendoantran/loto on this Kubuntu computer. Read AGENTS.md, KUBUNTU_AGENT_HANDOFF.md, XSMT_KUBUNTU_CHALLENGE.md, PREDICTION_KUBUNTU_HANDOFF.md, and PREDICTION_IMPLEMENTATION_PLAN.md completely, then inspect the actual checkout and any existing work.

This prompt authorizes implementation of the plan. Preserve the original six prediction stages and their order; begin with Stage 1 and proceed through the stages with relevant tests. Keep ML code and third-party dependencies inside an isolated number_prediction/ subproject/environment. Preserve the standard-library-only archive tooling, immutable XSMN baseline, checkpoints, raw responses, leading zeros, quality flags, existing display, and private repository. Restore and verify the bundled archive rather than rescraping it.

Use historical G.8 and G.ĐB inputs from XSMN and XSMT, with region/province/prize identity and separate prize outputs. Implement or reuse XSMT according to its existing challenge in separate roots and pass its graders/recovery checks. Investigate its historical boundary independently; do not treat fixtures as a live collector or invent unavailable records. Calendar day 1 is 2007-08-18 for every region and missing dates retain their positions.

Default to G.ĐB prediction, with G.8 or both selectable, for a specified province's next scheduled draw. Include only actual scheduled draws in the informational five-calendar-day outlook. Generate and record forecasts using past-only information before revealing/scoring target outcomes, then update history. Keep the entire target date withheld across regions unless reliable availability times justify a later validated policy. Preserve an untouched final test period for selection purposes. Implement every model family, ensemble, tuning and calibration method in the plan; accept an honest no-improvement result and a baseline predictor when appropriate.

This Kubuntu development computer is not assumed to be the training server. Heavy training will use Ubuntu 24.04 or 26.04 with Threadripper PRO 5995WX, 1 TB RAM, RTX 6000 Ada and RTX 4090. Daily inference targets Windows 11 Pro, i7-1265U, about 32 GB RAM, and CPU execution. Prepare portable training and deployment artifacts and benchmark on the actual target machines when access exists. Do not invent server access, training results, or Windows acceptance. Continue independent implementation/tests when a target machine is unavailable and report the precise remaining work.

Maintain number_prediction/IMPLEMENTATION_PROGRESS.md and stage reports without replacing collector progress files. Proceed with authorized reversible work without repeatedly asking for confirmation. Respect existing STOP states and fixed collector ranges, preserve user changes, keep credentials out of output and Git, and do not create subagents unless I ask. Report actual tests, data coverage, completed stages, measured results, artifact versions, and any genuine blocker.
```
