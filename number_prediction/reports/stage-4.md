# Stage 4: Weighted ensemble and leakage-free stacking

Status: implementation and local pilot verified; full stage acceptance remains pending the work below.

Averaging requires four aligned outputs and nonnegative unit-sum weights. The regularized multinomial stack consumes 400 probabilities. Initial fit-only rows never enter stack training. Base configurations remain separate from stack hyperparameter selection; OOF children fit anew with internal earlier early-stop validation.

## Actual validation

The chronological callback tests and full synthetic package integration pass. Both averaging and stacking fitted and scored both prizes in the real pilot. Stack manifests retain strict train-label-max < heldout-origin-min evidence. Logistic coefficients persist as JSON.

## Remaining acceptance

Run full-scale development comparisons with fixed or nested base configurations and review uncertainty/resources.

Code and data hashes, measured metrics, environment and limitations are recorded in `local-evidence.json`. No GPU, Windows, final-test or future result is claimed.
