# XSMT completion and small-data integration test

XSMT collection completed on 2026-10-22 at 19:21:39 UTC (3:21:39 p.m. EDT). The worker exited. Full consistency audits passed for both regional archives.

| Archive | Requested dates | Province/date draws | Number appearances |
|---|---:|---:|---:|
| XSMN | 7,005 | 21,592 | 388,656 |
| XSMT | 7,006 | 16,167 | 291,006 |

XSMT retains 6,960 saved dates, four flagged dates, 23 explicit no-draw dates and 19 review dates. These source issues were preserved; completion does not mean every date has clean, complete results. All 7,073 frozen XSMN assets still match their original manifest hashes.

## Modeling snapshot

New immutable snapshot: `number_prediction/datasets/post-xsmt-20261022T1936`.
Data version: `2c1037f153a3818ae1272614239bb85b7c9c82cac9a56cf8a3a3ac4fd9844a58`.

Both sources have complete export coverage. The snapshot contains 75,424 eligible prize targets: 43,098 XSMN and 32,326 XSMT. Source exclusions and unrelated-tier inclusions retain individual reasons. Original archives and all earlier snapshots were preserved. Generated snapshots remain local and excluded from ordinary source commits.

## Authorized bounded test

Only the documented small CPU pilot ran: fit 2007-08-18–2007-10-15, calibrate through 2007-11-15, and validate through 2007-12-31. Tree models used eight iterations; the Transformer used d_model 16, two heads, one layer, sequence eight and one epoch. CPU libraries were limited to two threads.

CatBoost, XGBoost, LightGBM, Transformer, weighted averaging, chronological stacking, uniform, historical frequency, smoothed frequency, province and Markov baselines all ran separately for G.8 and G.ĐB. This produced 22 predictor/prize comparisons. G.8 used 312 fit, 164 calibration and 243 validation examples; G.ĐB used 321, 168 and 250 respectively. The validation dates included both regions.

All 22 packages were loaded, used on strictly later 2008 development probes from both regions, saved again and reloaded. Every probability matrix had 100 aligned classes, finite nonnegative values and unit row sums. Save/load probabilities agreed within atol 1e-7, rtol 1e-6. Original packages and ledgers were retained.

Local verification: **22 prediction tests and 36 archive/collector tests passed**, plus three focused checks after restoring fold audit metadata. The tests cover leading zeros, quality policy, duplicate identities, future-data invariance, causal masking, chronological OOF/calibration boundaries, missing classes, native persistence and immutable forecasts.

## Portability repairs

Text-file reads/writes now specify UTF-8. CLI output explicitly uses UTF-8, including redirected Windows cp1252 environments. New regression checks load Vietnamese province/model/schedule text with explicit encoding and exercise CLI help under forced cp1252 output. Stacking fold audit records now survive predictor reloads. Hosted Windows CI is tracked in private PR #1; these local tests do not establish performance or compatibility on the owner's actual Windows computer or server.

## Preserved limits

No full model-training run, archive-data hyperparameter search, server/GPU run, or reserved 2025–2026 final-test scoring was started. This pilot verifies the pipeline executes; it does not establish predictive advantage. Full server experiments and actual Windows resource/probability measurements still require separate authorization and access.

Machine-readable audit, code/data versions, per-model pilot evidence, round-trip checks and source issue dates are in `post-xsmt-completion.json`.

## Publication status

The verified UTF-8/fold-metadata fixes and this report remain local. Automatic approval review rejected the upload to the existing private PR because it did not consider the current local-test request explicit authorization for publication, and the payload includes local paths/project metadata. No alternate upload was attempted. Updating private PR #1 and rerunning its hosted Windows CI require explicit owner approval. The existing PR still contains its earlier source version.
