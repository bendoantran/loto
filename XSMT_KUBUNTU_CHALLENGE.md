# Kubuntu implementation test: miền Trung (XSMT)

## Assignment and boundary

Implement and run a **new XSMT collector on the Kubuntu computer** for:

**https://xosodaiphat.com/xsmt-xo-so-mien-trung.html**

Use the same extraction method, source preservation, yearly organization, checkpoints, internet-outage recovery, display, and monitoring policy as the completed XSMN project. This is a new implementation exercise, not another migration of the existing Southern archive.

**This repository currently includes the XSMN implementation and an XSMT assessment kit. It does not yet provide a production XSMT collector or a `--region` option.** The Kubuntu agent must implement those changes. The scripts and commands below describe the required interface after implementation. The frozen reference files and grader are not proof that the Kubuntu implementation has run.

Keep `bendoantran/loto` private. Preserve the original XSMN snapshot, 7,005 checked dates and all original data. Add XSMT without repointing or overwriting the original database, URLs, progress files, notifications, or systemd units.

## Evidence from the supplied source

The supplied page was fetched and frozen on October 22, 2026. The assessment kit contains:

- `reference/xsmt/raw/region-2026-10-22.html.gz`: the original supplied regional page.
- Nine fixed daily pages in `reference/xsmt/raw/` (seven benchmark days and two year-boundary days).
- `reference/xsmt/expected.json`: source URLs, fetch times, SHA-256 hashes, expected prize strings, province order, loto values and exact totals.
- `tools/check_xsmt_benchmark.py`: a candidate-output grader. It reads an independently produced dataset; it does not scrape or implement the collector.
- `test_xsmt_reference.py`: tests of the assessment kit, including rejection of corrupted CSV values and wrong-region checkpoints. Its assembled test outputs are explicitly synthetic test artifacts, not a completed Kubuntu scrape.

Do not replace frozen expected results with whatever a candidate produces. If the website later corrects a historical result, preserve the new raw response and report a source-versus-reference difference instead of silently changing the answer key.

Source details the agent must handle correctly:

1. The observed XSMT prize table **uses CSS class `table-xsmn`**, shared with XSMN. Do not assume that the region is identified by the class name, or invent a required `table-xsmt` selector.
2. Identify region from the requested source profile and the dated result heading/breadcrumb. Merely finding “XSMT” somewhere in a page is insufficient because menus contain links to multiple regions.
3. The historical URL pattern observed from the supplied page is **`https://xosodaiphat.com/xsmt-DD-MM-YYYY.html`**.
4. Modern completed fixtures have **nine tiers and 18 winning-number appearances per province/date**, with two or three province columns in this benchmark. Read province names and order from each actual table; do not reuse the XSMN schedule or hardcode a column count.
5. The same page contains province loto tables, links, sidebars, advertisements and generic explanatory text. Associate the correct loto tables with each date/province and ignore unrelated sidebar tables.
6. The source's generic “today” text and stated 17:15 draw time do not establish a result table's date or completeness. Read its dated heading and numeric cells. Do not ingest a partial live draw as a clean completed draw.

## Stage A — Protect and verify the existing project

On Kubuntu, first follow `KUBUNTU_AGENT_HANDOFF.md`, restore the XSMN checkpoint, and run its full baseline audit. Record its exact counts and hashes before adapting code.

Use separate data roots:

```text
~/Documents/xoso                  existing clone and completed XSMN archive
~/Documents/xoso-xsmt-pilot       new seven-day XSMT live test
~/Documents/xoso-xsmt-boundary    separate two-day year-transition test
~/Documents/xoso-xsmt             eventual full XSMT history
```

Resolve the actual home directory on the target computer. If any destination already contains work, inspect and reuse its correct checkpoint, or select a new empty root. Do not delete or reset it. Treat an interrupted pilot as work to resume, not an excuse to start over.

The new date range applies only to XSMT. The XSMN range remains **2007-08-18 through 2026-10-21** and must continue to pass its existing baseline verifier.

## Stage B — Implement explicit region profiles

Prefer a small region-aware extension to the proven collector over a separate replacement framework. Implement explicit profiles for `xsmn` and `xsmt` and propagate the profile through URLs, parsing, state validation, controls, verification and monitoring.

Required behavior:

- Preserve XSMN as the backward-compatible default. Legacy checkpoints with no region key are XSMN, not automatically reclassified XSMT.
- Every **new XSMT checkpoint must store `settings.region = "xsmt"`**. Validate the saved region before any network request, export, or mutation.
- Refuse an XSMT command pointed at the existing XSMN database, even though its date keys and shared table class could otherwise parse successfully. Refuse the reverse mismatch too.
- Generate only `xsmt-...` daily URLs for XSMT. Update cancellation/not-archived detection for the actual XSMT source wording; the current XSMN cancellation regex is region-specific.
- Validate the actual dated heading's region and date. A valid numeric table from the wrong region must not pass.
- Preserve source number strings, historical formats, original order and repeats, displayed loto and independently derived loto. Continue to flag unexplained source discrepancies rather than altering numbers.
- Keep the existing CSV columns and draw fields. Add region metadata in checkpoint/provenance where useful without breaking the existing XSMN export consumers or changing the frozen snapshot.
- Require an explicit XSMT start/end range when creating a fresh root until its historical availability has been investigated. Do not inherit XSMN's August 18, 2007 start date as an XSMT fact.
- Do not globally replace `xsmn` with `xsmt`. That would change the existing scraper and miss the shared HTML class.

Required CLI shape (implement it before running these commands):

```bash
python3 history.py run --region xsmt --root "$HOME/Documents/xoso-xsmt-pilot" --start 2026-10-16 --end 2026-10-22
python3 history.py status --region xsmt --root "$HOME/Documents/xoso-xsmt-pilot"
python3 history.py export --region xsmt --root "$HOME/Documents/xoso-xsmt-pilot"
```

Add corresponding region/root propagation to the control tools, or supply equivalent XSMT-specific wrappers and document them precisely. Existing XSMN commands must still work.

## Stage C — The live seven-day accuracy test

Fetch and process the historical daily pages for the **fixed range 2026-10-16 through 2026-10-22**, sequentially, from the real website on Kubuntu. Use the same pacing and retries as the existing collector. Keep the seven live responses and their hashes in the new pilot root.

Expected modern reference totals:

| Draw date | Province columns in source order | Draws | Winning-number appearances |
|---|---|---:|---:|
| 2026-10-16 | Gia Lai; Ninh Thuận | 2 | 36 |
| 2026-10-17 | Đà Nẵng; Quảng Ngãi; Đắk Nông | 3 | 54 |
| 2026-10-18 | Khánh Hòa; Kon Tum; Huế | 3 | 54 |
| 2026-10-19 | Phú Yên; Huế | 2 | 36 |
| 2026-10-20 | Đắk Lắk; Quảng Nam | 2 | 36 |
| 2026-10-21 | Đà Nẵng; Khánh Hòa | 2 | 36 |
| 2026-10-22 | Quảng Bình; Bình Định; Quảng Trị | 3 | 54 |
| **Total** | **7 dates** | **17** | **306** |

After the pilot finishes, stop any worker and run the supplied independent output grader from the clone:

```bash
python3 tools/check_xsmt_benchmark.py --root "$HOME/Documents/xoso-xsmt-pilot" --case pilot
```

Expected output includes `passed: true`, `dates: 7`, `province_date_draws: 17`, and `winning_numbers: 306`.

The grader checks exact date/province/tier/position/number/loto values, repeats, leading zeros, province order, raw-page counts, own-source hashes, source URLs, SQLite integrity, explicit region identity, checkpoint totals, and CSV/JSON/database agreement. It permits new live HTML bytes to differ from the frozen bytes while requiring the same published numbers and internally valid source hashes.

Spot checks from the fixed fixtures, in addition to the full comparison:

- **2026-10-21, Khánh Hòa, G.ĐB = `044743`**. Do not convert it to an integer or discard its first zero.
- **2026-10-18, Khánh Hòa, G.8 = `09`**.
- **2026-10-22, Bình Định, G.6 includes `0144` and `0774`**.
- **2026-10-21, Khánh Hòa's displayed loto contains `04` twice**. Do not deduplicate it.

Reading the supplied expected JSON and emitting its values is not a live-scraping implementation. The assessment report must distinguish the frozen-fixture test, actual Kubuntu network requests, and the produced dataset. Include live request logs and raw-response hashes as evidence, with no credentials.

## Stage D — Prove resumability and durability

Preserve the existing operational values: **one request at a time**, **20-second timeout**, **1.5-second rest after each successful request**, **5/10/20/40/60-second network backoff**, **WAL/FULL SQLite commits after each date**, and **raw HTML saved before parsing**.

Create a dedicated scratch test root for fault injection. Do not mutate the completed XSMN archive or reset the live pilot to manufacture a demonstration. Run and record these tests:

1. **Interruption after committed progress:** stop after at least two saved dates, restart the process with the same root, and prove those dates were not requested again. Check request counts and hashes, not just a printed “resume” message.
2. **Internet loss and recovery:** use an injected failing transport or controlled loopback HTTP server to produce at least two connection errors, then a successful response. Verify retries, increasing delays, no fabricated success, and continuation from the pending date. Do not disable the owner's Wi-Fi without their instruction.
3. **Crash after raw save, before commit:** leave a downloaded raw page with an unfinished row, restart, and prove the cached page is reused without another HTTP request.
4. **Crash after commit, before export refresh:** verify the date stays committed, is not re-downloaded, and yearly exports rebuild without duplicates.
5. **Exclusive lock:** hold the data root in one Linux process, start a second, and prove it is refused. Do not delete the lock file to defeat the guard.
6. **Durable intentional stop:** STOP persists across process restart and reboot; the monitor/supervisor must not override it. Only an explicit start/resume command may clear it.
7. **Power/process restart recovery:** use the supplied checkpoint and supervisor approach, preserving the same data root. Do not claim a physical Kubuntu reboot test unless one actually happened; report a simulated crash test separately.

The original tests may mock time for fast deterministic retries, but production settings must retain the real values. Document which tests use frozen/synthetic responses and which run against the live website.

## Stage E — Prove year-by-year output

Use the separate boundary root and the **fixed range 2025-12-31 through 2026-01-01**. Do not reconfigure the seven-day pilot's saved range.

After implementing region support:

```bash
python3 history.py run --region xsmt --root "$HOME/Documents/xoso-xsmt-boundary" --start 2025-12-31 --end 2026-01-01
python3 tools/check_xsmt_benchmark.py --root "$HOME/Documents/xoso-xsmt-boundary" --case year-boundary
```

Expected: **2 checked dates, 5 province/date draws, 90 winning numbers**, split into actual **`years/2025/` and `years/2026/`** folders. Each folder must have CSV, JSONL, issue records, and the appropriate original HTML. The 2025 exports must be finalized before collection advances into 2026.

## Stage F — Same display, controls and monitoring

Produce a separate XSMT `PROGRESS.md` and `progress.json` in each XSMT data root. Keep the existing year-table structure, progress counts, UTC timestamps and distinction between clean completion and completion with issues. The display must refresh from real committed progress after each date and during retries, not from a fake progress bar or hardcoded values.

Keep yearly export refresh every 10 newly processed dates, on year completion and on graceful stop. The fixed pilot is already shorter than 10 days; its final export must still be written.

Supply clearly documented XSMT start/status/stop/view commands. Kubuntu services and timers must have **different names** from the existing XSMN units, for example `loto-xsmt-history.service` and `loto-xsmt-monitor.timer`. Pass the correct region and data root into every process. Do not replace the original units.

Apply the same quiet 30-minute policy: report newly completed years, final completion, sustained parser/source problems or failures needing attention. Stay quiet while advancing within a year, automatically retrying the internet, or unchanged after final completion. Keep XSMT notification history separate from XSMN's already-finished monitor state. Never infer that the Windows chat automation moved to Kubuntu automatically.

## Stage G — Discover and collect full XSMT history

Once the accuracy, isolation and recovery tests pass, use the separate full root **`$HOME/Documents/xoso-xsmt`** for the owner's requested historical collection.

Investigate XSMT history independently. Record the earliest verified available dated XSMT results page, nearby earlier missing/not-archived/cancelled pages and the search method. A single missing day does not prove all earlier dates are absent. Do not call XSMN's August 18, 2007 boundary the XSMT start without evidence. Freeze the confirmed full range through **2026-10-22** and document any uncertainty or gaps.

Collect ascending dates one calendar year at a time, with resumable checkpoints, preserved source HTML, the same quality statuses and year-completion notifications. Run in the background with supervision while the computer is awake. Internet off/on must be handled automatically without clearing state. A long full-history run may remain in progress after implementation acceptance, but must have a live, verified checkpoint and an installed progress monitor; do not report the whole history finished until every requested date has been checked and audited.

Do not add future dates or automatic daily updates unless the owner requests them. Do not upload XSMT data to a new repository or make this one public. If committing implementation changes to `bendoantran/loto`, preserve existing work and use the owner's normal private-repository workflow.

## Negative cases that must be tested

- An XSMN result page sent to the XSMT parser, and an XSMT page sent to the XSMN parser.
- A correct-region page with the wrong date.
- Numeric prize rows mixed with unrelated sidebar tables or changed province order.
- Partial live numbers, empty cells, captcha/login/error HTML or a layout that cannot be interpreted safely.
- A genuine explicit XSMT no-draw notice, and an explicit not-archived notice. Synthetic examples must be labeled test fixtures, not claimed as real historical availability evidence.
- Missing/duplicate prize tiers, unusual widths/counts, loto mismatches and repeated two-digit endings.
- An existing database whose saved region or range does not match the command.

Use known quality states and preserve the source. Do not count an unreadable page as saved or a network error as unavailable.

## Evidence report and scoring

Write **`XSMT_ACCEPTANCE_REPORT.md`** and **`xsmt-acceptance.json`** on the Kubuntu computer. Include actual OS/Python version, code commit, data roots, source URLs and fetch times, fixture/live-source distinction, test outputs, benchmark totals, raw hashes, retry/request-count evidence, year split, lock proof, STOP proof, progress screenshots or captured tables, installed service/timer paths, and any untested reboot or permission step. Record the independently researched historical boundary and full-run progress separately.

| Area | Points | Required evidence |
|---|---:|---|
| Region isolation and correct source handling | 20 | Wrong-region guards; separate data/monitor/service roots; original XSMN audit still passes |
| Numeric and loto accuracy | 25 | Pilot grader passes all 306 values; exact strings, order and repeats |
| Interruption, internet and checkpoint recovery | 25 | Request counters, cache reuse, crash/restart tests, exclusive Linux lock, durable STOP |
| Calendar-year organization | 10 | Boundary grader passes 90 numbers in separate 2025/2026 exports |
| Existing display and quiet monitoring | 10 | Actual progress files, correct counts, refresh and notification history |
| Reproducible Kubuntu evidence | 10 | Actual target commands, old-regression suite, baseline audit and honest acceptance report |
| **Total** | **100** | **No credit for unsupported claims or hardcoded output** |

The implementation cannot pass if it overwrites the original archive, mixes regions, makes the repository public, fabricates missing numbers, discards leading zeros/repeats, or claims recovery without saved checkpoint/request evidence. Passing the automated benchmark is necessary, but does not replace the recovery and target-environment checks.

## Paste this into the Kubuntu AI agent

```text
Add a real miền Trung (XSMT) collector to my private https://github.com/bendoantran/loto project. Read AGENTS.md, KUBUNTU_AGENT_HANDOFF.md, and XSMT_KUBUNTU_CHALLENGE.md completely. Implement the XSMT challenge on this Kubuntu computer with the same method, durability, retries, yearly exports, PROGRESS.md/progress.json display, start/status/stop controls and quiet monitoring as the existing scraper.

Preserve the completed XSMN archive and its fixed range. The new task is authorized in separate XSMT roots, with region mismatch guards and distinct services/monitor state. The repository contains reference HTML, expected results and a grader, not an already implemented XSMT production collector. Do not claim that reading those files is live scraping. Inspect the real source: its prize table shares the table-xsmn class, while the region identity and historical URLs are XSMT.

Implement the required --region interface and run the seven-day live pilot (2026-10-16 through 2026-10-22: 7 dates, 17 draws, 306 winning numbers), the two-day year-boundary case (2025-12-31 through 2026-01-01: 2 dates, 5 draws, 90 numbers), and the supplied output graders. Prove network failure/recovery, process restart without repeat downloads, cached-page reuse, year transitions, duplicate-worker refusal, STOP persistence and real progress reporting. Re-run the original XSMN baseline verifier and all regression tests.

After those pass, research the oldest XSMT results independently, freeze its historical range through 2026-10-22, and start the resumable year-by-year historical run in the separate full XSMT root with monitoring. Write the required Markdown/JSON acceptance report and score only verified evidence. Do not invent dates/numbers, reset old work, substitute a new dashboard, bypass source restrictions, or claim a physical reboot/full-history completion that did not happen. Proceed with authorized reversible work without repeatedly asking me for confirmation; report any actual target-specific permission or access blocker precisely.
```
