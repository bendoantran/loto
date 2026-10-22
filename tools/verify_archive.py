"""Verify database, full date coverage, raw HTML hashes, and yearly numeric exports."""
import argparse
import csv
import gzip
import hashlib
import json
import sqlite3
import sys
from collections import Counter
from datetime import date, timedelta
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
import history


def verify(root, baseline=False):
    root = Path(root).resolve()
    if history.lock_held(root):
        raise ValueError("Stop the collector before performing a full consistent audit")
    db = sqlite3.connect(f"file:{(root / 'history.sqlite3').as_posix()}?mode=ro", uri=True)
    db.row_factory = sqlite3.Row
    try:
        if db.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise ValueError("Database integrity check failed")
        settings = dict(db.execute("SELECT key,value FROM settings"))
        first, last = date.fromisoformat(settings["start"]), date.fromisoformat(settings["end"])
        expected = {str(first + timedelta(days=i)) for i in range((last - first).days + 1)}
        rows = {row["date"]: dict(row) for row in db.execute("SELECT * FROM days")}
        if set(rows) != expected or any(r["status"] not in history.TERMINAL for r in rows.values()):
            raise ValueError("Incomplete date coverage")
        seen, years, draw_count, number_count = set(), [], 0, 0
        for year in range(first.year, last.year + 1):
            folder = root / "years" / str(year)
            records = [json.loads(line) for line in (folder / "results.jsonl").read_text(encoding="utf-8").splitlines()]
            expected_csv, local_dates = {}, set()
            for record in records:
                day = record["date"]
                if day in seen or int(day[:4]) != year or day not in rows:
                    raise ValueError("Duplicate or unexpected exported date: " + day)
                seen.add(day)
                local_dates.add(day)
                row = rows[day]
                if record["status"] != row["status"] or record["draws"] != json.loads(row["payload"])["draws"]:
                    raise ValueError("Database and JSON differ: " + day)
                raw_path = (root / record["raw_path"]).resolve()
                if not raw_path.is_relative_to(root):
                    raise ValueError("Unsafe raw HTML path")
                digest = hashlib.sha256(gzip.decompress(raw_path.read_bytes())).hexdigest()
                if digest != row["sha256"] or digest != record["sha256"]:
                    raise ValueError("Raw HTML hash differs: " + day)
                for draw in record["draws"]:
                    draw_count += 1
                    for tier, values in draw["prizes"].items():
                        for position, number in enumerate(values, 1):
                            key = (day, draw["province"], tier, str(position))
                            if key in expected_csv or not isinstance(number, str):
                                raise ValueError("Duplicate number key or non-string number")
                            expected_csv[key] = (number, number[-2:])
                            number_count += 1
                if row["draw_count"] != len(record["draws"]) or row["number_count"] != sum(len(ns) for d in record["draws"] for ns in d["prizes"].values()):
                    raise ValueError("Stored daily counters differ: " + day)
            observed = set()
            with (folder / "prizes.csv").open(encoding="utf-8-sig", newline="") as f:
                for record in csv.DictReader(f):
                    key = (record["date"], record["province"], record["prize"], record["position"])
                    if key in observed or expected_csv.get(key) != (record["number"], record["loto"]):
                        raise ValueError("CSV differs from JSON")
                    observed.add(key)
            if observed != set(expected_csv) or local_dates != {d for d in expected if int(d[:4]) == year}:
                raise ValueError("Yearly coverage or CSV rows differ")
            if len(list((folder / "raw").glob("*.gz"))) != len(local_dates):
                raise ValueError("Yearly raw HTML count differs")
            years.append({"year": year, "dates": len(records), "winning_numbers": len(observed)})
        if seen != expected:
            raise ValueError("Dates missing from yearly exports")
        counts = dict(Counter(row["status"] for row in rows.values()))
        if baseline:
            manifest = json.loads((REPO / "snapshots/manifest.json").read_text(encoding="utf-8"))
            actual = (settings["start"], settings["end"], len(rows), draw_count, number_count, counts)
            wanted = (manifest["start"], manifest["end"], manifest["checked_dates"], manifest["province_date_draws"], manifest["winning_numbers"], manifest["status_counts"])
            if actual != wanted:
                raise ValueError("Archive totals differ from the migration baseline")
        return {"verified_at_utc": history.utcnow(), "integrity": "ok", "start": settings["start"], "end": settings["end"],
                "checked_dates": len(rows), "province_date_draws": draw_count, "winning_numbers": number_count,
                "status_counts": counts, "years": years}
    finally:
        db.close()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root", type=Path, default=REPO)
    p.add_argument("--baseline", action="store_true")
    args = p.parse_args()
    report = verify(args.root, args.baseline)
    history.atomic_write(args.root / "verification-local.json", json.dumps(report, ensure_ascii=False, indent=2))
    print(json.dumps({k: v for k, v in report.items() if k != "years"}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
