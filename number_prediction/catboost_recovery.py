"""Isolate native snapshot loading so CatBoost cannot silently discard bad progress."""
from pathlib import Path
import queue
import re
import shutil
import subprocess
import sys
import tempfile
import threading
from .recovery import CheckpointStore, atomic_json, exclusive_lock, read_json


def resume(model, x, y, checkpoint, stop_check=None, after_checkpoint=None):
    """Native warnings bypass Python log callbacks; supervise a separate process.

    Keep a checksummed copy before the native library touches the snapshot.
    The child owns its own kernel lock, including if its parent dies.
    Temporary numeric inputs are derived data, never archive evidence.
    """
    import numpy as np
    checkpoint = Path(checkpoint).resolve()
    invalid = checkpoint / "invalid-snapshot.json"
    if invalid.exists():
        raise ValueError(f"CatBoost previously rejected this snapshot; preserve {invalid} and inspect its backup")
    with exclusive_lock(checkpoint / "native-worker.lock"):
        store = CheckpointStore(checkpoint / "resume-evidence")
        backup = store.commit(lambda path: shutil.copyfile(checkpoint / "native.snapshot", path),
                              ".snapshot", {"reason": "before_native_resume"})
    with tempfile.TemporaryDirectory(prefix=".resume-input-", dir=checkpoint) as temp:
        folder = Path(temp)
        np.save(folder / "x.npy", x, allow_pickle=False)
        np.save(folder / "y.npy", y, allow_pickle=False)
        atomic_json(folder / "params.json", model.params)
        command = [sys.executable, "-m", "number_prediction.catboost_recovery", str(folder), str(checkpoint)]
        child = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                 text=True, encoding="utf-8", errors="replace", bufsize=1)
        messages = queue.Queue()
        def reader():
            try:
                for line in child.stdout:
                    messages.put(line)
            finally:
                messages.put(None)
        thread = threading.Thread(target=reader, daemon=True)
        thread.start()
        restored, output, finished = 0, "", False
        try:
            while not finished:
                if stop_check:
                    stop_check()
                try:
                    line = messages.get(timeout=.1)
                except queue.Empty:
                    continue
                if line is None:
                    finished = True
                    continue
                print(line, end="", flush=True)
                output = (output + line)[-16000:]
                if "can't load progress from snapshot file" in output.lower():
                    child.kill()
                    child.wait(timeout=30)
                    atomic_json(invalid, {"error": "Native CatBoost refused its snapshot; silent restart blocked",
                        "preserved_snapshot": str(backup), "native_output": output})
                    raise ValueError(f"CatBoost snapshot is invalid. Stopped instead of retraining; evidence: {invalid}")
                match = re.search(r"Restore #(\d+) trees from progress", output)
                if match:
                    restored = int(match[1])
            code = child.wait()
            if code:
                raise RuntimeError(f"CatBoost resume worker exited {code}; preserve {backup}\n{output}")
            from .trees import TreeModel
            loaded = TreeModel.load(folder / "model")
            model.model, model.classes = loaded.model, loaded.classes
            model.training_device = loaded.training_device
            model.resumed_from_round = restored
            if after_checkpoint:
                after_checkpoint({"rounds": model.params["iterations"], "native_snapshot": True})
            return model
        finally:
            if child.poll() is None:
                child.terminate()
                try:
                    child.wait(timeout=30)
                except subprocess.TimeoutExpired:
                    child.kill()
                    child.wait()
            thread.join(timeout=10)
            child.stdout.close()


def main():
    import numpy as np
    from .trees import TreeModel
    folder, checkpoint = map(Path, sys.argv[1:3])
    # This lock survives parent death and prevents another native writer.
    with exclusive_lock(checkpoint / "native-worker.lock"):
        atomic_json(checkpoint / "native-worker.json", {"pid": __import__("os").getpid()})
        model = TreeModel(**read_json(folder / "params.json"))
        model.fit(np.load(folder / "x.npy", mmap_mode="r"), np.load(folder / "y.npy", mmap_mode="r"),
                  checkpoint=checkpoint, _catboost_resume_child=True)
        model.save(folder / "model")


if __name__ == "__main__":
    main()
