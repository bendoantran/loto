# Detailed project review

## Purpose and authorized task

This private repository stores a completed XSMN lottery archive and a durable Python collector. The separate XSMT assignment extends that proven collector to Central Vietnam. The prediction documents describe a future project; this task implemented scraping only.

## Instructions and architecture

- `AGENTS.md` protects the original range, archive, schemas, one-worker rule, standard-library-only scraper, source preservation, STOP state, progress display and repository privacy. It prohibits delegation unless the owner asks; no subagents were created.
- `KUBUNTU_AGENT_HANDOFF.md` defines migration by restore/audit, exact baseline counts, retries, cache/commit/export order, controls, systemd units and quiet monitoring. The baseline was restored and fully verified before implementation.
- `XSMT_KUBUNTU_CHALLENGE.md` is the operational assignment: explicit region profiles, isolated roots, exact seven-day live pilot, actual year-boundary test, failure recovery, independent earliest-date research and supervised full collection.
- `PREDICTION_IMPLEMENTATION_PLAN.md` and `PREDICTION_KUBUNTU_HANDOFF.md` preserve the six future ML stages, two-region inputs, fixed calendar index, prize choices, predict-before-reveal evaluation and three-computer roles. No ML implementation or training was started.
- `README.md`, `HISTORY.md`, `ARCHIVE_REPORT.md`, `PROGRESS.md` and `progress.json` document the current archive, controls, quality states and fixed progress display. The latter two original XSMN files were preserved byte for byte.

## Source modules and data flow

`history.py` is the historical collector. Each data root owns settings, daily checkpoints, lock, STOP marker, raw cache, yearly exports, progress and logs. Daily work is ordered by date; one HTTP request uses a 20-second timeout, followed by 1.5 seconds of pacing. Network errors stay unfinished and retry after 5/10/20/40/60 seconds; rate limits get at least 60 seconds. The raw gzip response is atomically written before parsing. The parsed result, source hash, timestamps and counters are committed to SQLite in WAL/FULL mode after every date. Progress refreshes after every date/retry. CSV/JSONL/issues exports refresh every ten newly processed dates and at year boundaries and graceful exit.

`scrape.py` contains the shared HTML table parser and the original separate single-page XSMN tool. It handles omitted HTML closing tags and the shared `table-xsmn`/`table-loto` classes. Its original strict `extract` routine remains available. New paragraph captions let the XSMT historical parser associate each loto table with the actual province and date.

`regions.py` is the new explicit XSMN/XSMT profile and checkpoint identity layer. It supplies the correct regional and daily URLs, validates the dated draw heading rather than menu text, treats checkpoints without a region key as XSMN, and rejects mismatched regions/ranges/URLs before database mutation or downloads. Every new XSMT checkpoint explicitly stores `region=xsmt` and needs a caller-supplied start/end range.

`history.parse_day` reads actual province columns in source order and nine prize tiers. Values remain strings. It retains original number order, prize positions, leading zeros and repeated appearances, stores displayed and independently derived loto separately, and flags unexplained discrepancies. Empty/non-numeric/incomplete layouts go to review, with raw HTML retained. Explicit source notices identify no-draw and not-archived dates; network failures never become unavailable data.

`tools/control.py` supplies start/status/durable-stop/service-condition commands and now propagates region/root. `tools/monitor.py` uses separate per-root notification state and reports only meaningful year/final completions, sustained review growth or unexpected exits. It respects intentional stops. `tools/install_service.py` generates distinct XSMT unit names and preserves existing units. Actual systemd validation exposed and led to correcting the inherited WorkingDirectory quoting bug.

`tools/restore_snapshot.py` checks snapshot hashes and SQLite integrity and never overwrites existing work. `tools/verify_archive.py` checks complete date coverage, raw hashes, unique numeric keys, counters, and CSV/JSON/database agreement; it now also validates region/source provenance. Neither tool resets the original archive.

`tools/check_xsmt_benchmark.py` remains the independent output grader. Its frozen expected values were not changed. `tools/scrape_region.py` is the new exact-regional-page extraction command. `tools/probe_xsmt_history.py` saves individual historical-discovery responses with hashes and timestamps. `tools/prove_xsmt_recovery.py` records offline injected failures and real child-process crash/restart evidence; it is not a live transport.

The `.sh` and `.ps1` wrappers retain the original XSMN workflow. `XSMT_RUNBOOK.md` documents equivalent explicit-region Python controls and the installed separate services. `.github/workflows/portability.yml` defines Ubuntu/Windows offline CI; this session ran tests on the actual KDE/Ubuntu computer, not Windows or GitHub Actions. `.gitattributes` preserves text line endings and binary archive assets; `.gitignore` excludes mutable databases, logs, locks and credentials.

## Dataset and file roles

- `years/2007` through `years/2026`: original XSMN CSV, JSONL, issue records and 7,005 compressed source responses. These are the canonical historical XSMN exports.
- `snapshots/history.sqlite3.gz`, `snapshots/manifest.json`, `snapshots/monitor-state.json`: frozen migration database, asset hashes and original quiet-completion state.
- `archive-audit.json`: original full audit and per-date flagged/source-gap details. Original numeric totals are 21,592 draws and 388,656 appearances. There are 95 flagged dates, 133 explicit no-draw dates and two review gaps.
- `data/source.html`, `data/results.json`, `data/prizes.csv`: a separate original regional-page snapshot; it must not be counted as extra independent historical draws.
- `reference/xsmt/expected.json`, nine daily gzip pages and one regional gzip page: immutable assessment sources. They are fixtures, not live collection evidence.
- `tests/fixtures`: modern, historical-anomaly, no-draw and unavailable source examples.
- New XSMT pilot/boundary/full roots live separately under this workspace's `work/`. The full collection manifest discloses its independently researched start and earlier-date uncertainty. The full root is still collecting and must receive a final full audit after completion.
- `outputs/xsmt/source.html`, `results.json` and `prizes.csv`: this task's actual scrape of the requested regional URL. It covers seven displayed dates, 17 province/date draws and 306 appearances.

All archive HTML was read/decompressed and checked programmatically by frozen-file/full-archive validation. CSV and JSON values were compared with the restored database. This is a comprehensive structural and consistency inspection; it is not a claim of manually reading every repeated HTML tag and lottery number in the archive.

## Tests, findings and practical limits

The original 25 tests passed before changes. The final 36-test suite adds region/range isolation, malformed/partial/wrong-region source, province/loto association, retry/rate-limit policy, distinct service wiring, and a complete separate-process recovery proof. Both actual live XSMT output graders passed: 306 pilot values and 90 year-boundary values. The original baseline passed again afterward, including all frozen hashes. The completed XSMN start downloaded nothing; its monitor stayed quiet.

Recovery evidence covers stopping after committed dates, cache reuse after abrupt exit between raw save and commit, crash after commit before export, export reconstruction before a year transition, retries without fabricated success, Linux cross-process locking and durable STOP. Retry clocks and transport failures are injected offline; a physical reboot and real power failure were not performed.

Full XSMT collection runs under an installed user service with a separate 30-minute monitor. The machine has Linger=no, so pre-login/after-logout operation was not enabled. Desktop popup delivery was not verified; the journal and per-root event file are available. Keep the machine awake. Earlier historical dates were sampled rather than exhaustively enumerated; 2007-08-18 is the earliest verified available XSMT date in this investigation, not a proved global minimum.

Code changes remain local and uncommitted. `xsmt-acceptance.json` identifies the base commit and exact Python-file hashes. The acceptance report distinguishes full-history progress from finished pilots and records the provisional rubric score and its limitations.
