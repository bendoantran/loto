# XSMT collector

The collector now supports `--region xsmt`. XSMN remains the default. Legacy
checkpoints without a region key are XSMN; they are refused by XSMT commands.
All tools use only the Python standard library. The prediction plan remains a
separate, unimplemented project.

## Data roots on this computer

| Purpose | Absolute path |
|---|---|
| Original XSMN archive | `/home/ldoan4/Documents/Codex/2026-10-22/git/loto` |
| Live XSMT pilot | `/home/ldoan4/Documents/Codex/2026-10-22/git/work/xsmt-pilot` |
| Live year-boundary case | `/home/ldoan4/Documents/Codex/2026-10-22/git/work/xsmt-boundary` |
| Full XSMT collection | `/home/ldoan4/Documents/Codex/2026-10-22/git/work/xsmt` |
| Discovery and recovery evidence | `/home/ldoan4/Documents/Codex/2026-10-22/git/work/xsmt-evidence` |
| User-facing page scrape and reports | `/home/ldoan4/Documents/Codex/2026-10-22/git/outputs/xsmt` |

The full XSMT checkpoint freezes **2007-08-18 through 2026-10-22**, 7,006 dates.
Its `collection-manifest.json` records independent historical discovery and the
uncertainty about unsampled earlier dates. Thirteen live pages from discovery,
pilot and year-boundary runs were copied with their original hashes and mtimes
into the full raw cache, avoiding repeat downloads. The full run still processes
every calendar date in order and independently parses the cached source.

## Existing progress display and controls

Run from the clone. These commands always name the region and data root:

```bash
XSMT_ROOT=/home/ldoan4/Documents/Codex/2026-10-22/git/work/xsmt
python3 tools/control.py status --region xsmt --root "$XSMT_ROOT"
watch --interval 2 --no-title cat -- "$XSMT_ROOT/PROGRESS.md"
python3 tools/control.py request-stop --region xsmt --root "$XSMT_ROOT" --wait 30
```

The stop command creates a durable STOP marker. Do not delete locks or SQLite
files. The installed supervisor and monitor respect STOP. To explicitly resume
under the installed supervisor, after checking the saved state:

```bash
rm -f -- "$XSMT_ROOT/STOP"
systemctl --user start loto-xsmt-history.service
```

For a manually managed process instead of the installed supervisor:

```bash
python3 tools/control.py start --region xsmt --root "$XSMT_ROOT"
```

That start command explicitly clears STOP and refuses a second active worker.
For a fresh XSMT root it additionally requires both `--start` and `--end`.

## Supervision and quiet monitoring

Installed user units are `loto-xsmt-history.service`, `loto-xsmt-monitor.service`
and `loto-xsmt-monitor.timer`. Their files live in
`/home/ldoan4/.config/systemd/user/`. The collector uses Restart=on-failure with
60 seconds between supervisor retries; the monitor checks every 30 minutes.
It reports new year completions, final completion, sustained review increases
and failures needing attention. It stays quiet during normal daily progress,
connection retries, and unchanged completion. State and event history live in
the XSMT root, separate from XSMN.

```bash
systemctl --user status loto-xsmt-history.service --no-pager
systemctl --user list-timers loto-xsmt-monitor.timer --all
journalctl --user -u loto-xsmt-history.service -n 20 --no-pager
python3 tools/monitor.py --region xsmt --root "$XSMT_ROOT" --no-notify --no-restart
```

Keep the computer awake. This machine currently has `Linger=no`; the enabled
units resume with the user's session, and pre-login/after-logout operation has
not been enabled. No physical reboot was performed. Desktop popup delivery is
not verified; monitor events and the journal are the durable notification record.

## Verification and maintenance

Stop the collector and confirm `worker_running: false` before exporting or
performing a full consistent audit. Never reset a completed or interrupted root.

```bash
python3 history.py export --region xsmt --root "$XSMT_ROOT"
python3 tools/verify_archive.py --region xsmt --root "$XSMT_ROOT"
python3 -m unittest discover -p 'test_*.py' -v
python3 tools/check_xsmt_benchmark.py --root /home/ldoan4/Documents/Codex/2026-10-22/git/work/xsmt-pilot --case pilot
python3 tools/check_xsmt_benchmark.py --root /home/ldoan4/Documents/Codex/2026-10-22/git/work/xsmt-boundary --case year-boundary
```

To repeat fault injection, choose a **new empty evidence destination**:

```bash
python3 tools/prove_xsmt_recovery.py prove --root /path/to/new-evidence-root
```

These fault tests use frozen raw responses and a mocked retry clock. Separate
child processes really exit between raw save, checkpoint commit and export;
they do not perform a physical reboot or disconnect the owner's network.

The separate regional-page scraper preserves raw HTML first:

```bash
python3 tools/scrape_region.py --region xsmt --out /path/to/new-output
```

Do not combine the regional-page snapshot, pilot, boundary case and full archive
as independent observations. They overlap. The full checkpoint/yearly exports
are the canonical XSMT dataset. Import CSV number/loto columns as text to keep
leading zeros and repeated appearances.
