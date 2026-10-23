"""Restore the checksummed private modeling snapshot from Git-tracked chunks; no scraping."""
import hashlib
import json
from pathlib import Path
import sys
import tarfile
import tempfile


def restore(manifest_path, destination):
    manifest_path, destination = Path(manifest_path), Path(destination)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    def verify():
        for name, expected in manifest["files"].items():
            path = (destination / name).resolve()
            if not path.is_relative_to(destination.resolve()):
                raise ValueError("Unsafe transfer path")
            with path.open("rb") as stream:
                if hashlib.file_digest(stream, "sha256").hexdigest() != expected:
                    raise ValueError("Restored snapshot changed: " + name)
    if destination.exists():
        verify()
        return manifest
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryFile(dir=destination.parent) as archive:
        digest = hashlib.sha256()
        for part in manifest["parts"]:
            path = (manifest_path.parent / part["name"]).resolve()
            if path.parent != manifest_path.parent.resolve():
                raise ValueError("Unsafe chunk path")
            content = path.read_bytes()
            if hashlib.sha256(content).hexdigest() != part["sha256"]:
                raise ValueError("Transfer chunk changed: " + path.name)
            archive.write(content)
            digest.update(content)
        if digest.hexdigest() != manifest["archive_sha256"]:
            raise ValueError("Transfer archive hash mismatch")
        archive.seek(0)
        destination.mkdir()
        with tarfile.open(fileobj=archive) as bundle:
            members = bundle.getmembers()
            for member in members:
                if not (member.isfile() or member.isdir()) or not (destination / member.name).resolve().is_relative_to(destination.resolve()):
                    raise ValueError("Unsafe transfer archive member")
            bundle.extractall(destination, members=members, filter="data")
    verify()
    return manifest


if __name__ == "__main__":
    value = restore(*sys.argv[1:3])
    print(json.dumps({"data_version": value["data_version"], "files_verified": len(value["files"])}))
