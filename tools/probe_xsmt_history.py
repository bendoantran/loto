"""Preserve sequential, explicitly selected XSMT history-discovery probes."""
import argparse
import gzip
import hashlib
import json
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
import history


def probe(root, days):
    root.mkdir(parents=True, exist_ok=True)
    for day in sorted(set(days)):
        history.date.fromisoformat(day)
        raw_path, record_path = root / (day + '.html.gz'), root / (day + '.json')
        if record_path.exists():
            print(record_path.read_text(), flush=True)
            continue
        url = history.source_url(day, 'xsmt')
        fetched = history.utcnow()
        if raw_path.exists():
            raw = gzip.decompress(raw_path.read_bytes())
        else:
            raw = history.fetch(url, 20)
            if len(raw) > 5_000_000:
                raise ValueError('Source page exceeds 5 MB')
            fetched = history.utcnow()
            history.atomic_write(raw_path, gzip.compress(raw, mtime=0))
            time.sleep(1.5)
        try:
            result = history.parse_day(raw, day, 'xsmt')
        except (ValueError, UnicodeError, IndexError, KeyError) as error:
            result = {'status': 'review', 'draws': [], 'flags': [], 'error': str(error)}
        record = {'date': day, 'source_url': url, 'fetched_at_utc': fetched,
                  'sha256': hashlib.sha256(raw).hexdigest(),
                  'raw_path': str(raw_path), 'draw_count': len(result['draws']),
                  'number_count': sum(len(ns) for draw in result['draws'] for ns in draw['prizes'].values()), **result}
        history.atomic_write(record_path, json.dumps(record, ensure_ascii=False, indent=2))
        print(json.dumps({k:v for k,v in record.items() if k != 'draws'}, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root', type=Path, required=True)
    p.add_argument('--date', action='append', required=True)
    args = p.parse_args()
    probe(args.root.resolve(), args.date)
