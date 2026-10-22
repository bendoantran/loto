# Resumable lottery history

Collects August 18, 2007 through October 21, 2026: 7,005 dates, in order, one calendar year at a time. The first and last years cover only the requested portions. This date range is saved in the database and does not move automatically.

## Start, check and stop

Open PowerShell in `C:\Users\bendo\Documents\xoso`:

```powershell
.\start-history.ps1
.\status-history.ps1
.\stop-history.ps1
```

The start command launches a hidden local Python process. Starting it again while it is already running does not launch a second collector. The stop command requests a graceful stop; it allows an active HTTP request to finish or time out before stopping. To resume after stopping, a restart, or a reboot, run `start-history.ps1` again. It removes the stop request and resumes the saved checkpoint.

If PowerShell policy blocks these scripts, use these commands in an existing terminal:

```powershell
python history.py run
python history.py status
```

For the foreground run, press Ctrl+C to stop. If the `STOP` file exists from a previous stop request, remove that one file before running `python history.py run`.

## Internet interruptions

The collector retries failed downloads after 5, 10, 20, 40 and then 60 seconds, staying at a maximum one-minute retry interval. Completed dates are committed to SQLite immediately and are skipped when restarting. Downloaded HTML is saved before parsing, so a restart can reuse a page downloaded just before an interruption. Requests have a 20-second timeout, and the collector rests for 1.5 seconds after each successful network request.

The computer must remain on and awake for collection to progress. Switching the internet off does not erase progress. Reconnecting lets a running collector continue automatically. After a computer restart, manually run the start script again.

## Files

- `PROGRESS.md`: live, readable overview with a row for every year.
- `progress.json`: the same progress in a machine-readable form, updated after every date and when retrying a failed request.
- `history.sqlite3`: durable checkpoint and source of truth; journal mode WAL and full synchronous commits are enabled. Do not edit it while collecting.
- `history.log`: timestamped download/retry/year-completion events in UTC.
- `years/YYYY/raw/YYYY-MM-DD.html.gz`: compressed original responses.
- `years/YYYY/results.jsonl`: one record per checked date, including source URL, timestamp, original province/prize numbers, source loto tables, derived loto tables and quality flags.
- `years/YYYY/prizes.csv`: one row per winning number; import number/loto columns as Text to preserve leading zeros.
- `years/YYYY/issues.jsonl`: flagged, unavailable or unparsed dates for review.

Yearly exports refresh every 10 newly processed dates, when a year finishes, and on a graceful stop. SQLite and the progress files update after every date. A forced termination can leave exports behind the database; resuming or running `python history.py export` rebuilds them without downloading anything again.

## Progress and quality

Every requested date has one of these states:

| State | Meaning |
|---|---|
| pending/retry | Still needs a successful download; connection failures remain in this state |
| saved | Numeric data saved and source loto matches prize endings |
| flagged | Numeric data saved exactly as published, with source discrepancies identified |
| no_draw | The source explicitly says the requested date's draw did not take place; its notice is retained |
| unavailable | The website explicitly states it has no archived result for that date |
| review | Original HTML saved; parsing could not safely interpret the expected dated results |

“Processed” includes flagged, cancelled-draw, unavailable and review dates; it is a coverage count, not a claim that every date has complete clean data. Cancelled draws are counted separately and do not represent missing winning numbers. Year completion distinguishes clean completion from completion with issues. Missing archive dates and unknown layouts are not silently counted as clean results.

Historical special prizes can contain five digits; these remain unchanged. Other unusual number widths, counts, or discrepancies with the source loto table are flagged rather than fixed or invented. Additional sidebar tables are excluded.

After a parser fix, `python history.py retry-review --year 2007` queues that year's unparsed dates for reprocessing from cached HTML. Start the collector again afterward. This command leaves already saved data untouched. Use `python history.py export --year 2007` to rebuild just one year's exports while the collector is stopped.

The original single-page `scrape.py` and its `data/` snapshot remain separate from the historical collector.

## Validation performed

The offline suite covers modern leading zeros and repeats, historical anomalies, explicit unavailable and cancelled dates, wrong-date responses, interrupted connections and reconnection, stopping during an outage, restarting without duplicate downloads, reusing cached HTML after a crash, year boundaries, exclusive worker locking, and preserving unknown layouts for review.

```powershell
python -m unittest discover -p test_history.py -v
```
