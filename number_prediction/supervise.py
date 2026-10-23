"""Bounded restart supervisor; generate a user unit without installing or starting it."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time
if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from number_prediction.data import digest, canonical
from number_prediction.recovery import (StopControl, StopRequested, atomic_json, exclusive_lock, read_json)


def supervise(command, folder, max_retries=3, retry_seconds=60):
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    control = StopControl(folder / "STOP")
    context = {"command": command, "max_retries": max_retries, "retry_seconds": retry_seconds}
    with exclusive_lock(folder / "supervisor.lock"), control.signals():
        path = folder / "supervisor-state.json"
        state = read_json(path) if path.exists() else {"context": context, "attempts": 0}
        if state["context"] != context:
            raise ValueError("Supervisor command/budget changed; preserve its state and use a new directory")
        if state.get("state") == "complete":
            return 0
        try:
            while state["attempts"] <= max_retries:
                control.check()
                # A resumed single run must explicitly opt into the existing destination.
                resolved = list(command)
                if "--out" in resolved:
                    destination = Path(resolved[resolved.index("--out") + 1])
                    if (destination / "STOP").exists():
                        raise StopRequested("Child run has a durable STOP request")
                    if (destination / "run-context.json").exists() or (destination.exists()
                            and all(p.name == "worker.lock" for p in destination.iterdir())):
                        if "--resume" not in resolved:
                            resolved.append("--resume")
                state.update(state="running", attempts=state["attempts"] + 1, command_sha256=digest(canonical(command)))
                atomic_json(path, state)
                child = subprocess.Popen(resolved)
                try:
                    while child.poll() is None:
                        if control.signalled or control.path.exists():
                            child.terminate()
                            try:
                                child.wait(timeout=30)
                            except subprocess.TimeoutExpired:
                                child.kill()
                                child.wait()
                            control.check()
                        try:
                            child.wait(timeout=1)
                        except subprocess.TimeoutExpired:
                            pass
                    code = child.returncode
                finally:
                    if child.poll() is None:
                        child.terminate()
                        try:
                            child.wait(timeout=30)
                        except subprocess.TimeoutExpired:
                            child.kill()
                            child.wait()
                state.update(last_returncode=code, state="complete" if code == 0 else "stopped" if code == 75 else "failed")
                atomic_json(path, state)
                if code in (0, 75):
                    return code
                if state["attempts"] > max_retries:
                    break
                deadline = time.monotonic() + retry_seconds
                while time.monotonic() < deadline:
                    control.check()
                    time.sleep(max(0, min(1, deadline - time.monotonic())))
            state["state"] = "retry_budget_exhausted"
            atomic_json(path, state)
            return 78
        except StopRequested:
            state["state"] = "stopped"
            atomic_json(path, state)
            return 75


def unit_text(command_file, state, max_retries, retry_seconds):
    def quote(value):
        return '"' + str(value).replace('\\', '\\\\').replace('"', '\\"').replace('%', '%%') + '"'
    invocation = [sys.executable, Path(__file__).resolve(), "--command", Path(command_file).resolve(),
                  "--state", Path(state).resolve(), "--max-retries", max_retries, "--retry-seconds", retry_seconds, "--execute"]
    return "\n".join(["[Unit]", "Description=Loto prediction recovery supervisor", "",
        "[Service]", "Type=simple", "WorkingDirectory=" + str(Path(__file__).resolve().parent.parent).replace("%", "%%"),
        "ExecStart=" + " ".join(quote(x) for x in invocation), "Restart=on-failure", "RestartSec=60",
        "RestartPreventExitStatus=75 78", "KillSignal=SIGTERM", "KillMode=mixed", "TimeoutStopSec=40",
        "Environment=OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 MKL_NUM_THREADS=2 NUMEXPR_NUM_THREADS=2",
        "", "[Install]", "WantedBy=default.target", ""])


def main():
    from number_prediction import configure_cli
    configure_cli()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--command", type=Path, required=True, help="UTF-8 JSON array of command arguments; no shell")
    parser.add_argument("--state", type=Path, required=True, help="Persistent supervisor state directory, including its own STOP")
    parser.add_argument("--max-retries", type=int, default=3)
    parser.add_argument("--retry-seconds", type=float, default=60)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--write-unit", type=Path, help="Create a new systemd user unit file; never installs/enables it")
    args = parser.parse_args()
    command = read_json(args.command)
    if not isinstance(command, list) or not command or not all(isinstance(x, str) for x in command):
        parser.error("Command must be a nonempty JSON array of strings")
    if args.max_retries < 0 or args.retry_seconds < 0:
        parser.error("Retry count and delay cannot be negative")
    if args.write_unit:
        if os.name == "nt":
            parser.error("systemd units require Linux; manual --execute is portable")
        with args.write_unit.open("x", encoding="utf-8") as stream:
            stream.write(unit_text(args.command, args.state, args.max_retries, args.retry_seconds))
    if args.execute:
        raise SystemExit(supervise(command, args.state, args.max_retries, args.retry_seconds))
    print(json.dumps({"prepared_only": True, "unit": str(args.write_unit) if args.write_unit else None}))


if __name__ == "__main__":
    main()
