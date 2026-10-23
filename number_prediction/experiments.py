"""Prepare/restart a serial server comparison grid using one immutable snapshot."""
import argparse
import json
import subprocess
import sys
from pathlib import Path
if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from number_prediction.data import canonical, digest, load_snapshot
from number_prediction.pipeline import environment
from number_prediction.recovery import (StopControl, StopRequested, atomic_json, exclusive_lock, read_json,
                                       verify_completed_run)


def main():
    from number_prediction import configure_cli
    configure_cli()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--params", type=Path)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--max-jobs", type=int, default=1, help="Bound this invocation; rerun to continue pending jobs")
    parser.add_argument("--province", action="append", default=[], help="Add explicitly requested province-only comparisons")
    args = parser.parse_args()
    if args.max_jobs < 1:
        parser.error("--max-jobs must be positive")
    _, manifest = load_snapshot(args.data)
    args.out.mkdir(parents=True, exist_ok=True)
    path = args.out / "experiment-grid.json"
    params_digest = digest(args.params.read_bytes()) if args.params else None
    context = {"data_version": manifest["data_version"], "params_sha256": params_digest, "provinces": args.province,
               "environment": environment(), "config_sha256": digest(Path(__file__).with_name("config.json").read_bytes()),
               "source": {p.name: digest(p.read_bytes()) for p in Path(__file__).parent.glob("*.py")}}
    jobs = []
    for scope in ("both", "xsmn", "xsmt"):
        for inputs in ("both", "G.8", "G.ĐB"):
            for province in [None, *args.province]:
                label = digest(canonical([scope, inputs, province]))[:12]
                destination = args.out / label
                command = [sys.executable, str(Path(__file__).resolve().with_name("train.py")), "--data", str(args.data.resolve()),
                    "--out", str(destination.resolve()), "--family", "all", "--prize", "both", "--training-region", scope,
                    "--input-prizes", inputs, "--horizons", "1,2,3,4,5"]
                if args.params:
                    command += ["--params", str(args.params.resolve())]
                if province:
                    command += ["--province", province]
                jobs.append({"label": label, "scope": scope, "inputs": inputs, "province": province, "command": command})
    grid = {"context": context, "jobs": jobs, "policy": "serial, bounded; verified partial jobs resume automatically"}
    with exclusive_lock(args.out / "grid.lock"):
        if path.exists():
            if read_json(path)["context"] != context:
                raise ValueError("Existing grid uses another snapshot/settings/code/environment")
        else:
            atomic_json(path, grid)
        if args.execute:
            control = StopControl(args.out / "STOP")
            with control.signals():
                try:
                    execute(args, context, jobs, control)
                except StopRequested as error:
                    print(str(error))
                    raise SystemExit(75)
    print(json.dumps({"jobs": len(jobs), "plan": str(path), "executed": args.execute}))


def execute(args, context, jobs, control):
    count = 0
    for job in jobs:
        control.check()
        done = args.out / (job["label"] + ".done")
        destination = args.out / job["label"]
        if done.exists():
            record = read_json(done)
            if record["context"] != context or read_json(destination / "run-status.json")["state"] != "complete":
                raise ValueError("Completed grid job has inconsistent state")
            if record["report_sha256"] != verify_completed_run(destination):
                raise ValueError("Completed grid report changed")
            continue
        if count >= args.max_jobs:
            break
        command = list(job["command"])
        if destination.exists():
            command.append("--resume")
        child = subprocess.Popen(command)
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
            if child.returncode == 75:
                raise StopRequested("Grid child intentionally stopped; resume explicitly after inspecting STOP")
            if child.returncode:
                raise subprocess.CalledProcessError(child.returncode, command)
            atomic_json(done, {"context": context, "job": job["label"],
                "report_sha256": verify_completed_run(destination)})
            count += 1
        finally:
            if child.poll() is None:
                child.terminate()
                child.wait()


if __name__ == "__main__":
    main()
