"""Preserve and extract the actual regional page with explicit region guards."""
import argparse
import csv
import hashlib
import json
import re
import sys
import time
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
import history
from scrape import Tables


def scrape(region, out):
    source = history.PROFILES[region]["page"]
    raw = history.fetch(source, 20)
    if len(raw) > 5_000_000:
        raise ValueError("Response exceeds the 5 MB page limit")
    fetched = history.utcnow()
    history.atomic_write(out / "source.html", raw)  # Preserve before parsing.
    time.sleep(1.5)
    parser = Tables()
    parser.feed(raw.decode("utf-8-sig"))
    dates = set()
    for table in parser.tables:
        if table["kind"] != "prizes":
            continue
        match = re.search(r"\b\d{2}/\d{2}/\d{4}\b", table["heading"])
        if match:
            day = datetime.strptime(match[0], "%d/%m/%Y").date().isoformat()
            if history.dated_heading(table["heading"], day, region):
                dates.add(day)
    if not dates:
        raise ValueError("No dated results for the requested region; raw response preserved")
    records = []
    for day in sorted(dates):
        try:
            record = history.parse_day(raw, day, region)
        except (ValueError, UnicodeError, IndexError, KeyError) as error:
            record = {"status": "review", "draws": [], "flags": [], "error": str(error)}
        records.append({"date": day, **record})
    draws = [draw for record in records for draw in record["draws"]]
    result = {"region": region, "source_url": source, "fetched_at_utc": fetched,
              "source_sha256": hashlib.sha256(raw).hexdigest(),
              "date_range": [min(dates), max(dates)], "checked_dates": len(dates),
              "draw_count": len(draws),
              "number_count": sum(len(ns) for draw in draws for ns in draw["prizes"].values()),
              "records": records}
    history.atomic_write(out / "results.json", json.dumps(result, ensure_ascii=False, indent=2))
    with (out / "prizes.csv").open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(history.FIELDS)
        for draw in draws:
            for tier, numbers in draw["prizes"].items():
                for position, number in enumerate(numbers, 1):
                    writer.writerow([draw["date"], draw["weekday"], draw["province"], tier,
                                     position, number, number[-2:], "; ".join(draw["quality_flags"]), source])
    return {k: v for k, v in result.items() if k != "records"}


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--region", choices=history.PROFILES, required=True)
    p.add_argument("--out", type=Path, required=True)
    args = p.parse_args()
    print(json.dumps(scrape(args.region, args.out.resolve()), ensure_ascii=False, indent=2))
