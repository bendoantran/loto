"""Non-admin server checks and explicit, recoverable launch commands. No implicit training."""
import argparse
import ctypes
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys
import time
import uuid
if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from number_prediction.recovery import atomic_json, exclusive_lock, read_json, verify_completed_run

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "number_prediction/datasets/post-xsmt-20261022T1936"
_DETACHED_CHILDREN = []


def locked(path):
    """Probe an existing kernel lock without deleting it or leaving a new file."""
    if not path.exists():
        return False
    try:
        with exclusive_lock(path):
            return False
    except RuntimeError:
        return True


def opencl_devices():
    """Inspect the OpenCL GPU LightGBM actually needs, independently of CUDA."""
    lib = ctypes.CDLL("libOpenCL.so.1")
    uint, ptr = ctypes.c_uint, ctypes.c_void_p
    lib.clGetPlatformIDs.argtypes = [uint, ctypes.POINTER(ptr), ctypes.POINTER(uint)]
    lib.clGetDeviceIDs.argtypes = [ptr, ctypes.c_ulong, uint, ctypes.POINTER(ptr), ctypes.POINTER(uint)]
    lib.clGetDeviceInfo.argtypes = [ptr, uint, ctypes.c_size_t, ptr, ctypes.POINTER(ctypes.c_size_t)]
    count = uint()
    if lib.clGetPlatformIDs(0, None, ctypes.byref(count)) != 0 or not count.value:
        raise RuntimeError("No OpenCL platform: the NVIDIA driver must provide libnvidia-opencl.so.1")
    platforms = (ptr * count.value)()
    if lib.clGetPlatformIDs(count, platforms, None) != 0:
        raise RuntimeError("Cannot enumerate OpenCL platforms")
    names = []
    for platform_id, p in enumerate(platforms):
        n = uint()
        if lib.clGetDeviceIDs(p, 0xFFFFFFFF, 0, None, ctypes.byref(n)) != 0:
            continue
        devices = (ptr * n.value)()
        if lib.clGetDeviceIDs(p, 0xFFFFFFFF, n, devices, None) != 0:
            continue
        for device_id, device in enumerate(devices):
            kind = ctypes.c_ulong()
            if lib.clGetDeviceInfo(device, 0x1000, ctypes.sizeof(kind), ctypes.byref(kind), None) != 0 or not kind.value & 4:
                continue
            value = ctypes.create_string_buffer(4096)
            if lib.clGetDeviceInfo(device, 0x102B, len(value), value, None) == 0:
                identity = ctypes.create_string_buffer(16)
                identity_ok = lib.clGetDeviceInfo(device, 0x106A, 16, identity, None) == 0
                names.append({"platform_id": platform_id, "device_id": device_id,
                    "name": value.value.decode("utf-8", errors="replace"),
                    "uuid": str(uuid.UUID(bytes=identity.raw)) if identity_ok else None})
    if not names:
        raise RuntimeError("No OpenCL GPU; CUDA readiness alone does not establish LightGBM readiness")
    return names


def gpu_selection():
    import torch
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA device zero unavailable; check the driver and allocation")
    devices = opencl_devices()
    identity = str(getattr(torch.cuda.get_device_properties(0), "uuid", "")).lower().removeprefix("gpu-")
    requested = (os.environ.get("LOTO_OPENCL_PLATFORM"), os.environ.get("LOTO_OPENCL_DEVICE"))
    if any(v is not None for v in requested):
        if not all(v is not None for v in requested):
            raise ValueError("Set both LOTO_OPENCL_PLATFORM and LOTO_OPENCL_DEVICE")
        matches = [d for d in devices if (d["platform_id"], d["device_id"]) == tuple(map(int, requested))]
    else:
        matches = [d for d in devices if d["uuid"] and d["uuid"] == identity]
        if not matches and len(devices) == 1 and devices[0]["name"] == torch.cuda.get_device_name(0):
            matches = devices
    if len(matches) != 1:
        raise RuntimeError("Cannot uniquely match the allocated CUDA GPU to OpenCL. Devices: " + json.dumps(devices) + "; set both LOTO_OPENCL_PLATFORM and LOTO_OPENCL_DEVICE explicitly")
    selected = matches[0]
    if selected["uuid"] and identity and selected["uuid"] != identity:
        raise RuntimeError("Selected OpenCL GPU differs from allocated CUDA device zero; correct the GPU allocation/indices")
    return {"gpu_platform_id": selected["platform_id"], "gpu_device_id": selected["device_id"],
            "selected": selected, "opencl_devices": devices, "cuda_uuid": identity}


def doctor(device, data=DATA):
    """Readiness only: filesystem probes and a CUDA kernel, never model fitting."""
    import importlib.metadata
    from number_prediction.data import load_snapshot
    checks = []
    def check(name, action):
        try:
            checks.append({"check": name, "passed": True, "detail": action()})
        except Exception as error:
            checks.append({"check": name, "passed": False, "detail": str(error)})
    def system():
        if platform.system() != "Linux" or platform.machine() not in ("x86_64", "AMD64"):
            raise RuntimeError("This offline bundle targets Linux x86_64 with glibc; use another bundle for other systems")
        if sys.version_info[:2] != (3, 12):
            raise RuntimeError("Use the bundled Python 3.12 via ./loto")
        return {"python": platform.python_version(), "libc": platform.libc_ver(), "uid": os.getuid()}
    check("platform", system)
    def filesystem():
        import tempfile
        scratch = ROOT / "number_prediction/runs"
        scratch.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(prefix=".doctor-", dir=scratch) as temp:
            folder = Path(temp)
            atomic_json(folder / "probe.json", {"leading_zero": "00", "text": "G.ĐB"})
            if read_json(folder / "probe.json")["leading_zero"] != "00":
                raise RuntimeError("Filesystem readback differs")
            lock = folder / "probe.lock"
            with exclusive_lock(lock):
                code = "from pathlib import Path; from number_prediction.server import locked; import sys; sys.exit(0 if locked(Path(sys.argv[1])) else 1)"
                subprocess.run([sys.executable, "-c", code, str(lock)], cwd=ROOT, check=True, timeout=15)
        free = shutil.disk_usage(scratch).free
        if free < 2 * 1024**3:
            raise RuntimeError("Less than 2 GiB free; free space before the pilot. Full runs require more.")
        return {"atomic_write_fsync_cross_process_lock": True, "free_gib": round(free / 1024**3, 2)}
    check("writable_persistent_filesystem", filesystem)
    def packages():
        result = subprocess.run([sys.executable, "-m", "pip", "--isolated", "--no-cache-dir", "check"], capture_output=True,
                                text=True, encoding="utf-8", timeout=60)
        if result.returncode:
            raise RuntimeError(result.stdout + result.stderr)
        for module in ("numpy", "pandas", "scipy", "sklearn", "catboost", "lightgbm", "xgboost", "torch", "optuna", "openpyxl"):
            __import__(module)
        return {n: importlib.metadata.version(n) for n in ("torch", "xgboost", "catboost", "lightgbm")}
    check("binary_dependencies", packages)
    def snapshot():
        rows, manifest = load_snapshot(data)
        return {"rows": len(rows), "data_version": manifest["data_version"],
                "regions": sorted({r["region"] for r in rows}), "final_test_scored": False}
    check("immutable_snapshot", snapshot)
    if device == "cuda":
        def cuda():
            import torch
            import xgboost
            if not torch.cuda.is_available():
                raise RuntimeError("CUDA unavailable. This cannot install a kernel driver without an administrator; check GPU allocation/driver/device permissions or select CPU explicitly.")
            if not xgboost.build_info().get("USE_CUDA"):
                raise RuntimeError("XGBoost wheel lacks CUDA support")
            x = torch.arange(16, dtype=torch.float32, device="cuda").reshape(4, 4)
            total = float((x @ x.T).sum().cpu())
            if total != 3680:
                raise RuntimeError("CUDA kernel result differs")
            return {"gpu": torch.cuda.get_device_name(0), "kernel_sum": total, "runtime": torch.version.cuda}
        check("cuda_kernel_and_xgboost_build", cuda)
        check("lightgbm_allocated_opencl_gpu", gpu_selection)
    result = {"passed": all(c["passed"] for c in checks), "device": device, "model_fit_ran": False, "checks": checks}
    return result


def plan_folder(name):
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}", name):
        raise ValueError("Name must be 1..64 letters, digits, underscores or hyphens")
    return ROOT / "number_prediction/runs" / (name + ".launch")


def prepare(name, device, profile="pilot"):
    folder = plan_folder(name)
    folder.parent.mkdir(exist_ok=True)
    output = folder.with_name(name)
    if folder.exists() or output.exists():
        raise FileExistsError("Name already exists; preserve it and choose a new name")
    settings = read_json(ROOT / "number_prediction/pilot.json") if profile == "pilot" else {"model": {}}
    settings.setdefault("model", {}).update(device=device, threads=2)
    if device == "cuda":
        selection = gpu_selection()
        settings["model"].update({k: selection[k] for k in ("gpu_platform_id", "gpu_device_id")})
    folder.mkdir()
    atomic_json(folder / "params.json", settings)
    command = [sys.executable, str(ROOT / "number_prediction/train.py"), "--data", str(DATA),
               "--out", str(output), "--family", "all", "--prize", "both", "--params", str(folder / "params.json")]
    if profile == "pilot":
        command += ["--train-end", "2007-10-15", "--calibration-end", "2007-11-15", "--validation-end", "2007-12-31", "--checkpoint-every", "1"]
    else:
        command += ["--checkpoint-every", "10"]
    atomic_json(folder / "command.json", command)
    atomic_json(folder / "plan.json", {"name": name, "device": device, "profile": profile,
        "output": str(output), "created": time.time(), "prepared_only": True})
    return folder


def state_paths(folder):
    index = read_json(folder / "supervision.json")["generation"] if (folder / "supervision.json").exists() else 0
    return index, folder / f"supervisor-{index}"


def launch(folder, resume=False, foreground=False):
    plan = read_json(folder / "plan.json")
    output = Path(plan["output"])
    with exclusive_lock(folder / "launch.lock"):
        index, supervisor = state_paths(folder)
        if locked(supervisor / "supervisor.lock") or locked(output / "worker.lock"):
            raise RuntimeError("This run already has a live worker/supervisor; do not start a second writer")
        if (output / "run-status.json").exists() and read_json(output / "run-status.json")["state"] == "complete":
            verify_completed_run(output)
            return {"state": "complete", "verified": True, "fitted_again": False}
        if not resume and ((output / "STOP").exists() or (supervisor / "STOP").exists()):
            raise RuntimeError("Durable STOP exists. Inspect the run, then use the explicit resume command")
        elif not resume and (supervisor / "supervisor-state.json").exists():
            state = read_json(supervisor / "supervisor-state.json")
            if state.get("state") in ("stopped", "retry_budget_exhausted"):
                raise RuntimeError("Previous supervision stopped/exhausted; inspect it and use explicit resume")
        readiness = doctor(plan["device"])
        if not readiness["passed"]:
            raise RuntimeError("Pre-launch checks failed: " + json.dumps(readiness, ensure_ascii=False))
        if plan["device"] == "cuda":
            selection = gpu_selection()
            params = read_json(folder / "params.json")["model"]
            if any(params.get(k) != selection[k] for k in ("gpu_platform_id", "gpu_device_id")):
                raise RuntimeError("OpenCL allocation changed since preparation; preserve the plan and prepare a new run")
        if resume:
            # Only an explicit resume grants a new bounded retry allowance.
            # Do not clear durable stops until pre-launch checks succeed.
            for path in (output / "STOP", supervisor / "STOP"):
                if path.exists():
                    path.unlink()
            index += 1
            supervisor = folder / f"supervisor-{index}"
        atomic_json(folder / "supervision.json", {"generation": index, "explicit_resume": resume})
        command = [sys.executable, str(ROOT / "number_prediction/supervise.py"), "--command", str(folder / "command.json"),
                   "--state", str(supervisor), "--max-retries", "3", "--retry-seconds", "60", "--execute"]
        if foreground:
            # A foreground run must still accept STOP from another terminal.
            foreground_command = command
        else:
            foreground_command = None
        if foreground_command is None:
            with (folder / "process.log").open("ab", buffering=0) as log:
                child = subprocess.Popen(command, cwd=ROOT, stdin=subprocess.DEVNULL, stdout=log,
                                         stderr=subprocess.STDOUT, start_new_session=True, close_fds=True)
            _DETACHED_CHILDREN[:] = [p for p in _DETACHED_CHILDREN if p.poll() is None]
            _DETACHED_CHILDREN.append(child)
            atomic_json(folder / "process.json", {"pid": child.pid, "started": time.time(), "generation": index})
            # Wait only for supervisor ownership or a quick failure, not for fitting.
            deadline = time.monotonic() + 10
            while time.monotonic() < deadline and child.poll() is None:
                if locked(supervisor / "supervisor.lock"):
                    return {"state": "started", "pid": child.pid, "log": str(folder / "process.log")}
                time.sleep(.05)
            if child.poll() not in (None, 0):
                raise RuntimeError(f"Supervisor exited {child.returncode}; inspect {folder / 'process.log'}")
            return {"state": "dispatched", "pid": child.pid, "log": str(folder / "process.log")}
    return {"returncode": subprocess.run(foreground_command, cwd=ROOT).returncode}


def main():
    from number_prediction import configure_cli
    configure_cli()
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    d = sub.add_parser("doctor")
    d.add_argument("--device", choices=("cpu", "cuda"), default="cuda")
    for action in ("prepare", "pilot"):
        p = sub.add_parser(action)
        p.add_argument("--name", default="pilot-" + time.strftime("%Y%m%d-%H%M%S") if action == "pilot" else None, required=action == "prepare")
        p.add_argument("--device", choices=("cpu", "cuda"), default="cuda")
        if action == "prepare":
            p.add_argument("--profile", choices=("pilot", "development"), default="pilot")
    for action in ("start", "resume", "status", "stop"):
        p = sub.add_parser(action)
        p.add_argument("name")
        if action in ("start", "resume"):
            p.add_argument("--foreground", action="store_true")
    args = parser.parse_args()
    if args.action == "doctor":
        result = doctor(args.device)
    elif args.action in ("prepare", "pilot"):
        if args.action == "pilot":
            result = doctor(args.device)
            if not result["passed"]:
                print(json.dumps(result, ensure_ascii=False, indent=2))
                raise SystemExit(2)
        folder = prepare(args.name, args.device, getattr(args, "profile", "pilot"))
        result = {"prepared": str(folder), "training_started": False}
        if args.action == "pilot":
            result = launch(folder, foreground=True)
    else:
        folder = plan_folder(args.name)
        plan = read_json(folder / "plan.json")
        _, supervisor = state_paths(folder)
        output = Path(plan["output"])
        if args.action in ("start", "resume"):
            result = launch(folder, resume=args.action == "resume", foreground=args.foreground)
        elif args.action == "stop":
            with exclusive_lock(folder / "launch.lock"):
                atomic_json(supervisor / "STOP", {"requested": time.time()})
                atomic_json(output / "STOP", {"requested": time.time()})
            result = {"state": "stop_requested", "checkpoints_preserved": True}
        else:
            result = {"plan": plan, "supervisor_running": locked(supervisor / "supervisor.lock"),
                      "worker_running": locked(output / "worker.lock"), "stop_requested": (output / "STOP").exists() or (supervisor / "STOP").exists(),
                      "supervisor": read_json(supervisor / "supervisor-state.json") if (supervisor / "supervisor-state.json").exists() else None,
                      "run": read_json(output / "run-status.json") if (output / "run-status.json").exists() else None}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if result.get("passed") is False:
        raise SystemExit(2)
    if result.get("returncode"):
        raise SystemExit(result["returncode"])


if __name__ == "__main__":
    main()
