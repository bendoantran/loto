# Exact Kubuntu migration and AI-agent handoff

## 1. Objective and acceptance boundary

Reproduce the owner's existing **loto** web-scraping project on Kubuntu, including its full archive, parser behavior, checkpoint/resume method, yearly exports, progress table, background operation, and quiet progress monitoring.

Repository: **https://github.com/bendoantran/loto**. It must remain **private**. The Windows source project is `C:\Users\bendo\Documents\xoso`. The recommended Kubuntu clone is **`$HOME/Documents/xoso`**. Resolve `$HOME` on the target computer; do not copy the Windows username or drive letter into Linux commands.

The historical collection is already finished. **Restore and audit it; do not re-download it.** A start command on the migrated baseline must report that nothing needs downloading. The archive's end date remains **2026-10-21**, even if the computer's current date is later. Adding later draws requires a separate owner request and a designed checkpoint-range extension; passing a different `--end` to this existing database is deliberately rejected.

Keep the current display: `PROGRESS.md` and `progress.json`, with the same year rows, status names and counts. There is no existing web dashboard to reproduce. `watch-progress.sh` displays the same Markdown content in a terminal. Local desktop notifications and the optional AI heartbeat use the existing quiet-notification policy; a Windows Codex chat automation does not automatically migrate to another computer.

## 2. Baseline that must survive migration

| Item | Exact value |
|---|---:|
| Earliest requested date | 2007-08-18 |
| Last requested date | 2026-10-21 |
| Calendar dates checked | 7,005 |
| Calendar-year folders | 20 (2007 through 2026; first and last partial) |
| Province/date draws exported | 21,592 |
| Winning-number appearances exported | 388,656 |
| Clean dates (`saved`) | 6,775 |
| Published numbers saved with flags (`flagged`) | 95 |
| Explicit cancelled draws (`no_draw`) | 133 |
| Explicit not-archived dates (`unavailable`) | 0 |
| Unparsed source gaps (`review`) | 2 |

These counts describe the saved source, not an assertion that the website's numbers are official or error-free. No flagged numbers were corrected or invented.

The cancelled draws are **2020-04-01 through 2020-04-28** (28) and **2021-07-09 through 2021-10-21** (105). Every corresponding saved page explicitly says the draw did not take place, and all its prize cells are empty.

The unresolved source gaps are:

- **2008-09-02:** all prize cells are empty.
- **2011-02-03:** An Giang G.1 and special-prize numbers are missing. This entire date remains `review` in the existing extraction method. Other published values are still in its preserved original HTML. Do not silently invent the missing values or change this treatment during migration.

The repository includes all original responses and the original final audit. `snapshots/manifest.json` records the migration snapshot's hashes and totals. The compressed database is approximately 3.6 MB; the full checkout is approximately 192 MB before Git metadata and local restored files. Have about 1 GB free to allow clone, local restore and verification.

## 3. Target prerequisites and authentication

Use a Kubuntu installation with **Python 3.10 or later**, Git, a normal writable local filesystem, and internet access for the initial clone. SQLite, gzip, HTTP, CSV, JSON and locks use the Python standard library. No pip install, npm, Docker, database server, API key, or paid service is required.

First inspect the target:

```bash
uname -a
python3 --version
git --version
command -v systemctl
df -h "$HOME"
```

If the prerequisite tools are missing, install them through the normal Kubuntu package manager, using the owner's authorized sudo flow:

```bash
sudo apt update
sudo apt install -y git python3 ca-certificates gh procps
```

Check the Python version explicitly:

```bash
python3 -c 'import sys; assert sys.version_info >= (3, 10), "Python 3.10+ is required"'
```

If this fails, stop using that interpreter and select an installed Python 3.10+ interpreter or arrange an OS-supported Python update. Do not replace system Python or upgrade the whole operating system automatically.

Authenticate using the owner's GitHub account, or another account that has explicitly been granted access to this private repository. Complete browser/device authentication as the human when necessary; the AI agent must not ask for a token in chat or print credentials:

```bash
gh auth login --hostname github.com --git-protocol https --web
gh auth setup-git
gh api repos/bendoantran/loto --jq '{name: .full_name, private: .private, visibility: .visibility}'
```

Expected `private` is **true** and `visibility` is **private**. A 404 when signed out, or when using an unauthorized account, is normal for a private repository; authenticate rather than making the repository public.

## 4. Clone without overwriting another project

If `$HOME/Documents/xoso` already exists, inspect it before cloning. Reuse it only if it is the intended clone and has no conflicting local work. Otherwise choose a new directory and substitute that path consistently below. Do not delete or reset an existing folder to make the instructions fit.

For a new destination:

```bash
mkdir -p "$HOME/Documents"
git clone --depth 1 https://github.com/bendoantran/loto.git "$HOME/Documents/xoso"
cd "$HOME/Documents/xoso"
git remote -v
git status --short
chmod +x start-history.sh status-history.sh stop-history.sh watch-progress.sh
```

The remote URL must not contain a token. The repository stores individual yearly exports and individual compressed pages, rather than a single oversized Git blob. Do not turn on GitHub Pages or share the repository through a public fork.

## 5. Restore the exact checkpoint, then audit

Run from the clone:

```bash
python3 tools/restore_snapshot.py --verify-files
python3 tools/verify_archive.py --baseline
python3 -m unittest discover -p 'test_*.py' -v
bash status-history.sh
```

The restore command checks the frozen assets' hashes on the first clone, verifies the database checksum and SQLite integrity, and restores `history.sqlite3`. It also seeds the local monitor state. If a database already exists, it leaves that checkpoint untouched and reports `existing_checkpoint_preserved`. Never delete an existing checkpoint merely to rerun restore.

`--verify-files` is intended for the untouched clone: it also checks the baseline progress files. Those display files can legitimately change after future collection. A changed live progress timestamp does not mean the original HTML has changed; use the full archive verifier for an active project's data audit.

The verifier checks every requested date exactly once, all 7,005 original HTML hashes, SQLite integrity, JSON/database agreement, CSV values and loto endings (including leading zeros), unique numeric keys, yearly coverage, and baseline totals. It writes `verification-local.json`. This is the principal migration acceptance result.

The restored status must show:

```text
state: finished
processed_days: 7005
total_days: 7005
percent: 100
saved_days: 6775
flagged_days: 95
no_draw_days: 133
unavailable_days: 0
review_days: 2
worker_running: false
```

Then confirm that starting does not download anything:

```bash
bash start-history.sh
```

Expected: **The saved date range is finished; nothing needs downloading.** This is successful migration, not a failure to start.

## 6. Exact method and data contract

Preserve these operational properties:

1. Source region page: `https://xosodaiphat.com/xsmn-xo-so-mien-nam.html`. Historical URL pattern: `https://xosodaiphat.com/xsmn-DD-MM-YYYY.html`.
2. One network request at a time, with dates ascending and one calendar year completed before the next.
3. HTTP timeout **20 seconds**. Rest **1.5 seconds after every successful network request**, in addition to the download time.
4. Connection/DNS/reset failures retry after **5, 10, 20, 40 and then 60 seconds**, capped at 60. HTTP 403/429 gets at least 60 seconds. Do not bypass access restrictions or add parallel downloading.
5. SQLite journal mode **WAL**, synchronous **FULL**. Commit the result/checkpoint after every date.
6. Write compressed original HTML atomically before parsing. Reuse cached HTML after interruption; skip already terminal dates. A failed network request remains pending/retry, never cleanly completed.
7. All winning numbers are strings. Preserve leading zeros, source order, prize positions, duplicate appearances and Vietnamese province names.
8. Nine prize tiers: G.8, G.7, G.6, G.5, G.4, G.3, G.2, G.1, G.ĐB. Historical five-digit special prizes remain valid. Other unusual widths/counts are flagged without silently changing them.
9. Preserve displayed two-digit loto grouped by first digit. Also store derived two-digit endings separately and flag inconsistencies; never deduplicate repetitions.
10. Keep six date states: pending/retry (unfinished), saved, flagged, no_draw, unavailable and review. `processed` includes every terminal state; it does not mean every date has complete winning numbers.
11. Ignore unrelated sidebar tables even when they share a CSS class with loto tables. Date comes from the actual draw heading, not the page's generic “today” text.
12. Write `progress.json` and `PROGRESS.md` after every date and during retries. Update yearly exports every **10 newly processed dates**, on year transitions and on graceful stop. A forced kill can leave exports behind SQLite; rebuild safely while stopped.

CSV header, unchanged:

```text
date,weekday,province,prize,position,number,loto,quality_flags,source_url
```

Import `number` and `loto` as **Text** in spreadsheet software. JSONL strings preserve leading zeros directly.

## 7. Exact display and file layout

```text
xoso/
  history.py                 historical collector
  scrape.py                  original single-page scraper
  history.sqlite3            local live checkpoint; ignored by Git
  progress.json              live machine-readable progress
  PROGRESS.md                existing year-by-year Markdown display
  history.log                local UTC events/retries; ignored by Git
  monitor-state.json         local notification history; ignored by Git
  monitor-events.jsonl       local meaningful notifications; ignored by Git
  STOP                       durable user stop request, when present
  years/YYYY/
    results.jsonl            one record per checked date
    prizes.csv               one row per winning-number appearance
    issues.jsonl              flagged/unavailable/review records
    raw/YYYY-MM-DD.html.gz    original response for every checked date
  snapshots/
    history.sqlite3.gz       frozen restorable migration checkpoint
    manifest.json            exact snapshot totals/hashes
    monitor-state.json       completed Windows monitor baseline
```

The table columns remain **Year, Processed, Clean, Flagged, No draw, Unavailable, Review, State**. Keep `complete` separate from `finished_with_issues`. UTC timestamps are intentional.

To see the same display continuously:

```bash
bash watch-progress.sh
```

Press Ctrl+C to close the viewer; that does not stop a detached collector. For a KDE editor view, open `PROGRESS.md` in the preferred Markdown/text editor without keeping the file write-locked.

## 8. Start, stop and connection recovery

```bash
bash start-history.sh
bash status-history.sh
bash stop-history.sh
tail -n 30 history.log
```

`start-history.sh` runs a detached local process if work remains. It refuses a duplicate worker and removes STOP only when explicitly starting/resuming. `stop-history.sh` writes STOP and waits up to 30 seconds for graceful exit. Do not delete the lock file to force a second worker.

Wi-Fi may be disconnected and reconnected at any time. Keep the collector process alive; it retries automatically. If the process or computer restarts, run the start command again. The machine must be awake for progress; a powered-off or sleeping computer does not scrape. Do not disable the owner's network or change KDE power-management settings without their instruction. The offline regression suite already simulates network failures and recovery.

For supervised operation and login/reboot resume, install the user service below. Without that service, detached-process survival across a full reboot requires manually starting again.

## 9. Kubuntu systemd user service and quiet 30-minute monitor

Generate the unit files on the target computer, using its actual interpreter and paths:

```bash
cd "$HOME/Documents/xoso"
python3 tools/install_service.py
systemctl --user daemon-reload
systemctl --user cat loto-history.service
systemctl --user cat loto-monitor.service
systemctl --user cat loto-monitor.timer
systemctl --user enable loto-history.service
systemctl --user enable --now loto-monitor.timer
```

The generator will not replace an existing unit silently. Inspect any existing configuration before choosing `--replace`; it backs up previous units. These are **user** units, not root services.

The collector service uses the same `history.py`, `Restart=on-failure`, a 60-second supervisor delay, graceful stop, and a condition that skips a finished archive or a STOP request. An inactive/skipped collector is expected for this completed archive. It will not create a fresh database if restore was omitted.

For unfinished work supervised by this service:

```bash
bash start-history.sh --service
systemctl --user status loto-history.service --no-pager
journalctl --user -u loto-history.service -n 30 --no-pager
bash stop-history.sh
```

STOP persists across reboots. Use `stop-history.sh` when collection must remain stopped until the user chooses start/resume. A plain `systemctl --user stop loto-history.service` performs a graceful supervisor stop but does not create the durable STOP marker; an enabled service may run again after the next login/reboot. Normal system shutdown must not create STOP, otherwise automatic reboot recovery would be disabled. The service therefore uses `KillSignal=SIGINT` without an ExecStop command that writes STOP.

By default, enabled user services start with the user's session. If the owner wants them available before login and after logout, use the normal authorized system configuration:

```bash
loginctl enable-linger "$USER"
loginctl show-user "$USER" -p Linger
```

This may require an authorization prompt or administrator assistance. Do not claim pre-login restart support until `Linger=yes` and the user units have actually been checked on the target system. The completed archive still exits/skips normally rather than running forever.

Monitor commands:

```bash
python3 tools/monitor.py --no-notify --no-restart
systemctl --user list-timers loto-monitor.timer --all
journalctl --user -u loto-monitor.service -n 30 --no-pager
```

The timer checks about every 30 minutes. It remains quiet within a year, during automatic network retries, and after unchanged final completion. It reports newly completed years, full completion, sustained review-count increases, or an unexpectedly dead worker. Its recorded messages are in `monitor-events.jsonl` and the user journal. If `notify-send` is installed and a desktop session is available, it also sends a local desktop notification. Optional package: `sudo apt install libnotify-bin`. A headless session may have journal output without a popup.

The local monitor can restart an unexpectedly exited unfinished worker, but it cannot perform AI reasoning or repair unknown parser changes. If using an AI-agent heartbeat as in the original Windows chat, use the exact policy in section 10. Choose one notification source or suppress desktop popups to avoid duplicates. Do not claim the Windows chat's automation has moved automatically.

## 10. Exact policy for a Kubuntu AI-agent heartbeat

If the target AI app supports recurring work, configure a **30-minute check in the current project chat**, with this prompt, substituting the resolved project path. If it does not, keep the installed local monitor and document that chat notifications are not available; do not fabricate an app feature.

> Monitor the user's resumable loto history collection in the resolved Kubuntu project folder for August 18, 2007 through October 21, 2026. Read progress.json, PROGRESS.md, monitor-state.json, and the recent history.log. The collection is already finished in the migrated baseline; verify the restored database and exports before accepting migration, then remain quiet while unchanged. Track reported year completions and final results without resetting notification history. During any owner-authorized unfinished collection, stay quiet while it advances within a year or automatically retries an internet outage. Notify only on new year completions, full completion, sustained parsing problems, or failures needing attention. Report saved, flagged, cancelled, unavailable and review counts accurately; finished_with_issues is not clean. If an unfinished process exits unexpectedly, inspect its logs; repair a routine recoverable problem only after appropriate tests, then resume through the existing start tool. Respect STOP and intentional stopped states, preserve checkpoints and source HTML, never run duplicate workers, do not change the requested range, do not invent or silently correct published numbers, and never bypass source restrictions. After completion, verify complete date coverage and all exports and report unresolved source gaps once, then remain quiet on subsequent unchanged checks.

The Linux agent can perform recurring repair only while its app/runtime is available. The systemd collector handles network retry and process supervision independently of AI availability.

## 11. Maintenance without losing data

Stop the collector and verify it is no longer running before maintenance:

```bash
bash stop-history.sh
bash status-history.sh
```

To rebuild existing exports without network requests:

```bash
python3 history.py export --year 2026
```

To reparse review dates after a tested parser fix, using saved HTML:

```bash
python3 history.py retry-review --year 2011
bash start-history.sh
```

Do not run these commands merely to make the two known source gaps disappear. An incomplete source remains incomplete. Reclassification of an explicit cancelled-draw notice is valid only when the original source supports it.

The main SQLite file is local and ignored by Git because it is mutable. The repository includes a frozen compressed SQLite snapshot instead. For later owner-authorized checkpoint updates, stop the collector, create a consistent SQLite backup using Python's `sqlite3.Connection.backup`, verify it, compress it, and update the snapshot manifest together. Never copy only a running database while ignoring its WAL. Do not overwrite the migration baseline casually or push credentials, lock files, PIDs, local logs or tokens.

Only push to the confirmed private remote. There is no automatic data upload/sync process. One active computer should own a checkpoint; Git is not a mechanism for merging two simultaneously edited SQLite databases.

## 12. Testing and target acceptance checklist

The offline suite checks source preservation, cancelled/missing/wrong-date responses, historical anomalies, internet failure then recovery, restart without repeat downloads, cached-page recovery, year transitions, process locking, safe restore, quiet notifications and STOP. The repository also includes GitHub Actions tests on Ubuntu and Windows. Review the actual run result; do not infer that a workflow file means it passed.

The Kubuntu AI agent must report these results after running them on the target:

1. Actual OS, Python version and resolved clone path.
2. GitHub repository remains private and the intended account can clone it.
3. Restore completed or safely preserved an existing checkpoint.
4. Full verifier passes with the exact baseline totals in section 2.
5. All offline tests pass on Kubuntu, including a real second-process lock test using `fcntl.flock`.
6. Status is finished, 7,005/7,005, worker_running=false.
7. Starting the completed range downloads nothing and does not reset progress.
8. The same Markdown display opens and the viewer refreshes correctly.
9. Generated user units pass `systemd-analyze --user verify` on that machine and the monitor timer is installed if requested.
10. Monitoring remains quiet for the migrated completed archive; no duplicate completion notifications.
11. The two source gaps and all 95 flagged dates remain preserved and visible.
12. Any target-specific missing permission or environment limitation is stated precisely. Do not claim a full reboot/login test unless one was actually performed.

Use this extra unit check after installation:

```bash
systemd-analyze --user verify \
  "$HOME/.config/systemd/user/loto-history.service" \
  "$HOME/.config/systemd/user/loto-monitor.service" \
  "$HOME/.config/systemd/user/loto-monitor.timer"
```

## 13. Paste this into the Kubuntu AI agent

```text
Implement the existing loto project on this Kubuntu computer from the PRIVATE GitHub repository https://github.com/bendoantran/loto. Read AGENTS.md and KUBUNTU_AGENT_HANDOFF.md completely, then execute the migration and acceptance checklist. Use ~/Documents/xoso unless it conflicts with existing files. Preserve the exact scraper method, fixed date range, timeout/pacing/retry behavior, SQLite durability, cache/resume behavior, source preservation, data schemas, quality flags, yearly exports, PROGRESS.md/progress.json display, and quiet monitoring policy.

The full historical archive is already collected. Restore the bundled checkpoint and verify 7,005 checked dates, 21,592 province/date draws, and 388,656 winning-number appearances. Do not re-scrape 19 years, overwrite an existing checkpoint, extend the date range, make GitHub public, or invent missing numbers. Keep the 95 flagged dates, 133 cancelled draws, and two source-review gaps. Set up the supplied Kubuntu controls and systemd user supervision/30-minute monitor where supported; use the handoff's exact AI heartbeat policy if this app supports recurring checks. Keep the existing display, rather than designing a replacement.

Run the offline tests, full baseline verifier, duplicate-process lock check, no-download-on-completed-start check, unit-file validation, and quiet-monitor check. Use authorized existing GitHub authentication or let me complete browser authentication; never ask for a token in chat. Proceed with reversible setup work without repeatedly asking for permission. At the end, report what was actually installed, exact verification results, paths and start/status/stop commands, plus any remaining target-specific permission or environment limitation. Do not claim a reboot test or actual Kubuntu acceptance unless you performed it.
```

## Reference documentation

- [GitHub: create a repository and choose visibility](https://docs.github.com/en/repositories/creating-and-managing-repositories/creating-a-new-repository)
- [GitHub: regular Git file-size limits](https://docs.github.com/en/repositories/working-with-files/managing-large-files/about-large-files-on-github)
- [GitHub CLI authentication](https://cli.github.com/manual/gh_auth_login)
- [GitHub CLI Git credential setup](https://cli.github.com/manual/gh_auth_setup-git)
- [Python POSIX locking](https://docs.python.org/3/library/fcntl.html)
- [systemd service behavior](https://www.freedesktop.org/software/systemd/man/latest/systemd.service.html)

## 14. New owner-authorized XSMT implementation test

After the XSMN migration, the owner requested a separate miền Trung implementation exercise. Read **[XSMT_KUBUNTU_CHALLENGE.md](XSMT_KUBUNTU_CHALLENGE.md)** and use its ready-to-paste agent prompt, frozen source references, output graders, recovery tests and scoring checklist.

This adds a new region in separate data roots; it does not replace or extend the existing XSMN archive. Implement and test region support on Kubuntu before beginning full XSMT history. The current repository includes assessment tools and reference results, not a completed XSMT production collector.
