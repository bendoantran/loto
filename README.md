# loto — private lottery archive and resumable scraper

Private repository: **https://github.com/bendoantran/loto**.

**Training server, no sudo:** see [SERVER-START.md](SERVER-START.md). The server-ready branch includes the frozen completed XSMN/XSMT modeling snapshot in checksummed chunks. Clone `codex/past-only-prediction`, run `bash setup-server.sh`, then `./loto doctor --device cuda`. Setup downloads pinned Python/packages into this directory and starts no training.

This is the full completed Southern Vietnam lottery archive, together with the exact extraction method, a restorable checkpoint, and Windows/Kubuntu controls. Start with **[KUBUNTU_AGENT_HANDOFF.md](KUBUNTU_AGENT_HANDOFF.md)** for the detailed migration procedure and a ready-to-use AI-agent prompt.

**XSMT collection:** the collector now accepts `--region xsmt`, while XSMN remains the default. See [XSMT_RUNBOOK.md](XSMT_RUNBOOK.md) for separate roots, controls and supervision, and [XSMT_ACCEPTANCE_REPORT.md](XSMT_ACCEPTANCE_REPORT.md) for actual live benchmark and recovery evidence. [XSMT_KUBUNTU_CHALLENGE.md](XSMT_KUBUNTU_CHALLENGE.md) retains the original acceptance assignment and frozen assessment kit. Full historical XSMT collection is separately checkpointed and may still be running; the pilot is not proof of full-history completion.

**Prediction implementation:** [number_prediction/README.md](number_prediction/README.md) documents the isolated six-stage prediction pipeline, verified data snapshots, model families, chronological evaluation and portable CPU tools. [number_prediction/IMPLEMENTATION_PROGRESS.md](number_prediction/IMPLEMENTATION_PROGRESS.md) separates actual local pilot evidence from pending full server training, final-test scoring and Windows acceptance. The archive tooling remains standard-library-only.

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

XSMN numeric extraction and frozen archive assets are preserved. Region-aware source/heading guards, XSMT province-loto association, export recovery after a crash, and separate regional controls extend the collector. No third-party Python packages are needed.

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
| `PREDICTION_IMPLEMENTATION_PLAN.md` | Complete agreed prediction specification and original six stages |
| `PREDICTION_KUBUNTU_HANDOFF.md` | Kubuntu implementation setup, agent prompt, and reporting contract |

The live SQLite database, lock files, PIDs, credentials, and local logs are excluded from Git. The frozen checkpoint and all archive data are included. Do not change repository visibility to public or enable GitHub Pages.
