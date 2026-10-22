# loto — private lottery archive and resumable scraper

Private repository: **https://github.com/bendoantran/loto**.

This is the full completed Southern Vietnam lottery archive, together with the exact extraction method, a restorable checkpoint, and Windows/Kubuntu controls. Start with **[KUBUNTU_AGENT_HANDOFF.md](KUBUNTU_AGENT_HANDOFF.md)** for the detailed migration procedure and a ready-to-use AI-agent prompt.

## Included archive

- Range: **August 18, 2007–October 21, 2026**, fixed unless the owner requests a change.
- **7,005 checked dates**, **21,592 province/date draws**, **388,656 winning-number appearances**.
- 6,775 clean dates; 95 dates saved with published inconsistencies flagged; 133 explicitly cancelled draws; 2 dates requiring review.
- Yearly CSV/JSONL exports and **all 7,005 original compressed HTML responses**.
- A consistent compressed SQLite checkpoint, with hashes and a restore command that never overwrites an existing database.

See [ARCHIVE_REPORT.md](ARCHIVE_REPORT.md) and [archive-audit.json](archive-audit.json) for the original final audit and source gaps.

## Kubuntu quick start

Authenticate to the private repository as an authorized GitHub user, then:

```bash
git clone --depth 1 https://github.com/bendoantran/loto.git "$HOME/Documents/xoso"
cd "$HOME/Documents/xoso"
python3 -c 'import sys; assert sys.version_info >= (3, 10), "Python 3.10+ is required"'
python3 tools/restore_snapshot.py --verify-files
python3 tools/verify_archive.py --baseline
python3 -m unittest discover -p 'test_*.py' -v
bash status-history.sh
```

The restored range is already finished. Starting it should say **nothing needs downloading**. Do not delete the checkpoint and scrape 19 years again just to migrate.

## Same progress display and controls

`PROGRESS.md` has the same year-by-year table as on Windows; `progress.json` is the same machine-readable display source.

```bash
bash watch-progress.sh     # live terminal view of the same Markdown table
bash start-history.sh      # detached collector, if any saved dates remain pending
bash status-history.sh
bash stop-history.sh       # durable STOP request
```

For supervised reboot/login resume and quiet 30-minute monitoring, follow the systemd section in the handoff. The migrated baseline monitor is already marked finished and remains quiet.

## What is preserved

One HTTP request at a time; ascending dates and years; 1.5-second rest after successful requests; 20-second HTTP timeout; network backoff of 5, 10, 20, 40, then 60 seconds; SQLite WAL/FULL commits after every date; cached HTML before parsing; no repeat downloads of committed dates; repeated numbers and leading zeros; all quality states and original notices; yearly export refresh every 10 dates and on year completion or graceful stop.

The parser is unchanged. Platform changes are limited to POSIX locking, graceful SIGTERM handling, and the additional migration/control/monitoring tools. No third-party Python packages are needed.

## Repository contents

| Path | Purpose |
|---|---|
| `history.py`, `scrape.py` | Historical collector and original single-page scraper |
| `years/YYYY/` | CSV, JSONL, issue records, and compressed original HTML |
| `snapshots/history.sqlite3.gz` | Immutable migration checkpoint |
| `snapshots/manifest.json` | Snapshot totals and per-file hashes |
| `tools/restore_snapshot.py` | Safe local checkpoint restore |
| `tools/verify_archive.py` | Full post-clone audit |
| `tools/control.py`, `*.sh` | Kubuntu process controls |
| `tools/install_service.py` | Generate systemd user service and monitor timer |
| `tools/monitor.py` | Quiet completion/failure notifications and progress record |
| `test_history.py`, `test_portability.py` | Offline regression tests |

The live SQLite database, lock files, PIDs, credentials, and local logs are excluded from Git. The frozen checkpoint and all archive data are included. Do not change repository visibility to public or enable GitHub Pages.
