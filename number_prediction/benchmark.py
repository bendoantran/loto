"""Run identical saved CPU probes on Linux and Windows; compare full probabilities."""
import argparse
import json
import os
import platform
import time
from pathlib import Path
import numpy as np
if __package__ in (None, ""):
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from number_prediction.pipeline import Predictor, environment
from number_prediction.data import canonical


def peak_memory_bytes():
    if os.name != "nt":
        import resource
        return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * (1 if platform.system() == "Darwin" else 1024)
    import ctypes
    from ctypes import wintypes
    class Counters(ctypes.Structure):
        _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD)] + [(name, ctypes.c_size_t) for name in
            ("PeakWorkingSetSize", "WorkingSetSize", "QuotaPeakPagedPoolUsage", "QuotaPagedPoolUsage", "QuotaPeakNonPagedPoolUsage", "QuotaNonPagedPoolUsage", "PagefileUsage", "PeakPagefileUsage")]
    counters = Counters()
    counters.cb = ctypes.sizeof(counters)
    handle = ctypes.windll.kernel32.GetCurrentProcess()
    if not ctypes.windll.psapi.GetProcessMemoryInfo(handle, ctypes.byref(counters), counters.cb):
        raise OSError("Windows GetProcessMemoryInfo failed")
    return counters.PeakWorkingSetSize


def main():
    from number_prediction import configure_cli
    configure_cli()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--queries", type=Path, required=True)
    parser.add_argument("--reference", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--repetitions", type=int, default=10)
    args = parser.parse_args()
    if args.repetitions < 1:
        parser.error("Repetitions must be positive")
    started = time.perf_counter()
    model = Predictor.load(args.model)
    load_seconds = time.perf_counter() - started
    queries = json.loads(args.queries.read_text(encoding="utf-8"))
    p = model.predict(queries)
    timings = []
    for _ in range(args.repetitions):
        started = time.perf_counter()
        model.predict(queries)
        timings.append(time.perf_counter() - started)
    comparison = None
    if args.reference:
        reference = json.loads(args.reference.read_text(encoding="utf-8"))
        if reference["model_version"] != model.model_version or reference["queries"] != queries:
            raise ValueError("Reference uses different model or probes")
        expected = np.asarray(reference["probabilities"])
        comparison = {"atol": 1e-6, "rtol": 1e-5, "max_abs": float(abs(p - expected).max()),
                      "passed": bool(np.allclose(p, expected, atol=1e-6, rtol=1e-5))}
        if not comparison["passed"]:
            raise ValueError("Cross-machine probability tolerance failed; preserve the existing deployment")
    report = {"environment": environment(), "model_version": model.model_version, "queries": queries,
        "probabilities": p.tolist(), "load_seconds": load_seconds,
        "median_batch_seconds": float(np.median(timings)), "peak_process_memory_bytes": peak_memory_bytes(),
        "repetitions": args.repetitions, "comparison": comparison}
    with args.out.open("xb") as stream:
        stream.write(canonical(report))
    print(json.dumps({k: v for k, v in report.items() if k not in ("queries", "probabilities")}))


if __name__ == "__main__":
    main()
