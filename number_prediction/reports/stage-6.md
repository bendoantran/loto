# Stage 6: Backtesting, inference, automated testing, and documentation

Status: implementation and local pilot verified; full stage acceptance remains pending the work below.

Historical forecasts commit before scoring and are labeled simulated. Ineligible learned periods use uniform warm-up and receive separate eligible/full operational metrics. The prospective append-only ledger preserves forecasts and outcome revisions. Schedule versions restrict actual scheduled dates; unsupported learned horizons are unavailable. Full JSON/CSV distributions, private CPU packages and cross-machine probe tools are implemented.

## Actual validation

The 20-test prediction suite and 36-test archive suite pass. Operational backtest: 907 development draws, including 739 uniform warm-up draws. A private deployment ZIP was produced; a local CPU probe ran. Four prospective uniform forecasts were recorded for both prizes over scheduled dates; they are unscored. The nine-job server grid was prepared without starting it.

## Remaining acceptance

Complete full server comparisons, freeze/score the reserved test once, run the package on the actual Windows computer, compare all probabilities, and score future prospective outcomes. Server/Windows access was not supplied.

Code and data hashes, measured metrics, environment and limitations are recorded in `local-evidence.json`. No GPU, Windows, final-test or future result is claimed.
