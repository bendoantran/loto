"""Read-only import; immutable snapshots never share mutable collector files."""
import csv
import gzip
import hashlib
import io
import json
import re
import sqlite3
from collections import Counter
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

ORIGIN = date(2007, 8, 18)
PRIZES = ("G.8", "G.ĐB")
FIELDS = {"date", "weekday", "province", "prize", "position", "number", "loto", "quality_flags", "source_url"}


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def digest(data):
    return hashlib.sha256(data).hexdigest()


def day_index(value):
    n = (date.fromisoformat(value) - ORIGIN).days + 1
    if n < 1:
        raise ValueError("Date precedes the fixed calendar origin")
    return n


def normalize_prize(value):
    return re.sub(r"\s+", "", value).replace("G.DB", "G.ĐB")


def valid_source(url, region, day):
    parts = urlsplit(url)
    expected = f"/{region}-" + date.fromisoformat(day).strftime("%d-%m-%Y") + ".html"
    return parts.scheme == "https" and parts.netloc == "xosodaiphat.com" and parts.path == expected and not parts.query


def validate_row(row, region, allow_missing_flags=False):
    required = FIELDS - ({"quality_flags"} if allow_missing_flags else set())
    if not required <= row.keys() or region not in ("xsmn", "xsmt"):
        raise ValueError("Incompatible schema or untrusted region")
    day = date.fromisoformat(row["date"])
    day_index(row["date"])
    if row["weekday"] != day.strftime("%A") or not valid_source(row["source_url"], region, row["date"]):
        raise ValueError("Weekday or source region/date mismatch")
    if not row["province"].strip() or not row["position"].isascii() or not row["position"].isdigit():
        raise ValueError("Invalid province/position")
    number, ending = row["number"], row["loto"]
    if not (number.isascii() and number.isdigit() and ending.isascii() and ending.isdigit()
            and len(ending) == 2 and number[-2:] == ending):
        raise ValueError("Invalid number/ending; never coerce, pad or guess source values")
    prize = normalize_prize(row["prize"])
    if prize == "G.8" and len(number) != 2:
        raise ValueError("G.8 must contain two source digits")
    return {**row, "region": region, "prize": prize, "day_index": day_index(row["date"])}


def eligibility(row, status):
    """Allow documented unrelated tier anomalies; exclude target and unknown issues."""
    if status not in ("saved", "flagged"):
        return False, "date_" + status
    flags = row.get("quality_flags", "")
    if not flags:
        return True, "validated_target"
    unrelated = []
    for flag in flags.split("; "):
        tier = normalize_prize(flag.split(":", 1)[0])
        if tier == row["prize"] or tier not in {"G.8", "G.7", "G.6", "G.5", "G.4", "G.3", "G.2", "G.1", "G.ĐB"}:
            return False, "target_or_unresolved_quality"
        unrelated.append(flag)
    return True, "validated_target_unrelated_tier_flags"


def read_external(path, columns=None, missing_flags=False):
    """Explicit CSV/Excel adapter; caller supplies trusted region and provenance."""
    path = Path(path)
    if path.suffix.lower() == ".csv":
        with path.open(encoding="utf-8-sig", newline="") as stream:
            records = list(csv.DictReader(stream))
    elif path.suffix.lower() == ".xlsx":
        from openpyxl import load_workbook
        book = load_workbook(path, read_only=True, data_only=True)
        rows = iter(book.active.values)
        header = next(rows)
        records = []
        for values in rows:
            # Numeric cells can already have lost leading zeros: reject them.
            records.append(dict(zip(header, values)))
        book.close()
    else:
        raise ValueError("Supported external inputs: .csv and .xlsx")
    mapped = [{(columns or {}).get(k, k): v for k, v in row.items()} for row in records]
    for row in mapped:
        if not isinstance(row.get("number"), str) or not isinstance(row.get("loto"), str):
            raise ValueError("Number and loto cells must be text, including in Excel")
        if missing_flags:
            row.setdefault("quality_flags", "")
    return mapped


def capture_source(root, region):
    """Verify stable CSV/JSON pairs and raw evidence without locking an active writer."""
    root = Path(root).resolve()
    db = sqlite3.connect((root / "history.sqlite3").as_uri() + "?mode=ro", uri=True)
    try:
        settings = dict(db.execute("SELECT key,value FROM settings"))
    finally:
        db.close()
    if settings.get("region", "xsmn") != region:
        raise ValueError("Checkpoint region mismatch")
    files, records, decisions, counts = {}, [], [], Counter()
    for folder in sorted((root / "years").glob("[0-9][0-9][0-9][0-9]")):
        csv_path, json_path = folder / "prizes.csv", folder / "results.jsonl"
        if not csv_path.exists() or not json_path.exists():
            continue
        for attempt in range(4):
            csv_bytes, json_bytes = csv_path.read_bytes(), json_path.read_bytes()
            exported = [json.loads(line) for line in json_bytes.decode().splitlines() if line]
            expected, days = {}, {}
            for rec in exported:
                day = rec["date"]
                if day in days or not valid_source(rec["source_url"], region, day):
                    raise ValueError("Duplicate date or wrong JSON source")
                if not settings["start"] <= day <= settings["end"] or day[:4] != folder.name:
                    raise ValueError("Export outside checkpoint/year range")
                raw_path = (root / rec["raw_path"]).resolve()
                if not raw_path.is_relative_to(root) or digest(gzip.decompress(raw_path.read_bytes())) != rec["sha256"]:
                    raise ValueError("Raw evidence missing, unsafe or hash mismatch")
                days[day] = rec
                for draw in rec["draws"]:
                    for tier, numbers in draw["prizes"].items():
                        for pos, number in enumerate(numbers, 1):
                            key = (day, draw["province"], tier, str(pos))
                            if key in expected:
                                raise ValueError("Duplicate JSON number key")
                            expected[key] = (number, number[-2:], "; ".join(draw["quality_flags"]))
            rows = list(csv.DictReader(io.StringIO(csv_bytes.decode("utf-8-sig"))))
            actual = {}
            for row in rows:
                key = tuple(row[k] for k in ("date", "province", "prize", "position"))
                if key in actual:
                    raise ValueError("Duplicate CSV key")
                actual[key] = tuple(row[k] for k in ("number", "loto", "quality_flags"))
            stable = csv_bytes == csv_path.read_bytes() and json_bytes == json_path.read_bytes()
            if stable and actual == expected:
                break
        else:
            raise ValueError("Collector exports changed or disagree; retry after its next export")
        for path, content in ((csv_path, csv_bytes), (json_path, json_bytes)):
            files[str(path.relative_to(root))] = content
        counts.update(rec["status"] for rec in exported)
        for row in rows:
            if normalize_prize(row["prize"]) not in PRIZES:
                continue
            try:
                normalized = validate_row(row, region)
                accepted, reason = eligibility(normalized, days[row["date"]]["status"])
                if row["position"] != "1":
                    accepted, reason = False, "multiple_target_positions"
            except ValueError as error:
                normalized, accepted, reason = None, False, str(error)
            decisions.append({"region": region, **row, "accepted": accepted, "reason": reason})
            if accepted:
                records.append({**normalized, "eligibility": reason,
                                "raw_sha256": days[row["date"]]["sha256"]})
    return records, decisions, files, {"region": region, "root": str(root), "settings": settings,
        "exported_date_states": dict(counts), "exported_dates": sum(counts.values()),
        "complete_export_coverage": sum(counts.values()) == (date.fromisoformat(settings["end"]) - date.fromisoformat(settings["start"])).days + 1}


def deduplicate(records):
    seen = {}
    for row in records:
        key = tuple(row[k] for k in ("region", "province", "date", "prize"))
        if key in seen and (seen[key]["number"], seen[key]["loto"]) != (row["number"], row["loto"]):
            raise ValueError("Conflicting observations: " + str(key))
        seen.setdefault(key, row)
    return sorted(seen.values(), key=lambda r: (r["date"], r["region"], r["province"], r["prize"]))


def make_snapshot(sources, destination):
    destination = Path(destination)
    # mkdir(exist_ok=False) makes overwrite of experiment inputs impossible.
    destination.mkdir(parents=True, exist_ok=False)
    records, decisions, manifests = [], [], []
    try:
        for source in sources:
            rs, ds, files, meta = capture_source(source["root"], source["region"])
            meta["files"] = {name: digest(content) for name, content in files.items()}
            prefix = destination / "sources" / source["region"]
            if prefix.exists():
                raise ValueError("Exactly one canonical root per region is permitted")
            for name, content in files.items():
                target = prefix / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(content)
            records.extend(rs)
            decisions.extend(ds)
            manifests.append(meta)
        records = deduplicate(records)
        payload = b"".join(canonical(row) + b"\n" for row in records)
        (destination / "records.jsonl").write_bytes(payload)
        (destination / "eligibility.jsonl").write_bytes(b"".join(canonical(row) + b"\n" for row in decisions))
        coverage = {}
        for row in records:
            key = "|".join(row[k] for k in ("region", "province", "prize"))
            item = coverage.setdefault(key, {"count": 0, "first": row["date"], "last": row["date"]})
            item["count"] += 1
            item["last"] = row["date"]
        manifest = {"schema": 1, "created_at": datetime.now(timezone.utc).isoformat(),
            "origin": str(ORIGIN), "quality_policy": "target_validated_unrelated_tier_flags_allowed_v1",
            "same_date_policy": "withhold_both_regions", "records_sha256": digest(payload),
            "eligibility_sha256": digest((destination / "eligibility.jsonl").read_bytes()),
            "sources": manifests, "rows": len(records), "decisions": dict(Counter(d["reason"] for d in decisions)),
            "coverage": coverage, "identities": sorted({(r["region"], r["province"]) for r in records})}
        manifest["data_version"] = digest(canonical(manifest))
        (destination / "manifest.json").write_bytes(canonical(manifest))
        return manifest
    except Exception:
        # Preserve failed capture evidence, never advertise a valid manifest.
        (destination / "FAILED").write_text("Capture failed; choose a new destination after resolving the error.\n")
        raise


def load_snapshot(root):
    root = Path(root)
    manifest = json.loads((root / "manifest.json").read_text())
    version = manifest.pop("data_version")
    if version != digest(canonical(manifest)):
        raise ValueError("Snapshot manifest changed")
    manifest["data_version"] = version
    raw = (root / "records.jsonl").read_bytes()
    if digest(raw) != manifest["records_sha256"]:
        raise ValueError("Snapshot records changed")
    return [json.loads(line) for line in raw.splitlines()], manifest


def observations(records):
    """One draw with independent prize masks; missing is None, never class 00."""
    grouped = {}
    for row in deduplicate(records):
        key = tuple(row[k] for k in ("date", "region", "province"))
        item = grouped.setdefault(key, {"date": key[0], "region": key[1], "province": key[2],
                                       "G.8": None, "G.ĐB": None})
        item[row["prize"]] = int(row["loto"])
    return sorted(grouped.values(), key=lambda r: (r["date"], r["region"], r["province"]))
