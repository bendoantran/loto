# Final Plan: Province-Specific G.ĐB and G.8 Prediction

Planning status: finalized specification for future implementation. Writing this plan does not authorize coding, training, scraper changes, or deployment. The original six implementation stages and their order are preserved.

This is the canonical prediction specification for the private repository https://github.com/bendoantran/loto. The owner will use another Codex agent on Kubuntu to implement it. Start with [PREDICTION_KUBUNTU_HANDOFF.md](PREDICTION_KUBUNTU_HANDOFF.md), [AGENTS.md](AGENTS.md), and the existing archive/XSMT handoffs. This documentation commit contains no prediction implementation or trained model. When the owner supplies the implementation prompt in the handoff, proceed through the six stages under that authorization.

Use Linux paths resolved on the target machine. Windows paths in the original discussion identify the source and daily-use computer, not the Kubuntu working directory. Preserve existing collection roots, fixed ranges, snapshots, schemas, and progress displays.

## 1. Objective and scope

Build a Python system that learns from historical G.8 and G.ĐB results across provinces in Southern Vietnam (XSMN) and Central Vietnam (XSMT), and returns ranked probabilities for a specified province's next scheduled draw.

- Default target: the last two digits of G.ĐB.
- Optional target: the two-digit G.8 result.
- Allow requests for G.ĐB, G.8, or both.
- Return a separate 100-class distribution for each requested prize, with classes ordered 00 through 99.
- Main forecast: the next scheduled draw for the requested province.
- Informational forecast: that province's scheduled draws within the next five calendar days. Do not manufacture a draw on a date when the province is not scheduled to draw.
- Initial training input scope: G.8 and G.ĐB history. Other prize tiers require a later explicit scope change.
- Include both XSMN and XSMT as collection and training sources. Preserve region identity and evaluate whether combining regions improves predictions.
- Evaluate whether prediction improves on simple baselines. A finding of no convincing improvement is a valid project result.

All originally requested model families will be implemented and compared. Daily deployment may select a single model, ensemble, or baseline according to predefined validation criteria and measured local resource requirements.

## 2. Data source, target mapping, and calendar index

Existing Southern Vietnam historical source: `<repository-root>/years/YYYY/prizes.csv`, across the available collected years. For the recommended Kubuntu clone this is `$HOME/Documents/xoso/years/YYYY/prizes.csv`. The separate `data/prizes.csv` snapshot is not the main historical dataset. The original Windows source was `C:\Users\bendo\Documents\xoso`; do not require that path on Linux.

The repository's migration baseline is a completed XSMN archive, described in [KUBUNTU_AGENT_HANDOFF.md](KUBUNTU_AGENT_HANDOFF.md): 2007-08-18 through 2026-10-21, 7,005 checked dates, 21,592 province/date draws, and 388,656 winning-number appearances across all tiers. These are archive totals, not counts of usable G.8/G.ĐB targets. Restore and verify the bundled snapshot using the existing tools; do not rescrape or silently extend the fixed baseline. Preserve its original treatment of review dates and quality states. Any alternative treatment for modeling must be an explicit, separately recorded eligibility policy rather than a change to the source archive.

Additional required collection source: Central Vietnam results at https://xosodaiphat.com/xsmt-xo-so-mien-trung.html. Collect and validate its G.8 and G.ĐB outcomes through available date-specific and province-specific archives. The 30-day results page at https://xosodaiphat.com/xsmt-30-ngay.html is an additional discovery and coverage-check route, not evidence of complete historical availability.

During implementation, add or reuse a separately checkpointed XSMT collection stream according to [XSMT_KUBUNTU_CHALLENGE.md](XSMT_KUBUNTU_CHALLENGE.md). Preserve existing XSMN files and collection progress. The challenge's separate full root is `$HOME/Documents/xoso-xsmt`, with exports at `$HOME/Documents/xoso-xsmt/years/YYYY/prizes.csv`; its pilot and boundary-test roots are also separate. Make these locations configurable and inspect any existing implementation/checkpoint before changing it. Load both sources through explicit manifests, avoiding accidental duplicate imports of snapshots or overlapping exports. Collecting other tiers for source validation is permitted; the initial model inputs and targets remain G.8 and G.ĐB.

The challenge's collection steps A–G are acceptance steps within Stage 1's XSMT/data work, not replacements for the six prediction stages. Respect its fixed test ranges, independently researched full-history boundary, region guards, and separate services. Frozen fixtures and graders are not proof of live collection. Validate existing XSMN data and prepare model-ready snapshots while XSMT collection progresses; report actual coverage rather than treating uncollected history as complete.

Request XSMT history from the same calendar origin where the source supports it, but audit its actual earliest available date, gaps, and quality independently. Coverage back to 2007-08-18 has not been confirmed. Mark unavailable history explicitly, retain the shared day index, and never manufacture records to align regions. Preserve raw source evidence and source-specific parsing/validation results.

Use the historical CSV fields documented by the repository: date, weekday, province, prize, position, number, loto, quality_flags, and source_url. The original seven-day snapshot may lack quality_flags; configure that difference explicitly. Inspect actual exports before implementation and reject incompatible schemas rather than inventing source fields. Preserve raw quality flags and derive a documented model-eligibility decision from them.

Add a normalized region field to processed data, using XSMN or XSMT. Existing raw CSV files do not need to be rewritten: derive region from the verified collection-source manifest or an explicit trusted mapping. Do not guess region from an unknown province name. Record source provenance alongside the region.

- Read number and loto as text to preserve leading zeros.
- Normalize known whitespace variations in prize names to G.ĐB and G.8 while preserving raw source values for traceability.
- Filter target rows by prize identity. G.ĐB uses its loto value, validated against the last two digits of number. G.8 uses its two-digit result, likewise checked against loto.
- Convert valid endings to integer classes 0–99 internally; display and export them as two-character strings.
- Use region, province, draw date, prize, and position as the normalized row key. Require at most one accepted target outcome per region/province/date/prize. Identical draws appearing on regional, province, and rolling-results pages are duplicate observations, not additional examples.
- Build one region/province/date example with distinct prize-specific outcomes and availability masks. Do not count two prize outcomes as two independent G.ĐB examples.

The calendar index is fixed:

| Date | Day index |
|---|---:|
| 2007-08-18 | 1 |
| 2007-08-19 | 2 |
| 2007-08-20 | 3 |

The index equals elapsed calendar days since 2007-08-18, plus one. All provinces and prizes on a date share its index. Missing dates retain their place. Future dates have a known index. Keep this distinct from the count of a province's observed draws.

Validate coverage by region, province, date, and prize; duplicated and conflicting records; missing or invalid endings; weekday consistency; source quality flags; and province-name aliases. Validate each region's source layout independently rather than assuming identical HTML or historical formats. Do not merge historical draw-station identities without a verified mapping. Preserve legitimate changes in G.ĐB number width when the ending is valid.

Missing values are not 00. Never invent outcomes. An issue in another prize does not automatically invalidate a verified G.ĐB or G.8 result. Record explicit inclusion, exclusion, and unresolved-quality reasons.

Each experiment uses a fixed data manifest containing file hashes, included date ranges and row counts by region, quality policy, region/province mapping, source provenance, and data cutoff. Collection can continue independently without changing an experiment's inputs.

## 3. Timing, information availability, and predict-before-reveal behavior

Use Vietnam time, Asia/Ho_Chi_Minh, for draw dates and schedules. Record prediction timestamps in an unambiguous timezone format.

Use the latest validated, completed results actually available at the prediction cutoff. Predict before the target draw begins; do not use its G.8 result to predict its G.ĐB result in the initial design.

Historical CSV dates alone do not establish intraday publication order. Until reliable timing is available, historical evaluation uses results dated strictly before the target date and predicts every province/prize for that date before revealing any outcomes from that date. A historical fetch timestamp does not establish when an old result originally became available.

Apply the date boundary across both regions together. A region's earlier scheduled start time does not establish that its results were completed and available before another region's draw. Same-day cross-region inputs remain excluded unless a later explicitly validated timing policy is introduced.

At every historical prediction origin:

1. Construct inputs using only eligible earlier results.
2. Generate probabilities using models trained only on eligible earlier information.
3. Record the forecast, cutoff, model version, and feature/data version.
4. Reveal the actual target results and score the recorded predictions.
5. Add the completed results to usable history.
6. Retrain only when the predefined retraining policy calls for it.

This is a simulated historical process. Live forecasts must actually be saved before outcomes arrive, retained without replacement, and scored once validated results become available. Corrected source outcomes receive revisions with an audit trail; original forecasts remain unchanged.

Begin the historical record at day 1 with a uniform baseline. Models needing more history remain in warm-up. Document when each model becomes eligible; do not create fake history. Report both common-date model comparisons and full operational performance including any fallback predictions.

Generating these predictions and scores does not constitute permission to tune against the final test period.

## 4. Shared training and feature design

Train shared models across both regions while preserving region identity, province identity, prize identity, and each province's draw sequence. Sharing examples is distinct from concatenating all provinces or regions into one arbitrary outcome sequence.

Candidate features include:

- Region, province, requested prize, calendar-day index, and justified calendar attributes known in advance.
- Separate G.8 and G.ĐB lag sequences for each province.
- Historical windows of 5, 10, 20, 50, and 100 province draws, where available.
- Smoothed rolling class and digit frequencies, occurrence counts, entropy, and transitions.
- Time since a number appeared, separately expressed as elapsed calendar days and elapsed province draws.
- Clearly identified within-region and cross-region historical aggregates available before the cutoff.
- Missing-history indicators and history lengths.

Treat number identities categorically. Means and standard deviations of numeric labels are optional experiments rather than assumed measures of similarity. Fit learned transformations and feature selection using training periods only.

G.8 does not need to cause G.ĐB to be tested as useful historical information. Any common pattern is a hypothesis to measure.

Within the existing stages, compare G.ĐB-only history, G.8-only history, and their combination; pooled models with province identity and province-only models where data supports them; and separate prize predictors versus shared representations with separate output heads. Keep target-date outcomes out of every input variant.

Also compare XSMN-only training, XSMT-only training, and combined-region training on the same eligible target-region/province dates. Use region identity as a candidate categorical feature or embedding. More records do not establish beneficial transfer; select combined or region-specific predictors using development data and retain regional coverage counts.

## 5. Required model families and probabilities

Implement uniform, historical frequency, smoothed frequency, and smoothed Markov baselines. Include a smoothed province-specific baseline with documented backoff through region, pooled, or uniform probabilities as selected in development. An optional digit-frequency baseline may also be evaluated.

Implement all four original learned model families:

- PyTorch causal Transformer, using categorical embeddings, positional information, region/province identity, and separate prize outputs where applicable. Preserve the original reference configuration: d_model 256, 8 heads, 6 layers, dropout 0.1, sequence length 128, and 100 classes. Make it configurable and compare appropriately sized variants. Use cross-entropy, early stopping, gradient clipping, learning-rate scheduling, checkpoints, and supported GPU/mixed-precision execution.
- CatBoost multiclass classifier.
- XGBoost multiclass probability classifier.
- LightGBM multiclass classifier.

Every implemented predictor exposes probabilities shaped (number of requested examples, 100), with stable class alignment. If two prizes are requested, each receives its own distribution summing to one.

Handle absent classes explicitly during fitting and probability alignment. Do not invent labeled examples to make a library fit. Use documented prior smoothing or uniform mixing, selected within development data, to avoid unsupported zero probabilities. Validate numerical finiteness, nonnegativity, and normalization. Any scoring-only numerical clipping is documented and consistent across methods.

Use native model persistence where appropriate, PyTorch weights and architecture metadata for the Transformer, and Joblib only for compatible preprocessing or scikit-learn components.

## 6. Ensemble, optimization, calibration, and evaluation rules

Implement both originally requested ensemble approaches:

- Weighted probability averaging across the four learned model families, with nonnegative weights summing to one.
- A regularized multinomial logistic-regression stack using the 400 aligned base-model probabilities for each prize task.

Allow development-selected shrinkage toward uniform probabilities. Keep the uniform baseline as a candidate final predictor.

Generate stacking inputs with explicit chronological expanding-window predictions. Initial training-only rows are not stacking examples. Do not use ordinary random/stratified stacking defaults or in-sample predictions. Every base-model fit, early-stopping choice, learned preprocessing step, and hyperparameter choice must respect the relevant fold's time boundary.

Use Optuna for model parameters, sequence length, ensemble weights, and stacking regularization. Record seeds, trial budgets, pruning decisions, and study state. Tune in inner chronological development splits; estimate selection performance in later chronological splits. Never use final test results to select features, weights, calibration, hyperparameters, or retraining cadence.

Fit calibration on a chronological segment later than the data used to fit the frozen predictor. Evaluate whether it helps on a subsequent development segment. Document any refitting procedure so calibration and ensemble inputs remain compatible with the final base models.

Reserve a final contiguous chronological test period before model development. Choose exact dates after auditing historical coverage and expected precision, and record them in configuration. Keep all provinces from a date on the same side of every split.

Predefine whether final evaluation uses frozen models or scheduled walk-forward refits. Under walk-forward evaluation, earlier test outcomes may enter later training only after they would have become available and under a policy selected entirely before the test. They cannot be used for discretionary redesign. Also retain prospective evaluation after development decisions are frozen.

Primary metric: multiclass log loss using natural logarithms. Secondary metrics: top-1, top-3, top-5, top-10 accuracy; multiclass Brier score; calibration diagnostics; performance over time; and deployment cost.

Report separately by region, prize, province, forecast horizon, and model, with draw counts and pooled results. State whether pooled metrics weight each draw equally; add region- and province-balanced summaries so differences in draw frequency or collection coverage do not hide weak performance elsewhere. Explicitly report whether adding XSMT improves, leaves unchanged, or harms XSMN performance, and vice versa, with the available uncertainty.

Uniform references for 100 classes are expected top-k accuracy k/100, log loss ln(100) approximately 4.60517, and Brier score 0.99 when squared errors are summed across classes and averaged across examples. Document Brier normalization and a reproducible tie-breaking policy.

Compare methods using paired predictions on identical eligible draws. Estimate uncertainty with date-grouped, temporally aware resampling where appropriate. Account for the many configurations examined, distinguish statistical from practical gains, and avoid claims stronger than sample size supports.

If no learned method convincingly improves on the strongest relevant baselines, report that finding. Deploy an appropriate baseline when it is the best validated choice. Model development remains complete even if no predictive advantage is found.

## 7. Forecast behavior and daily operation

Use verified, versioned region/province schedules to identify the next draw. Record schedule sources, regional draw-start information, and effective dates. The XSMT results page is an initial source for its current schedule, subject to verification. Reject or clearly explain unknown provinces, unsupported prizes, and unverified schedule dates. Do not infer historical schedules solely from today's schedule or use a scheduled start time as proof that a draw has completed.

The five-day outlook covers scheduled draws within five calendar days of the prediction date, using currently available history. Unknown intermediate outcomes are not replaced by actual future results or treated as certain model guesses. For later scheduled draws, evaluate direct horizon-conditioned predictions using training examples constructed with the same information restrictions. Any alternative that propagates possible intermediate outcomes must account for their uncertainty and be validated separately. If a horizon lacks adequate training or schedule support, mark that estimate unavailable. Label the outlook as informational and refresh it after new completed results arrive.

Support the original proposed train, backtest, and predict command-line interfaces. Add configurable region, province, target prize, forecast scope, model version, and cutoff selections. Region may be resolved from a verified unique province identity; ambiguous identities require explicit selection. Default top-k remains 10; accept 1 through 100. No commands exist until implementation is authorized.

Display and export full probabilities plus ranked results to CSV and JSON, including region, province, target prize, draw date, horizon, day index, model training cutoff, latest input date, forecast timestamp, model version, and baseline/no-advantage status where applicable. Do not present several possible dates for one prize as a single probability distribution.

Initially read saved, validated results. Automatic result fetching is configurable future implementation behavior and must pass the same checks. Continue preserving historical collection and raw evidence. Changes to the existing scraper are outside the authorization to write this plan.

## 8. Training server and Windows deployment

Development and implementation take place on the owner's Kubuntu computer using another Codex agent. Inspect that machine's actual OS, Python, storage, and hardware; it need not be the training server or the Windows daily-use computer. Keep dependencies and artifacts portable among these three roles.

Training server supplied by the user: AMD Ryzen Threadripper PRO 5995WX, 1 TB RAM, NVIDIA RTX 6000 Ada Generation, and NVIDIA GeForce RTX 4090. Server OS: Ubuntu 24.04 or 26.04. Verify the actual server environment and pin compatible Python, framework, NVIDIA driver, and runtime versions before training.

Daily computer, inspected read-only: Windows 11 Pro 64-bit; Intel Core i7-1265U with 10 cores and 12 logical processors; approximately 32 GB RAM; Intel Iris Xe graphics. Approximately 4 GB RAM was available during inspection; this is a transient reading, not a fixed capacity limit.

Use GPU-capable training on the server and CPU inference on Windows. Start by running independent experiments on the two GPUs and benchmark before using both for one model. Set resource limits to avoid contention between trials. Report unsupported GPU settings and any compatible CPU fallback.

Proposed operating defaults, subject to development-only validation:

| Operation | Starting policy |
|---|---|
| Validate and ingest results | After completed results become available |
| Refresh historical features | After each accepted update |
| Generate forecasts | After an accepted update or an explicit request |
| Refit selected models | Weekly on the server |
| Revisit hyperparameters | Monthly within a bounded search budget |
| Initial experiment search budget | 12–24 hours, reviewed after a measured pilot |
| Deploy a replacement | Only after predefined validation and Windows compatibility checks |

The search budget is not a completion-time promise. Compare weekly, daily, and monthly retraining in development before locking the operating policy. Updating feature history and using fixed model weights are separate operations.

Package model weights, native model files, feature construction, class/region/province/prize mappings, calibration and ensemble settings, required history or sufficient feature state, environment requirements, and a manifest with versions and cutoffs. Keep deployment self-contained; the training server need not remain online for local predictions once required artifacts and results are available.

Benchmark actual CPU inference latency and peak memory on the Windows computer. Preserve the currently working model when a replacement fails validation. Compare server and Windows probabilities within documented numerical tolerances. Compression or quantization is optional and requires revalidation; no automatic hardware upgrade is assumed.

## 9. Original implementation stages, unchanged

Stage 1: Data loading, validation, feature engineering, and baseline models.

- Specify and implement separately checkpointed XSMT collection and validated yearly exports alongside the existing XSMN history, as part of Stage 1 data loading. Preserve the current collector's files and progress.
- Load both regions' yearly G.8/G.ĐB history, build the shared calendar index, audit source layouts and coverage, and define region-aware schemas, snapshots, deduplication, and timing rules.
- Implement causal feature construction, missing-history behavior, and the required baselines.
- Define chronological development/test boundaries and predict-before-reveal contracts. Run relevant baseline and leakage tests.

Stage 2: CatBoost, XGBoost, and LightGBM.

- Implement the three multiclass model wrappers, pooled/province and within-/cross-region comparisons, prize-specific predictions, probability alignment, persistence, and CPU/GPU compatibility.
- Validate using past-only development predictions and run relevant tests.

Stage 3: PyTorch causal Transformer.

- Implement the original configurable architecture, region/province/prize representation, historical sequence handling, optional joint learning, and server training support.
- Verify causal masking, padding/missing-history behavior, saved-state loading, and CPU inference.

Stage 4: Weighted ensemble and leakage-free stacking.

- Implement constrained averaging, explicit chronological out-of-fold stacking, and uniform shrinkage/fallback comparisons.
- Validate fold separation, class alignment, prize-specific outputs, and inference schemas.

Stage 5: Hyperparameter optimization and probability calibration.

- Implement bounded, reproducible Optuna studies, nested chronological selection, calibration fitting/evaluation, and retraining-policy comparisons.
- Freeze the selected methods and operating policies before final testing.

Stage 6: Backtesting, inference, automated testing, and documentation.

- Complete the end-to-end historical predict-before-reveal backtester, execute the reserved evaluation under the frozen policy, and report results.
- Complete next-draw and informational-outlook inference, forecast logging and scoring, Windows deployment, automated tests, and documentation.

Run relevant tests after every stage and resolve failures before proceeding. Testing and temporal contracts apply throughout; the full backtesting deliverable remains in Stage 6.

## 10. Engineering, testing, and deliverables

Use Python 3.11 or later, with an exact version selected for compatibility. Retain PyTorch, CatBoost, XGBoost, LightGBM, scikit-learn, Optuna, Pandas/NumPy, optional Polars, and appropriate persistence tools. Keep ML code and its dependency files in a separate `number_prediction/` subproject and isolated virtual environment. The original scraper, migration, and collection tooling remains standard-library-only and retains its documented Python 3.10+ compatibility. Do not install ML dependencies into system Python or make existing archive commands depend on them. Support CSV and Excel inputs with configurable column mappings, retaining yearly CSV archives as the configured primary source. Record random seeds, request deterministic execution where supported, and document reproducibility limits across hardware and libraries.

Inspect and reuse appropriate existing infrastructure before coding. Under `number_prediction/`, organize independent modules for configuration, loading, validation/preprocessing, features, models, stacking, optimization, evaluation, persistence, schedules, and inference. Retain train.py, predict.py, backtest.py, tests, README, configuration, model artifacts, and results outputs within that subproject. Make data roots configurable relative to the clone or explicit Linux paths. Keep raw historical exports intact. Keep generated model weights, experiment databases, caches, and large result artifacts out of ordinary source commits by default; document their storage and transfer separately. Publish implementation source and documentation to the existing private repository using the owner's authorized workflow.

Tests must cover data validation and quality exclusions; leading zeros; fixed calendar-day indices and missing-date gaps; region/province/prize identity and sequence isolation; XSMT parsing and collection checkpoints; duplicate observations across overlapping regional/province pages; preservation of existing XSMN exports; modifying future rows without changing past inputs or predictions; same-date prediction/reveal separation across regions; missing classes and fallback behavior; causal attention; normalization and class order; chronological stacking and tuning separation; save/load round trips; updated-history features; regional schedule and forecast-horizon behavior; immutable forecast records and scoring; and Ubuntu-to-Windows inference agreement.

Include synthetic independent uniform outcomes and clearly injected dependencies, including province-specific and cross-prize cases. Across repeated random simulations, evaluate false-positive behavior rather than requiring every random run to show no apparent improvement. Verify that sufficiently strong injected dependencies can be learned without leakage.

Deliver the complete source and pinned installation instructions; XSMT collection support alongside preserved XSMN collection; region-aware data/configuration schemas; all requested model families; reproducible training and optimization; chronological stacking and calibration; historical and prospective scoring support; next-draw and five-day forecast interfaces; CPU deployment package; automated tests and synthetic generators; model/data manifests; and a comparison report covering within-region and cross-region performance, accuracy, probability quality, uncertainty, coverage, training cost, and local inference cost.

Acceptance requires collection support for both regions with actual coverage disclosed; reproducible past-only predictions; complete 100-class outputs for both selectable targets where supported by validated data; correct calendar/regional schedule handling; all original model families and ensemble methods compared; a functioning CPU deployment; and an honest held-out assessment. It does not require unavailable archive dates to be filled or a learned model to beat chance or the strongest baseline.

Keep an implementation progress record and stage reports as described in [PREDICTION_KUBUNTU_HANDOFF.md](PREDICTION_KUBUNTU_HANDOFF.md). This planning Windows session does not establish Kubuntu acceptance, training-server acceptance, or performance of any unimplemented model.

## Technical references

- Southern Vietnam results source: https://xosodaiphat.com/xsmn-xo-so-mien-nam.html
- Central Vietnam results and current schedule source: https://xosodaiphat.com/xsmt-xo-so-mien-trung.html
- Central Vietnam rolling results: https://xosodaiphat.com/xsmt-30-ngay.html
- Chronological validation: https://scikit-learn.org/stable/modules/generated/sklearn.model_selection.TimeSeriesSplit.html
- Stacking behavior: https://scikit-learn.org/stable/modules/generated/sklearn.ensemble.StackingClassifier.html
- Cross-validated prediction contract: https://scikit-learn.org/stable/modules/generated/sklearn.model_selection.cross_val_predict.html
- PyTorch saving/loading across devices: https://docs.pytorch.org/tutorials/beginner/saving_loading_models.html
- CatBoost prediction schema: https://catboost.ai/docs/en/concepts/python-reference_catboostclassifier_predict_proba
- NVIDIA Linux compatibility: https://docs.nvidia.com/cuda/cuda-installation-guide-linux/index.html
