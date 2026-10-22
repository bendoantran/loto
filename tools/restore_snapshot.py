"""Restore the migrated SQLite checkpoint without overwriting existing work."""
import argparse
import gzip
import hashlib
import json
import os
import shutil
import sqlite3
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
import history


def verify_files(repo, manifest):
    for relative, expected in manifest["files"].items():
        path = (repo / relative).resolve()
        if not path.is_relative_to(repo.resolve()):
            raise ValueError("Unsafe path in snapshot manifest")
        if path.stat().st_size != expected["bytes"] or hashlib.sha256(path.read_bytes()).hexdigest() != expected["sha256"]:
            raise ValueError("Snapshot asset differs: " + relative)


def restore(repo, root):
    repo, root = Path(repo).resolve(), Path(root).resolve()
    root.mkdir(parents=True, exist_ok=True)
    manifest = json.loads((repo / "snapshots/manifest.json").read_text(encoding="utf-8"))
    destination = root / "history.sqlite3"
    with history.WorkerLock(root):
        if destination.exists():
            return {"state": "existing_checkpoint_preserved", "path": str(destination)}
        # Progress files can legitimately change after the first restore; only the
        # frozen DB's hash is needed to restore safely. Full asset verification is separate.
        compressed = (repo / "snapshots/history.sqlite3.gz").read_bytes()
        if hashlib.sha256(compressed).hexdigest() != manifest["database_gzip_sha256"]:
            raise ValueError("Compressed snapshot hash differs")
        raw = gzip.decompress(compressed)
        if hashlib.sha256(raw).hexdigest() != manifest["database_sha256"]:
            raise ValueError("Database snapshot hash differs")
        temporary = root / "history.restore.tmp"
        history.atomic_write(temporary, raw)
        db = sqlite3.connect(f"file:{temporary.as_posix()}?mode=ro&immutable=1", uri=True)
        try:
            if db.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise ValueError("Snapshot failed integrity check")
            settings = dict(db.execute("SELECT key,value FROM settings"))
            counts = dict(db.execute("SELECT status,COUNT(*) FROM days GROUP BY status"))
            if settings != {"start": manifest["start"], "end": manifest["end"]} or counts != manifest["status_counts"]:
                raise ValueError("Snapshot coverage differs from manifest")
        finally:
            db.close()
        os.replace(temporary, destination)
        for source, name in [(repo / "progress.json", "progress.json"), (repo / "PROGRESS.md", "PROGRESS.md"),
                             (repo / "snapshots/monitor-state.json", "monitor-state.json")]:
            if not (root / name).exists():
                shutil.copy2(source, root / name)
        result = {"state": "restored", "restored_at_utc": history.utcnow(),
                  "checked_dates": manifest["checked_dates"], "path": str(destination),
                  "database_sha256": manifest["database_sha256"]}
        history.atomic_write(root / "SNAPSHOT_RESTORED.json", json.dumps(result, indent=2))
        return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root", type=Path, default=REPO)
    p.add_argument("--verify-files", action="store_true", help="Check all frozen file hashes; use on a fresh clone")
    args = p.parse_args()
    if args.verify_files:
        verify_files(REPO, json.loads((REPO / "snapshots/manifest.json").read_text(encoding="utf-8")))
    print(json.dumps(restore(REPO, args.root), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
