# Stage 1: Data loading, validation, feature engineering, and baseline models

Status: implementation and local pilot verified; full stage acceptance remains pending the work below.

Read-only source capture verifies checkpoint identity, daily URLs, raw HTML hashes and stable CSV/JSON agreement. Snapshot e0b42c7b43cc075a622b9fa67045d6bfa9d307e385f8966d65c65f68ae10742c contains 46,242 accepted prize targets. XSMN has 7,005 exported dates; XSMT has 690 exported dates in this snapshot and remains incomplete. Source numbers, missing masks, quality decisions and separate region/province sequences are retained. Initial test origin is fixed. The later 2025–2026 reserve has 2,071 XSMN targets per prize, no captured XSMT targets, and roughly 1.3 percentage points nominal 95% top-10 precision near 10% before temporal dependence. The same reserve remains untouched while coverage develops.

## Actual validation

Commands: `python3 tools/restore_snapshot.py --verify-files`; `python3 tools/verify_archive.py --baseline`; `python3 number_prediction/snapshot.py --out number_prediction/datasets/initial`; isolated `test_data` suite. Full audit: 7,005 dates, 21,592 draws, 388,656 appearances. Review/no-draw/flagged source treatment was preserved.

## Remaining acceptance

Complete XSMT history and run its stopped full verifier. Verify aliases before merging identities. Make a new fixed snapshot for full experiments; do not edit the initial one.

Code and data hashes, measured metrics, environment and limitations are recorded in `local-evidence.json`. No GPU, Windows, final-test or future result is claimed.
