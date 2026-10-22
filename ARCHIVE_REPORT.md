# loto historical archive — final report

Range: **2007-08-18 through 2026-10-21**.
Verified at: 2026-10-22T11:00:10+00:00 (UTC).

All **7,005 requested dates** have been checked, across **20 calendar years** (partial 2007 and 2026). The collector has finished and exited.

Saved **21,592 province/date draws** and **388,656 winning numbers**. Repeated appearances and leading zeros are retained.

## Coverage

| Date status | Count |
|---|---:|
| Clean results | 6,775 |
| Results saved with source inconsistencies flagged | 95 |
| Source explicitly states no draw took place | 133 |
| Original HTML preserved; source results incomplete or empty | 2 |
| Source explicitly says not archived | 0 |

The 133 no-draw dates comprise April 1–28, 2020 (28 dates), and July 9–October 21, 2021 (105 dates). Each saved page explicitly states that no draw took place; its prize cells are empty. These are counted separately from missing data.

## Unresolved source gaps

- **September 2, 2008:** every prize cell in the source table is empty.
- **February 3, 2011:** the source omits An Giang first-prize and special-prize numbers. This date remains in review; its full HTML, including the other published numbers, is preserved.

These two dates have no extracted numeric records in the yearly CSV exports. No missing numbers have been invented. The 95 flagged dates retain the published numbers exactly; detailed flags and source URLs appear in the yearly `issues.jsonl` files and `archive-audit.json`.

## Year-by-year coverage

| Year | Checked dates | Clean | Flagged | No draw | Review | Saved numbers |
|---|---:|---:|---:|---:|---:|---:|
| 2007 | 136 | 116 | 20 | 0 | 0 | 7,704 |
| 2008 | 366 | 313 | 52 | 0 | 1 | 20,646 |
| 2009 | 365 | 355 | 10 | 0 | 0 | 20,646 |
| 2010 | 365 | 364 | 1 | 0 | 0 | 20,646 |
| 2011 | 365 | 361 | 3 | 0 | 1 | 20,610 |
| 2012 | 366 | 360 | 6 | 0 | 0 | 20,700 |
| 2013 | 365 | 365 | 0 | 0 | 0 | 20,646 |
| 2014 | 365 | 363 | 2 | 0 | 0 | 20,646 |
| 2015 | 365 | 365 | 0 | 0 | 0 | 20,646 |
| 2016 | 366 | 365 | 1 | 0 | 0 | 20,718 |
| 2017 | 365 | 365 | 0 | 0 | 0 | 20,646 |
| 2018 | 365 | 365 | 0 | 0 | 0 | 20,646 |
| 2019 | 365 | 365 | 0 | 0 | 0 | 20,646 |
| 2020 | 366 | 338 | 0 | 28 | 0 | 19,116 |
| 2021 | 365 | 260 | 0 | 105 | 0 | 14,706 |
| 2022 | 365 | 365 | 0 | 0 | 0 | 20,664 |
| 2023 | 365 | 365 | 0 | 0 | 0 | 20,646 |
| 2024 | 366 | 366 | 0 | 0 | 0 | 20,700 |
| 2025 | 365 | 365 | 0 | 0 | 0 | 20,646 |
| 2026 | 294 | 294 | 0 | 0 | 0 | 16,632 |

## Verification

- SQLite integrity_check passed.
- All 7005 requested dates present exactly once.
- All yearly JSONL date coverage complete.
- All 7005 saved HTML hashes match database and exports.
- CSV numbers and loto endings match JSON exactly, including leading zeros.
- No duplicate number keys.
- All yearly raw HTML file counts match checked dates.
- Worker exited after finishing.

## Storage and locations

Project folder: `C:\Users\bendo\Documents\xoso`.
Project size at audit: approximately **216.4 MB** (206.4 MiB), including checkpoints, logs, exports, and compressed HTML.
The original HTML totals **601.9 MB** before compression and **135.0 MB** compressed.

- `years/YYYY/results.jsonl`: date records, original numbers, loto results, provenance, and status.
- `years/YYYY/prizes.csv`: one row per published winning number; import number/loto fields as Text.
- `years/YYYY/issues.jsonl`: source inconsistencies and unresolved dates.
- `years/YYYY/raw/YYYY-MM-DD.html.gz`: original compressed responses.
- `history.sqlite3`: durable collection checkpoints and stored results.
- `archive-audit.json`: verification results and all flagged-date details.
- `PROGRESS.md`: completed coverage overview.

This run covers the fixed requested range through October 21, 2026. It does not automatically fetch subsequent draw dates.
