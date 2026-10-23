"""Build a new offline Linux training bundle from explicit verified inputs; no downloads."""
import argparse
from email.parser import BytesParser
import hashlib
import json
from pathlib import Path
import shutil
import tarfile
import zipfile
if __package__ in (None, ""):
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from number_prediction.recovery import atomic_json, file_hash
from number_prediction.data import load_snapshot


def build(output, runtime, wheelhouse, data, opencl, license_file):
    output = Path(output)
    if output.exists():
        raise FileExistsError("Bundle output exists; preserve it and choose a new destination")
    repo = Path(__file__).resolve().parent.parent
    rows, manifest = load_snapshot(data)
    output.mkdir(parents=True)
    prediction = output / "number_prediction"
    prediction.mkdir()
    for p in (repo / "number_prediction").iterdir():
        if p.is_file() and p.suffix in (".py", ".md", ".json", ".txt"):
            shutil.copy2(p, prediction / p.name)
    for folder in ("tests", "server_bundle"):
        shutil.copytree(repo / "number_prediction" / folder, prediction / folder,
                        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    transfer_helper = repo / "tools/restore_prediction_transfer.py"
    if transfer_helper.exists():
        (output / "tools").mkdir()
        shutil.copy2(transfer_helper, output / "tools" / transfer_helper.name)
    for name in ("AGENTS.md", "KUBUNTU_AGENT_HANDOFF.md", "PREDICTION_KUBUNTU_HANDOFF.md", "PREDICTION_IMPLEMENTATION_PLAN.md"):
        shutil.copy2(repo / name, output / name)
    shutil.copytree(data, prediction / "datasets" / data.name)
    with tarfile.open(runtime) as archive:
        archive.extractall(output / "runtime", filter="data")
    # CPython can rewrite bundled bytecode on its very first invocation.
    # Verify source/native files, not a mutable interpreter cache.
    for cache in (output / "runtime").rglob("*.pyc"):
        cache.unlink()
    shutil.copytree(wheelhouse, output / "wheelhouse")
    lock = []
    names = set()
    for wheel in sorted((output / "wheelhouse").glob("*.whl")):
        with zipfile.ZipFile(wheel) as archive:
            meta = BytesParser().parsebytes(archive.read(next(n for n in archive.namelist() if n.endswith(".dist-info/METADATA"))))
        name, version = meta["Name"], meta["Version"]
        normalized = name.lower().replace("_", "-")
        if normalized in names:
            raise ValueError("Multiple wheels for " + name)
        names.add(normalized)
        lock.append(f"{name}=={version} --hash=sha256:{file_hash(wheel)}")
    if not {"torch", "xgboost", "lightgbm", "catboost"} <= names:
        raise ValueError("Wheelhouse lacks a required learned family")
    (output / "wheel-lock.txt").write_text("\n".join(lock) + "\n", encoding="utf-8")
    (output / "native/lib").mkdir(parents=True)
    (output / "native/vendors").mkdir()
    shutil.copy2(opencl, output / "native/lib/libOpenCL.so.1")
    shutil.copy2(license_file, output / "native/OPENCL-COPYING")
    (output / "native/vendors/nvidia.icd").write_text("libnvidia-opencl.so.1\n", encoding="utf-8")
    for name in ("setup.sh", "loto", "verify_bundle.py"):
        shutil.copy2(repo / "number_prediction/server_bundle" / name, output / name)
    for name in ("setup.sh", "loto"):
        (output / name).chmod(0o755)
    shutil.copy2(repo / "number_prediction/SERVER.md", output / "START-HERE.md")
    files = {}
    for path in sorted(output.rglob("*")):
        name = path.relative_to(output).as_posix()
        if path.is_symlink():
            if not path.resolve().is_relative_to(output.resolve()):
                raise ValueError("External symlink in runtime: " + name)
            files[name] = {"symlink": str(path.readlink())}
        elif path.is_file():
            files[name] = {"sha256": file_hash(path), "bytes": path.stat().st_size}
    result = {"schema": 1, "platform": "linux-x86_64-glibc", "data_version": manifest["data_version"],
        "rows": len(rows), "runtime_archive_sha256": file_hash(runtime), "files": files,
        "scope": "source, immutable modeling snapshot and offline Python/dependencies; no raw HTML/SQLite collector archive, old runs or credentials"}
    atomic_json(output / "bundle-manifest.json", result)
    return {"files": len(files), "wheels": len(names), "data_version": manifest["data_version"]}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("out", "runtime", "wheelhouse", "data", "opencl", "opencl-license"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(build(args.out, args.runtime, args.wheelhouse, args.data, args.opencl, args.opencl_license), indent=2))
