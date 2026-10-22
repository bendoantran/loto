"""Prepare/restart a serial server comparison grid using one immutable snapshot."""
import argparse
import json
import subprocess
import sys
from pathlib import Path
if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from number_prediction.data import canonical, digest, load_snapshot


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--params", type=Path)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--max-jobs", type=int, default=1, help="Bound this invocation; rerun to continue pending jobs")
    parser.add_argument("--province", action="append", default=[], help="Add explicitly requested province-only comparisons")
    args = parser.parse_args()
    _, manifest = load_snapshot(args.data)
    args.out.mkdir(parents=True, exist_ok=True)
    path = args.out / "experiment-grid.json"
    params_digest = digest(args.params.read_bytes()) if args.params else None
    context = {"data_version": manifest["data_version"], "params_sha256": params_digest, "provinces": args.province}
    jobs = []
    for scope in ("both", "xsmn", "xsmt"):
        for inputs in ("both", "G.8", "G.ĐB"):
            for province in [None, *args.province]:
                label = digest(canonical([scope, inputs, province]))[:12]
                destination = args.out / label
                command = [sys.executable, str(Path(__file__).with_name("train.py")), "--data", str(args.data.resolve()),
                    "--out", str(destination.resolve()), "--family", "all", "--prize", "both", "--training-region", scope,
                    "--input-prizes", inputs, "--horizons", "1,2,3,4,5"]
                if args.params:
                    command += ["--params", str(args.params.resolve())]
                if province:
                    command += ["--province", province]
                jobs.append({"label": label, "scope": scope, "inputs": inputs, "province": province, "command": command})
    grid = {"context": context, "jobs": jobs, "policy": "serial, bounded invocation, immutable run destinations; failed jobs require inspection"}
    if path.exists():
        if json.loads(path.read_text())["context"] != context:
            raise ValueError("Existing grid uses another snapshot/settings")
    else:
        path.write_bytes(canonical(grid))
    if args.execute:
        count = 0
        for job in jobs:
            done = args.out / (job["label"] + ".done")
            if done.exists():
                continue
            if count >= args.max_jobs:
                break
            # train refuses an existing destination, including a failed partial job.
            subprocess.run(job["command"], check=True)
            done.write_bytes(canonical({"context": context, "job": job["label"]}))
            count += 1
    print(json.dumps({"jobs": len(jobs), "plan": str(path), "executed": args.execute}))


if __name__ == "__main__":
    main()
