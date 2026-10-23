# Stage 2: CatBoost, XGBoost, and LightGBM

Status: implementation and local pilot verified; full stage acceptance remains pending the work below.

All three native multiclass wrappers produce stable 100-class outputs, with observed-class remapping and .01 default uniform mixing; absent classes never require fake labels. Native save/load is tested. CPU execution is actual; unsupported GPU builds report errors.

## Actual validation

Tests: `test_trees` passes missing/single-class, injected province dependency, alignment and native persistence. All three families fit both prizes in the real 2007 pilot; detailed metrics and times are in `local-evidence.json`. These are smaller pilot settings, not full server results.

## Remaining acceptance

Execute the complete matched-date regional/province/input-scope development comparisons and verify actual server GPU builds.

Code and data hashes, measured metrics, environment and limitations are recorded in `local-evidence.json`. No GPU, Windows, final-test or future result is claimed.
