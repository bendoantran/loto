"""Local, atomic recovery records. Never delete a lock to unlock a running job."""
import contextlib
import hashlib
import json
import os
import shutil
import signal
import uuid
from pathlib import Path
from .data import canonical, digest


def fsync_directory(path):
    if os.name != "nt":
        fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)


def atomic_bytes(path, payload):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name("." + path.name + "." + uuid.uuid4().hex + ".tmp")
    with temporary.open("xb") as stream:
        stream.write(payload)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)
    fsync_directory(path.parent)


def atomic_json(path, value):
    atomic_bytes(path, canonical(value))


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def file_hash(path):
    value = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def array_signature(arrays):
    import numpy as np
    result = []
    for array in arrays:
        array = np.ascontiguousarray(array)
        result.append({"shape": list(array.shape), "dtype": str(array.dtype),
                       "sha256": hashlib.sha256(array.tobytes()).hexdigest()})
    return result


def ensure_context(folder, context):
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / "context.json"
    expected = json.loads(canonical({"schema": 1, "context": context, "sha256": digest(canonical(context))}))
    if path.exists():
        if read_json(path) != expected:
            raise ValueError(f"Recovery context changed: {folder}; use a new run destination")
    else:
        atomic_json(path, expected)
    return folder


@contextlib.contextmanager
def exclusive_lock(path):
    """Kernel-owned lock is released on exit, SIGKILL, or reboot; filename persists."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    stream = path.open("a+b")
    try:
        if os.name == "nt":
            import msvcrt
            if path.stat().st_size == 0:
                stream.write(b"\0")
                stream.flush()
            stream.seek(0)
            msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError as error:
        stream.close()
        raise RuntimeError(f"Another worker owns {path}; do not remove the lock file") from error
    try:
        yield
    finally:
        stream.close()


class StopRequested(Exception):
    pass


class StopControl:
    def __init__(self, path):
        self.path, self.signalled = Path(path), False

    def check(self):
        if self.signalled or self.path.exists():
            raise StopRequested(f"Stopped at a recovery boundary; preserve {self.path} until explicit resume")

    @contextlib.contextmanager
    def signals(self):
        def request(signum, frame):
            self.signalled = True
        previous = {s: signal.signal(s, request) for s in (signal.SIGINT, signal.SIGTERM)}
        try:
            yield self
        finally:
            for s, handler in previous.items():
                signal.signal(s, handler)


class CheckpointStore:
    """Payload first, checksummed pointer last; retain two committed generations.

    Uncommitted crash debris is ignored, never promoted. A damaged committed
    payload raises an error rather than silently starting over or rolling back.
    """
    def __init__(self, folder):
        self.folder = Path(folder)
        self.folder.mkdir(parents=True, exist_ok=True)
        self.pointer = self.folder / "latest.json"

    def load(self):
        if not self.pointer.exists():
            return None
        entry = read_json(self.pointer)
        seal = entry.pop("record_sha256", None)
        if seal != digest(canonical(entry)):
            raise ValueError("Checkpoint pointer hash mismatch; preserve and inspect it")
        path = self.folder / entry["name"]
        if path.parent.resolve() != self.folder.resolve():
            raise ValueError("Unsafe checkpoint path")
        for name, expected in entry["files"].items():
            member = path / name if path.is_dir() else path
            if not member.resolve().is_relative_to(path.resolve() if path.is_dir() else self.folder.resolve()):
                raise ValueError("Unsafe checkpoint member")
            if file_hash(member) != expected:
                raise ValueError(f"Checkpoint hash mismatch: {member}; preserve and inspect it")
        return path, entry["progress"]

    def commit(self, writer, suffix, progress, after_commit=None):
        name = "generation-" + uuid.uuid4().hex + suffix
        path = self.folder / name
        writer(path)
        members = sorted(path.rglob("*")) if path.is_dir() else [path]
        hashes = {}
        for member in members:
            if member.is_file():
                with member.open("r+b") as stream:
                    os.fsync(stream.fileno())
                hashes[str(member.relative_to(path)) if path.is_dir() else "."] = file_hash(member)
        if path.is_dir():
            for directory in sorted((p for p in path.rglob("*") if p.is_dir()), reverse=True):
                fsync_directory(directory)
            fsync_directory(path)
        fsync_directory(self.folder)
        previous = self.folder / "previous.json"
        old_previous = read_json(previous) if previous.exists() else None
        if self.pointer.exists():
            atomic_bytes(previous, self.pointer.read_bytes())
        entry = {"name": name, "files": hashes, "progress": progress}
        atomic_json(self.pointer, {**entry, "record_sha256": digest(canonical(entry))})
        if old_previous and old_previous["name"] != name:
            old = self.folder / old_previous["name"]
            if old.parent.resolve() == self.folder.resolve() and old.name.startswith("generation-"):
                if old.is_dir():
                    shutil.rmtree(old)
                elif old.exists():
                    old.unlink()
        if after_commit:
            after_commit(progress)
        return path


def publish_package(model, destination, metadata):
    """An interrupted save leaves only an uncommitted sibling; never a final package."""
    destination = Path(destination)
    if destination.exists():
        raise FileExistsError(destination)
    temporary = destination.with_name("." + destination.name + "." + uuid.uuid4().hex + ".partial")
    model.save(temporary, metadata)
    for member in temporary.rglob("*"):
        if member.is_file():
            with member.open("r+b") as stream:
                os.fsync(stream.fileno())
    for directory in sorted((p for p in temporary.rglob("*") if p.is_dir()), reverse=True):
        fsync_directory(directory)
    fsync_directory(temporary)
    os.replace(temporary, destination)
    fsync_directory(destination.parent)


def publish_directory(source, destination):
    destination = Path(destination)
    temporary = destination.with_name("." + destination.name + "." + uuid.uuid4().hex + ".partial")
    shutil.copytree(source, temporary)
    for member in temporary.rglob("*"):
        if member.is_file():
            with member.open("r+b") as stream:
                os.fsync(stream.fileno())
    for directory in sorted((p for p in temporary.rglob("*") if p.is_dir()), reverse=True):
        fsync_directory(directory)
    fsync_directory(temporary)
    if destination.exists():
        raise FileExistsError(destination)
    os.replace(temporary, destination)
    fsync_directory(destination.parent)


def verify_completed_run(folder):
    """Verify published files before a grid considers a committed job complete."""
    from .data import PRIZES
    folder = Path(folder)
    if read_json(folder / "run-status.json")["state"] != "complete":
        raise ValueError("Run has not committed completion")
    report = read_json(folder / "development-report.json")
    for key, entry in report["models"].items():
        family, prize = key.split("|")
        label = f"{family}-prize{PRIZES.index(prize)}"
        package = folder / label
        manifest = read_json(package / "manifest.json")
        if manifest["model_version"] != digest(canonical(manifest["files"])):
            raise ValueError("Published model manifest changed")
        if manifest["model_version"] != entry["artifacts"]["model_version"]:
            raise ValueError("Report/model version mismatch")
        for name, expected in manifest["files"].items():
            member = (package / name).resolve()
            if not member.is_relative_to(package.resolve()) or file_hash(member) != expected:
                raise ValueError("Published model file changed/unsafe path")
        for name, expected in ((f"validation-{label}.npz", entry["artifacts"]["validation_sha256"]),
                (f"validation-queries-prize{PRIZES.index(prize)}.json", entry["artifacts"]["queries_sha256"])):
            if file_hash(folder / name) != expected:
                raise ValueError("Published validation artifact changed")
    if not report["models"]:
        raise ValueError("Completed run contains no results")
    return file_hash(folder / "development-report.json")
