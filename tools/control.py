"""Start/status/stop the same collector on Kubuntu or Windows."""
import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
import history


def status(root):
    if not (root / "history.sqlite3").exists():
        return {"state": "not_restored", "worker_running": history.lock_held(root)}
    result = subprocess.run([sys.executable, str(REPO / "history.py"), "status", "--root", str(root)],
                            check=True, capture_output=True, text=True, encoding="utf-8")
    return json.loads(result.stdout)


def start(root):
    info = status(root)
    if info["worker_running"]:
        return "Collector already running; no second worker started."
    if info["state"] == "not_restored":
        raise RuntimeError("Restore the checkpoint first: python3 tools/restore_snapshot.py")
    if info["processed_days"] == info["total_days"]:
        return "The saved date range is finished; nothing needs downloading."
    stop = root / "STOP"
    if stop.exists():
        stop.unlink()
    logs = root / "launch-logs"
    logs.mkdir(exist_ok=True)
    stamp = str(time.time_ns())
    kwargs = {"cwd": root, "stdin": subprocess.DEVNULL}
    if os.name == "nt":
        kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW | subprocess.DETACHED_PROCESS
    else:
        kwargs["start_new_session"] = True
    with (logs / (stamp + ".out.log")).open("ab") as out, (logs / (stamp + ".err.log")).open("ab") as err:
        process = subprocess.Popen([sys.executable, "-u", str(REPO / "history.py"), "run", "--root", str(root)],
                                   stdout=out, stderr=err, **kwargs)
    time.sleep(0.6)
    if process.poll() is not None and process.returncode != 0:
        raise RuntimeError("Collector exited at launch; inspect launch-logs/.")
    return f"Collector launched (PID {process.pid}); completed dates will be skipped."


def request_stop(root, wait=0):
    history.atomic_write(root / "STOP", "Stop requested by the user.\n")
    until = time.monotonic() + wait
    while wait and time.monotonic() < until and history.lock_held(root):
        time.sleep(0.5)
    return "Stop requested; committed dates are safe."


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("command", choices=["start", "status", "request-stop", "should-run"])
    p.add_argument("--root", type=Path, default=REPO)
    p.add_argument("--wait", type=float, default=0)
    args = p.parse_args()
    root = args.root.resolve()
    root.mkdir(parents=True, exist_ok=True)
    if args.command == "start":
        print(start(root))
    elif args.command == "status":
        print(json.dumps(status(root), ensure_ascii=False, indent=2))
    elif args.command == "request-stop":
        print(request_stop(root, args.wait))
    else:
        if (root / "STOP").exists() or not (root / "history.sqlite3").exists():
            raise SystemExit(1)
        info = status(root)
        raise SystemExit(0 if info["processed_days"] < info["total_days"] and not info["worker_running"] else 1)


if __name__ == "__main__":
    main()
