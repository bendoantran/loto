"""Verify transferred immutable files before setup; Python standard library only."""
import hashlib
import json
from pathlib import Path
import sys


def verify(root):
    root = Path(root).resolve()
    manifest = json.loads((root / "bundle-manifest.json").read_text(encoding="utf-8"))
    failures = []
    for name, expected in manifest["files"].items():
        path = root / name
        if not path.resolve().is_relative_to(root):
            failures.append(name + ": unsafe path")
            continue
        if "symlink" in expected:
            if not path.is_symlink() or str(path.readlink()) != expected["symlink"]:
                failures.append(name + ": symlink differs")
            continue
        try:
            digest = hashlib.sha256()
            with path.open("rb") as stream:
                for block in iter(lambda: stream.read(1024 * 1024), b""):
                    digest.update(block)
            if digest.hexdigest() != expected["sha256"]:
                failures.append(name + ": checksum differs")
        except OSError as error:
            failures.append(name + ": " + str(error))
    if failures:
        raise ValueError("Transfer verification failed:\n" + "\n".join(failures[:20]))
    return {"verified_files": len(manifest["files"]), "data_version": manifest["data_version"]}


if __name__ == "__main__":
    try:
        print(json.dumps(verify(Path(__file__).resolve().parent), indent=2))
    except (ValueError, OSError) as error:
        print(str(error), file=sys.stderr)
        raise SystemExit(2)
