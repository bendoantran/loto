"""Grade candidate XSMT exports against frozen source references; does not scrape."""
import argparse
import csv
import gzip
import hashlib
import json
import sqlite3
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DRAW_KEYS = ("date", "weekday", "province", "prizes", "loto_by_head", "derived_loto_by_head", "quality_flags")
CSV_FIELDS = ["date", "weekday", "province", "prize", "position", "number", "loto", "quality_flags", "source_url"]


def require(condition, message):
    if not condition:
        raise ValueError(message)


def check(root, case="pilot"):
    root = Path(root).resolve()
    reference = json.loads((REPO / "reference/xsmt/expected.json").read_text(encoding="utf-8"))
    expected = {day: record for day, record in reference["days"].items()
                if (day >= "2026-10-16") == (case == "pilot")}
    for day, record in expected.items():
        raw = gzip.decompress((REPO / record["raw_path"]).read_bytes())
        require(hashlib.sha256(raw).hexdigest() == record["raw_sha256"], "Frozen reference hash differs: " + day)
    p = json.loads((root / "progress.json").read_text(encoding="utf-8"))
    require(p["state"] == "finished", "Candidate must finish before grading")
    require(p["start"] == min(expected) and p["end"] == max(expected), "Wrong benchmark date range")
    require(p["processed_days"] == p["total_days"] == len(expected), "Wrong processed-date count")
    require(p["saved_days"] == len(expected) and p["flagged_days"] == p["unavailable_days"] == p["review_days"] == p.get("no_draw_days", 0) == 0,
            "Benchmark dates should all be saved cleanly")
    records = {}
    actual_csv = {}
    for year in sorted({day[:4] for day in expected}):
        folder = root / "years" / year
        for line in (folder / "results.jsonl").read_text(encoding="utf-8").splitlines():
            record = json.loads(line)
            day = record["date"]
            require(day not in records, "Duplicate JSON date: " + day)
            records[day] = record
        with (folder / "prizes.csv").open(encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            require(reader.fieldnames == CSV_FIELDS, "CSV schema differs from the existing export")
            for row in reader:
                key = (row["date"], row["province"], row["prize"], row["position"])
                require(key not in actual_csv, "Duplicate CSV numeric key")
                actual_csv[key] = row
    require(set(records) == set(expected), "Candidate has missing or extra dates")
    require(len(list((root / "years").glob("*/raw/*.html.gz"))) == len(expected), "Raw page count differs")
    expected_csv = {}
    for day, wanted in expected.items():
        record = records[day]
        require(record["status"] == "saved" and record["source_url"] == wanted["source_url"], "Wrong status or region URL: " + day)
        candidate = [{k: draw.get(k) for k in DRAW_KEYS} for draw in record["draws"]]
        require(candidate == wanted["draws"], "Prizes, province order, leading zeros, repeats, or loto differ: " + day)
        relative = f"years/{day[:4]}/raw/{day}.html.gz"
        require(record["raw_path"] == relative, "Unexpected raw path: " + day)
        digest = hashlib.sha256(gzip.decompress((root / relative).read_bytes())).hexdigest()
        require(digest == record["sha256"], "Candidate raw source hash differs: " + day)
        for draw in wanted["draws"]:
            for tier, numbers in draw["prizes"].items():
                for position, number in enumerate(numbers, 1):
                    key = (day, draw["province"], tier, str(position))
                    expected_csv[key] = dict(zip(CSV_FIELDS, [day, draw["weekday"], draw["province"], tier,
                                                               str(position), number, number[-2:], "", wanted["source_url"]]))
    require(actual_csv == expected_csv, "CSV differs from frozen reference values")
    db = sqlite3.connect(f"file:{(root / 'history.sqlite3').as_posix()}?mode=ro", uri=True)
    db.row_factory = sqlite3.Row
    try:
        require(db.execute("PRAGMA integrity_check").fetchone()[0] == "ok", "SQLite integrity check failed")
        settings = dict(db.execute("SELECT key,value FROM settings"))
        require(settings.get("region") == "xsmt", "Checkpoint must explicitly identify region=xsmt")
        days = {row["date"]: dict(row) for row in db.execute("SELECT * FROM days")}
        require(set(days) == set(expected), "SQLite date coverage differs")
        for day, row in days.items():
            wanted = expected[day]
            require(row["source_url"] == wanted["source_url"] and row["status"] == "saved", "Wrong checkpoint URL/status")
            require(row["draw_count"] == wanted["draw_count"] and row["number_count"] == wanted["number_count"], "Checkpoint counters differ")
            require(row["sha256"] == records[day]["sha256"], "SQLite and JSON source hashes differ")
            require(json.loads(row["payload"])["draws"] == records[day]["draws"], "SQLite and JSON numbers differ")
    finally:
        db.close()
    return {"case": case, "region": "xsmt", "passed": True, "dates": len(expected),
            "province_date_draws": sum(r["draw_count"] for r in expected.values()), "winning_numbers": len(actual_csv)}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root", type=Path, required=True)
    p.add_argument("--case", choices=["pilot", "year-boundary"], default="pilot")
    args = p.parse_args()
    print(json.dumps(check(args.root, args.case), indent=2))


if __name__ == "__main__":
    main()
