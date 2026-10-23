"""Extract the visible XSMN draw tables; Python 3, no external dependencies."""
import argparse
import csv
import hashlib
import json
import re
from collections import Counter
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.request import Request, urlopen

SOURCE = "https://xosodaiphat.com/xsmn-xo-so-mien-nam.html"
EXPECTED = {"G.8": (1, 2), "G.7": (1, 3), "G.6": (3, 4),
            "G.5": (1, 4), "G.4": (7, 5), "G.3": (2, 5),
            "G.2": (1, 5), "G.1": (1, 5), "G.ĐB": (1, 6)}


class Tables(HTMLParser):
    """Handle the source's intentionally omitted td/tr closing tags."""
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tables = []
        self.table = self.row = self.cell = None
        self.heading = ""
        self.h2 = None
        self.paragraph = []

    def close_cell(self):
        if self.cell is not None and self.row is not None:
            self.row.append(" ".join("".join(self.cell).split()))
        self.cell = None

    def close_row(self):
        self.close_cell()
        if self.row is not None and self.table is not None:
            self.table["rows"].append(self.row)
        self.row = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "p" and self.table is None:
            self.paragraph = []
        if tag == "h2":
            self.h2 = []
        if tag == "table":
            classes = attrs.get("class", "").split()
            kind = "prizes" if "table-xsmn" in classes else "loto" if "table-loto" in classes else None
            if kind:
                self.table = {"kind": kind, "heading": self.heading, "rows": [],
                              "caption": " ".join("".join(self.paragraph).split())}
                self.paragraph = []
        elif self.table is not None:
            if tag == "tr":
                self.close_row()
                self.row = []
            elif tag in ("td", "th"):
                self.close_cell()
                self.cell = []
            elif tag == "br" and self.cell is not None:
                self.cell.append(" ")

    def handle_endtag(self, tag):
        if tag == "h2" and self.h2 is not None:
            self.heading = " ".join("".join(self.h2).split())
            self.h2 = None
        if self.table is not None:
            if tag in ("td", "th"):
                self.close_cell()
            elif tag == "tr":
                self.close_row()
            elif tag == "table":
                self.close_row()
                self.tables.append(self.table)
                self.table = None

    def handle_data(self, data):
        if self.table is None:
            self.paragraph.append(data)
        if self.h2 is not None:
            self.h2.append(data)
        if self.cell is not None:
            self.cell.append(data)


def extract(raw):
    parser = Tables()
    parser.feed(raw.decode("utf-8"))
    draws, current, loto_index = [], [], 0
    for table in parser.tables:
        rows = table["rows"]
        if table["kind"] == "prizes":
            if current and loto_index != len(current):
                raise ValueError("Missing source loto tables")
            match = re.search(r"\b(\d{2}/\d{2}/\d{4})\b", table["heading"])
            if not match or not rows or rows[0][0] != "Giải":
                raise ValueError("Draw heading or province header changed")
            date = datetime.strptime(match[1], "%d/%m/%Y")
            current = [{"date": date.date().isoformat(), "weekday": date.strftime("%A"),
                        "province": province, "prizes": {}, "loto_by_head": {}}
                       for province in rows[0][1:]]
            loto_index = 0
            for row in rows[1:]:
                label = "G.ĐB" if row[0] == "ĐB" else row[0]
                if label not in EXPECTED or len(row) != len(current) + 1:
                    raise ValueError(f"Unexpected prize row: {row}")
                count, width = EXPECTED[label]
                for draw, cell in zip(current, row[1:]):
                    numbers = cell.split()
                    if len(numbers) != count or any(not re.fullmatch(rf"\d{{{width}}}", n) for n in numbers):
                        raise ValueError(f"Incomplete/invalid {draw['province']} {label}: {cell}")
                    if label in draw["prizes"]:
                        raise ValueError(f"Duplicate prize tier: {label}")
                    draw["prizes"][label] = numbers
            for draw in current:
                if set(draw["prizes"]) != set(EXPECTED):
                    raise ValueError("Missing prize tiers")
            draws.extend(current)
        elif current:
            if loto_index >= len(current) or len(rows) != 11:
                raise ValueError("Unexpected loto table count or shape")
            draw = current[loto_index]
            heads = {}
            for i, row in enumerate(rows[1:]):
                if len(row) != 2 or row[0] != str(i):
                    raise ValueError("Invalid loto head row")
                values = [] if row[1] == "-" else [v.strip() for v in row[1].split(",")]
                if any(not re.fullmatch(rf"{i}\d", v) for v in values):
                    raise ValueError("Invalid loto values")
                heads[str(i)] = values
            expected = Counter(n[-2:] for ns in draw["prizes"].values() for n in ns)
            observed = Counter(n for ns in heads.values() for n in ns)
            if expected != observed:
                raise ValueError(f"Loto differs from prize endings: {draw['date']} {draw['province']}")
            draw["loto_by_head"] = heads
            loto_index += 1
    if not draws or loto_index != len(current):
        raise ValueError("No complete draws found")
    keys = [(d["date"], d["province"]) for d in draws]
    if len(keys) != len(set(keys)):
        raise ValueError("Duplicate province/date")
    return draws


def main():
    args = argparse.ArgumentParser(description=__doc__)
    args.add_argument("--html", type=Path, help="Parse an existing HTML snapshot offline")
    args.add_argument("--out", type=Path, default=Path(__file__).parent / "data")
    opts = args.parse_args()
    if opts.html:
        raw = opts.html.read_bytes()
        fetched_at = datetime.fromtimestamp(opts.html.stat().st_mtime, timezone.utc).isoformat()
    else:
        req = Request(SOURCE, headers={"User-Agent": "loto-research/1.0"})
        with urlopen(req, timeout=30) as response:
            raw = response.read()
        fetched_at = datetime.now(timezone.utc).isoformat()
    draws = extract(raw)  # Validate everything before writing output.
    dates = sorted({d["date"] for d in draws})
    payload = {"project": "loto", "source_url": SOURCE, "fetched_at_utc": fetched_at,
               "source_sha256": hashlib.sha256(raw).hexdigest(),
               "date_range": [dates[0], dates[-1]], "draw_count": len(draws),
               "number_count": sum(len(ns) for d in draws for ns in d["prizes"].values()),
               "validation": "All prize widths/counts and all source loto tables match; duplicates retained.",
               "draws": draws}
    opts.out.mkdir(parents=True, exist_ok=True)
    (opts.out / "source.html").write_bytes(raw)
    (opts.out / "results.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    with (opts.out / "prizes.csv").open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["date", "weekday", "province", "prize", "position", "number", "loto", "source_url"])
        for d in draws:
            for tier, numbers in d["prizes"].items():
                for position, number in enumerate(numbers, 1):
                    writer.writerow([d["date"], d["weekday"], d["province"], tier, position, number, number[-2:], SOURCE])
    print(json.dumps({k: v for k, v in payload.items() if k != "draws"}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
