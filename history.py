"""Resumable, one-request-at-a-time XSMN archive collector (Python 3 standard library)."""
import argparse
import csv
import gzip
import hashlib
import json
import logging
import os
import re
import signal
import sqlite3
import sys
import time
from collections import Counter
from contextlib import closing
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from scrape import EXPECTED, Tables
from regions import PROFILES, dated_heading, source_url, validate_checkpoint

DEFAULT_START = "2007-08-18"
DEFAULT_END = "2026-10-21"
TERMINAL = ("saved", "flagged", "unavailable", "review", "no_draw")
FIELDS = ["date", "weekday", "province", "prize", "position", "number", "loto", "quality_flags", "source_url"]


def utcnow():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def atomic_write(path, content):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("wb") as f:
        f.write(content if isinstance(content, bytes) else content.encode("utf-8"))
        f.flush()
        os.fsync(f.fileno())
    os.replace(temporary, path)


def json_text(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def parse_day(raw, day, region="xsmn"):
    """Preserve original numbers and flag discrepancies rather than correcting them."""
    text = raw.decode("utf-8-sig")
    parser = Tables()
    parser.feed(text)
    target = date.fromisoformat(day).strftime("%d/%m/%Y")
    cancellation = re.search(
        rf"Kết quả\s+(?:{PROFILES[region]['tokens']})\s+ngày\s+{re.escape(target)}\s+không mở thưởng[^<]*",
        text, re.IGNORECASE)
    if cancellation:
        return {"status": "no_draw", "draws": [], "flags": [],
                "note": " ".join(cancellation[0].split())}
    chosen = None
    for index, table in enumerate(parser.tables):
        if table["kind"] == "prizes" and dated_heading(table["heading"], day, region):
            chosen = index
            break
    if chosen is None:
        no_results = re.search(r'class\s*=\s*["\']?[^>]*block-no-result', text)
        notice = re.search(rf"Kết quả\s+(?:{PROFILES[region]['tokens']})\s+[^<>]{{0,50}}{re.escape(target)}\s+không được lưu trữ", text, re.I)
        if no_results and notice:
            return {"status": "unavailable", "draws": [], "flags": [],
                    "note": "Source explicitly says this date is not archived."}
        raise ValueError("Expected dated prize table or explicit not-archived notice was not found")
    rows = parser.tables[chosen]["rows"]
    if not rows or rows[0][0] != "Giải" or not 1 <= len(rows[0][1:]) <= 4:
        raise ValueError("Unrecognized province header")
    provinces = rows[0][1:]
    if len(set(provinces)) != len(provinces):
        raise ValueError("Duplicate province columns")
    draws = [{"date": day, "weekday": date.fromisoformat(day).strftime("%A"),
              "province": province, "prizes": {}, "loto_by_head": {},
              "derived_loto_by_head": {}, "quality_flags": []} for province in provinces]
    for row in rows[1:]:
        if not row:
            continue
        label = "G.ĐB" if row[0] == "ĐB" else row[0]
        if label not in EXPECTED or len(row) != len(draws) + 1:
            raise ValueError(f"Unrecognized prize row: {row}")
        count, width = EXPECTED[label]
        for draw, cell in zip(draws, row[1:]):
            if label in draw["prizes"]:
                raise ValueError(f"Duplicate prize tier {label}")
            numbers = cell.split()
            if not numbers or any(not re.fullmatch(r"\d{2,6}", n) for n in numbers):
                raise ValueError(f"Incomplete or nonnumeric prize {label}: {cell}")
            draw["prizes"][label] = numbers
            if len(numbers) != count:
                draw["quality_flags"].append(f"{label}: expected {count} numbers, source has {len(numbers)}")
            # Historical five-digit special prizes are preserved as a valid historical format.
            allowed_widths = {5, 6} if label == "G.ĐB" else {width}
            if any(len(n) not in allowed_widths for n in numbers):
                draw["quality_flags"].append(f"{label}: unexpected digit count in source")
    for draw in draws:
        if set(draw["prizes"]) != set(EXPECTED):
            raise ValueError("Missing prize tiers")
        heads = {str(i): [] for i in range(10)}
        for numbers in draw["prizes"].values():
            for number in numbers:
                heads[number[-2]].append(number[-2:])
        draw["derived_loto_by_head"] = heads
    loto_tables = []
    for table in parser.tables[chosen + 1:]:
        if table["kind"] == "prizes":
            break
        # Sidebar tables can reuse table-loto; only take the province tables.
        if table["kind"] == "loto" and len(loto_tables) < len(draws):
            if region == "xsmt":
                expected_province = draws[len(loto_tables)]["province"]
                if not re.fullmatch(rf"Loto\s+{re.escape(expected_province)}\s+.+,\s*{re.escape(target)}", table.get("caption", "")):
                    continue
            loto_tables.append(table)
    for index, draw in enumerate(draws):
        if index >= len(loto_tables):
            draw["quality_flags"].append("Source loto table missing")
            continue
        loto_rows = loto_tables[index]["rows"]
        heads = {}
        valid = len(loto_rows) == 11
        for i, row in enumerate(loto_rows[1:]):
            if i > 9 or len(row) != 2 or row[0] != str(i):
                valid = False
                break
            values = [] if row[1] in ("-", "") else [v.strip() for v in row[1].split(",")]
            if any(not re.fullmatch(rf"{i}\d", v) for v in values):
                valid = False
            heads[str(i)] = values
        draw["loto_by_head"] = heads
        if not valid:
            draw["quality_flags"].append("Source loto table has an unexpected format")
        elif Counter(n for ns in heads.values() for n in ns) != Counter(n for ns in draw["derived_loto_by_head"].values() for n in ns):
            draw["quality_flags"].append("Source loto table differs from prize endings")
    flags = [draw["province"] + ": " + flag for draw in draws for flag in draw["quality_flags"]]
    return {"status": "flagged" if flags else "saved", "draws": draws, "flags": flags}


def connect(root, start=None, end=None, region="xsmn"):
    root = Path(root)
    path = root / "history.sqlite3"
    if path.exists():
        # Read-only preflight must precede journal-mode changes and schema writes.
        with closing(sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)) as existing:
            validate_checkpoint(existing, region, start, end)
    elif region == "xsmt" and (not start or not end):
        raise ValueError("A new XSMT root requires explicit --start and --end dates")
    elif region not in PROFILES:
        raise ValueError("Unknown source region: " + region)
    root.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(root / "history.sqlite3", timeout=30)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA synchronous=FULL")
    db.executescript("""
      CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
      CREATE TABLE IF NOT EXISTS days (
        date TEXT PRIMARY KEY, year INTEGER NOT NULL, status TEXT NOT NULL DEFAULT 'pending',
        attempts INTEGER NOT NULL DEFAULT 0, fetched_at TEXT, updated_at TEXT,
        source_url TEXT NOT NULL, sha256 TEXT, raw_path TEXT, payload TEXT,
        draw_count INTEGER NOT NULL DEFAULT 0, number_count INTEGER NOT NULL DEFAULT 0,
        error TEXT, next_retry REAL NOT NULL DEFAULT 0
      );
    """)
    stored = dict(db.execute("SELECT key,value FROM settings"))
    if not stored:
        start, end = start or DEFAULT_START, end or DEFAULT_END
        first, last = date.fromisoformat(start), date.fromisoformat(end)
        if last < first:
            raise ValueError("End date precedes start date")
        db.executemany("INSERT INTO settings VALUES (?,?)", [("start", start), ("end", end)])
        if region == "xsmt":
            db.execute("INSERT INTO settings VALUES ('region','xsmt')")
        db.executemany("INSERT INTO days(date,year,source_url) VALUES (?,?,?)",
                       [(str(first + timedelta(days=i)), (first + timedelta(days=i)).year,
                         source_url(str(first + timedelta(days=i)), region)) for i in range((last - first).days + 1)])
        db.commit()
    return db


def summary(db, state="stopped", current=None, message=None):
    rows = db.execute("""SELECT year,COUNT(*) total,
      SUM(status='saved') saved,SUM(status='flagged') flagged,
      SUM(status='unavailable') unavailable,SUM(status='review') review,
      SUM(status='no_draw') no_draw,
      SUM(status IN ('pending','retry')) remaining,
      SUM(draw_count) draws,SUM(number_count) numbers
      FROM days GROUP BY year ORDER BY year""").fetchall()
    years = [dict(row) for row in rows]
    for item in years:
        item["processed"] = item["total"] - item["remaining"]
        item["state"] = "pending" if not item["processed"] else "in_progress" if item["remaining"] else "finished_with_issues" if item["review"] or item["unavailable"] or item["flagged"] else "complete"
    total = sum(y["total"] for y in years)
    processed = sum(y["processed"] for y in years)
    settings = dict(db.execute("SELECT key,value FROM settings"))
    return {**({"region": "xsmt"} if settings.get("region") == "xsmt" else {}),
            "updated_at_utc": utcnow(), "state": state, "current_date": current,
            "message": message, "start": settings["start"], "end": settings["end"],
            "total_days": total, "processed_days": processed,
            "percent": round(100 * processed / total, 2) if total else 0,
            "saved_days": sum(y["saved"] for y in years),
            "flagged_days": sum(y["flagged"] for y in years),
            "unavailable_days": sum(y["unavailable"] for y in years),
            "review_days": sum(y["review"] for y in years),
            "no_draw_days": sum(y["no_draw"] for y in years),
            "years": years}


def write_progress(root, db, state, current=None, message=None):
    p = summary(db, state, current, message)
    atomic_write(root / "progress.json", json.dumps(p, ensure_ascii=False, indent=2))
    lines = ["# loto archive progress", "", f"Updated (UTC): {p['updated_at_utc']}",
             f"State: **{state}**. Current date: **{current or 'none'}**.",
             f"Range: {p['start']} through {p['end']}.",
             f"Processed **{p['processed_days']:,} / {p['total_days']:,} days ({p['percent']}%)**.",
             "", message or "", "", "| Year | Processed | Clean | Flagged | No draw | Unavailable | Review | State |",
             "|---|---:|---:|---:|---:|---:|---:|---|"]
    for y in p["years"]:
        lines.append(f"| {y['year']} | {y['processed']}/{y['total']} | {y['saved']} | {y['flagged']} | {y['no_draw']} | {y['unavailable']} | {y['review']} | {y['state']} |")
    lines += ["", "Flagged = numbers saved exactly as published, with quality flags. No draw = the source explicitly states the requested draw did not take place. Unavailable = source explicitly has no archived result. Review = HTML saved but automatic parsing needs attention.",
              "", "Checkpoints are committed after every date. Existing saved dates are skipped on restart. Yearly exports refresh every 10 processed dates, on stop, and when a year finishes."]
    atomic_write(root / "PROGRESS.md", "\n".join(lines) + "\n")
    return p


def export_year(root, db, year, region="xsmn"):
    validate_checkpoint(db, region)
    folder = root / "years" / str(year)
    folder.mkdir(parents=True, exist_ok=True)
    json_path, csv_path, issue_path = folder / "results.jsonl", folder / "prizes.csv", folder / "issues.jsonl"
    try:
        with json_path.with_suffix(".jsonl.tmp").open("w", encoding="utf-8", newline="\n") as jf, csv_path.with_suffix(".csv.tmp").open("w", encoding="utf-8-sig", newline="") as cf, issue_path.with_suffix(".jsonl.tmp").open("w", encoding="utf-8", newline="\n") as issues:
            writer = csv.writer(cf)
            writer.writerow(FIELDS)
            for row in db.execute("SELECT * FROM days WHERE year=? AND status IN ('saved','flagged','unavailable','review','no_draw') ORDER BY date", (year,)):
                payload = json.loads(row["payload"]) if row["payload"] else {"draws": []}
                record = {"date": row["date"], "status": row["status"], "source_url": row["source_url"],
                          "fetched_at_utc": row["fetched_at"], "sha256": row["sha256"],
                          "raw_path": row["raw_path"], **payload}
                if region == "xsmt":
                    record["region"] = region
                jf.write(json_text(record) + "\n")
                if row["status"] in ("flagged", "unavailable", "review"):
                    issues.write(json_text({"date": row["date"], "status": row["status"],
                                            "flags": payload.get("flags", []), "error": row["error"],
                                            "source_url": row["source_url"]}) + "\n")
                for draw in payload.get("draws", []):
                    for tier, numbers in draw["prizes"].items():
                        for position, number in enumerate(numbers, 1):
                            writer.writerow([draw["date"], draw["weekday"], draw["province"], tier,
                                             position, number, number[-2:], "; ".join(draw["quality_flags"]), row["source_url"]])
        for path in (json_path, csv_path, issue_path):
            os.replace(path.with_suffix(path.suffix + ".tmp"), path)
    except BaseException:
        logging.exception("Year export interrupted; database remains the source of truth")
        raise


class WorkerLock:
    def __init__(self, root):
        self.root = root
        self.file = None

    def __enter__(self):
        self.file = (self.root / "worker.lock").open("a+b")
        try:
            if os.name == "nt":
                import msvcrt
                if os.fstat(self.file.fileno()).st_size == 0:
                    self.file.write(b"0")
                    self.file.flush()
                self.file.seek(0)
                msvcrt.locking(self.file.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            self.file.close()
            raise RuntimeError("A collector is already running for this project") from None
        return self

    def __exit__(self, *args):
        if os.name == "nt":
            import msvcrt
            self.file.seek(0)
            msvcrt.locking(self.file.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl
            fcntl.flock(self.file.fileno(), fcntl.LOCK_UN)
        self.file.close()


def lock_held(root):
    try:
        with WorkerLock(root):
            return False
    except RuntimeError:
        return True


def interruptible_wait(seconds, stop_file):
    until = time.monotonic() + seconds
    while time.monotonic() < until:
        if stop_file.exists():
            return False
        time.sleep(min(1, max(0, until - time.monotonic())))
    return not stop_file.exists()


def fetch(url, timeout):
    req = Request(url, headers={"User-Agent": "loto-history/1.0 (personal archival research)",
                               "Accept": "text/html"})
    with urlopen(req, timeout=timeout) as response:
        if response.status != 200:
            raise URLError(f"HTTP {response.status}")
        if "text/html" not in response.headers.get("Content-Type", "").lower():
            raise URLError("Unexpected response content type")
        return response.read(5_000_001)


def collect(root, db, interval=1.5, timeout=20, limit=None, region="xsmn"):
    validate_checkpoint(db, region)
    stop_file = root / "STOP"
    current_year = None
    processed = 0
    consecutive_errors = 0
    state, day, message = "stopped", None, None
    try:
        # Reconcile any commit that survived a crash before its export refresh,
        # including the last date of a previous calendar year, before advancing.
        if not stop_file.exists():
            for y in db.execute("SELECT DISTINCT year FROM days WHERE status IN ('saved','flagged','unavailable','review','no_draw') ORDER BY year"):
                export_year(root, db, y[0], region)
        while not stop_file.exists():
            row = db.execute("SELECT * FROM days WHERE status IN ('pending','retry') ORDER BY date LIMIT 1").fetchone()
            if row is None:
                state, message = "finished", "Every requested date has been checked. See yearly issue files for gaps or flagged records."
                break
            day = row["date"]
            year = row["year"]
            if current_year is not None and year != current_year:
                export_year(root, db, current_year, region)
                logging.info("YEAR FINISHED %s", current_year)
            current_year = year
            remaining_delay = row["next_retry"] - time.time()
            if remaining_delay > 0:
                state = "waiting_for_retry"
                write_progress(root, db, state, day, row["error"])
                if not interruptible_wait(min(60, remaining_delay), stop_file):
                    break
                continue
            state = "running"
            write_progress(root, db, state, day)
            raw_relative = Path("years") / str(year) / "raw" / (day + ".html.gz")
            raw_file = root / raw_relative
            cached = raw_file.exists()
            attempts = row["attempts"]
            if not cached:
                attempts += 1
                try:
                    raw = fetch(row["source_url"], timeout)
                    if len(raw) > 5_000_000:
                        raise URLError("Response exceeds the 5 MB page limit")
                except (HTTPError, URLError, TimeoutError, ConnectionError, OSError) as error:
                    consecutive_errors += 1
                    backoff = min(60, 5 * (2 ** min(consecutive_errors - 1, 4)))
                    # A rate-limit response gets at least one minute of rest.
                    if isinstance(error, HTTPError) and error.code in (403, 429):
                        backoff = 60
                    message = f"Download failed; retry in {backoff}s: {type(error).__name__}: {error}"
                    db.execute("UPDATE days SET status='retry',attempts=?,updated_at=?,error=?,next_retry=? WHERE date=?",
                               (attempts, utcnow(), message, time.time() + backoff, day))
                    db.commit()
                    logging.warning("%s %s", day, message)
                    write_progress(root, db, "waiting_for_connection_or_server", day, message)
                    continue
                fetched_at = utcnow()
                atomic_write(raw_file, gzip.compress(raw, mtime=0))
                logging.info("HTTP SAVED url=%s fetched_at=%s sha256=%s", row["source_url"], fetched_at, hashlib.sha256(raw).hexdigest())
            else:
                raw = gzip.decompress(raw_file.read_bytes())
                fetched_at = datetime.fromtimestamp(raw_file.stat().st_mtime, timezone.utc).isoformat(timespec="seconds")
            consecutive_errors = 0
            error = None
            try:
                payload = parse_day(raw, day, region)
            except (ValueError, UnicodeError, IndexError, KeyError) as parse_error:
                payload = {"status": "review", "draws": [], "flags": [], "error": str(parse_error)}
                error = str(parse_error)
            draws = payload["draws"]
            numbers = sum(len(ns) for draw in draws for ns in draw["prizes"].values())
            db.execute("""UPDATE days SET status=?,attempts=?,fetched_at=?,updated_at=?,sha256=?,
                       raw_path=?,payload=?,draw_count=?,number_count=?,error=?,next_retry=0 WHERE date=?""",
                       (payload["status"], attempts, fetched_at, utcnow(), hashlib.sha256(raw).hexdigest(),
                        raw_relative.as_posix(), json_text(payload), len(draws), numbers, error, day))
            db.commit()
            processed += 1
            logging.info("%s %s draws=%s numbers=%s flags=%s%s", day, payload["status"], len(draws), numbers,
                         len(payload["flags"]), " cached" if cached else "")
            write_progress(root, db, "running", day)
            if processed % 10 == 0:
                export_year(root, db, year, region)
            # Include the final successful request in the pacing contract.
            if not cached and not interruptible_wait(interval, stop_file):
                break
            if limit and processed >= limit:
                state, message = "stopped", f"Stopped after the requested {limit} dates; run again to resume."
                break
    except KeyboardInterrupt:
        state, message = "stopped", "Stopped by keyboard; saved dates will be skipped on resume."
    except BaseException as exc:
        state, message = "error", f"{type(exc).__name__}: {exc}"
        logging.exception("Collector stopped unexpectedly")
        raise
    finally:
        if current_year is not None:
            export_year(root, db, current_year, region)
        # Repair exports left behind by a crash after a committed previous year.
        for year_row in db.execute("SELECT DISTINCT year FROM days WHERE status IN ('saved','flagged','unavailable','review','no_draw') ORDER BY year"):
            if year_row[0] != current_year:
                export_year(root, db, year_row[0], region)
        if stop_file.exists():
            state, message = "stopped", "STOP requested; all committed dates are safe."
        write_progress(root, db, state, day, message)
        logging.info("WORKER %s %s", state, message or "")


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("command", choices=["run", "status", "export", "retry-review"])
    p.add_argument("--root", type=Path, default=Path(__file__).resolve().parent)
    p.add_argument("--region", choices=PROFILES, default="xsmn")
    p.add_argument("--start")
    p.add_argument("--end")
    p.add_argument("--year", type=int)
    p.add_argument("--limit", type=int)
    p.add_argument("--interval", type=float, default=1.5, help="Seconds of rest after each successful HTTP request")
    p.add_argument("--timeout", type=float, default=20)
    a = p.parse_args()
    if a.interval < 0 or a.timeout <= 0 or (a.limit is not None and a.limit <= 0):
        p.error("interval must be nonnegative; timeout and limit must be positive")
    root = a.root.resolve()
    root.mkdir(parents=True, exist_ok=True)
    if a.command == "status":
        if not (root / "history.sqlite3").exists():
            print(json.dumps({"state": "not_started", "worker_running": lock_held(root)}))
            return
        db = sqlite3.connect(f"file:{(root / 'history.sqlite3').as_posix()}?mode=ro", uri=True, timeout=30)
        db.row_factory = sqlite3.Row
        validate_checkpoint(db, a.region, a.start, a.end)
        progress_file = root / "progress.json"
        old = json.loads(progress_file.read_text(encoding="utf-8")) if progress_file.exists() else {}
        result = summary(db, old.get("state", "unknown"), old.get("current_date"), old.get("message"))
        result["worker_running"] = lock_held(root)
        if not result["worker_running"] and result["state"] not in ("finished", "stopped", "error"):
            result["state"] = "stopped_unexpectedly_resume_available"
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return
    with WorkerLock(root):
        db = connect(root, a.start, a.end, a.region)
        logging.basicConfig(filename=root / "history.log", encoding="utf-8", level=logging.INFO,
                            format="%(asctime)sZ %(levelname)s %(message)s")
        logging.Formatter.converter = time.gmtime
        if a.command == "run":
            if (root / "STOP").exists():
                raise SystemExit("STOP exists. Use the start script for your operating system to resume.")
            atomic_write(root / "worker.json", json_text({"pid": os.getpid(), "started_at_utc": utcnow(), "root": str(root)}))
            logging.info("WORKER START pid=%s range=%s", os.getpid(), dict(db.execute("SELECT key,value FROM settings")))
            def stop_on_signal(signum, frame):
                raise KeyboardInterrupt
            previous_handler = signal.signal(signal.SIGTERM, stop_on_signal)
            try:
                collect(root, db, a.interval, a.timeout, a.limit, a.region)
            finally:
                signal.signal(signal.SIGTERM, previous_handler)
        elif a.command == "retry-review":
            # Reparse saved HTML after a parser fix, without downloading it again.
            where = "status='review'" + (" AND year=?" if a.year else "")
            db.execute(f"UPDATE days SET status='pending',next_retry=0 WHERE {where}", (a.year,) if a.year else ())
            db.commit()
            write_progress(root, db, "stopped", message="Review dates queued for reprocessing from their cached HTML.")
        else:
            years = [a.year] if a.year else [r[0] for r in db.execute("SELECT DISTINCT year FROM days ORDER BY year")]
            for year in years:
                export_year(root, db, year, a.region)
        db.close()


if __name__ == "__main__":
    main()
