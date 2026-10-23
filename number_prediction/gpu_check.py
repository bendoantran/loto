"""Record actual CUDA readiness; refuse a GPU test when CUDA is unavailable."""
import argparse
import ctypes.util
import json
import platform
import shutil
import subprocess
from pathlib import Path
if __package__ in (None, ""):
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from number_prediction.recovery import atomic_json


def probe():
    import torch
    commands = {}
    for name, command in (("pci", ["lspci", "-nnk"]), ("nvidia_smi", ["nvidia-smi"])):
        if shutil.which(command[0]):
            result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=15)
            commands[name] = {"returncode": result.returncode, "output": result.stdout + result.stderr}
        else:
            commands[name] = {"unavailable": True}
    available = torch.cuda.is_available()
    result = {"platform": platform.platform(), "torch": str(torch.__version__), "torch_cuda": torch.version.cuda,
        "cuda_available": available, "device_count": torch.cuda.device_count(),
        "libcuda": ctypes.util.find_library("cuda"), "device_nodes": [str(p) for p in Path("/dev").glob("nvidia*")],
        "commands": commands, "gpu_fit_ran": False}
    if available:
        # A real CUDA allocation/kernel/synchronization, separate from a model fit.
        a = torch.arange(16, dtype=torch.float32, device="cuda").reshape(4, 4)
        result["cuda_kernel_sum"] = float((a @ a.T).sum().cpu())
        torch.cuda.synchronize()
        result["devices"] = [torch.cuda.get_device_name(i) for i in range(torch.cuda.device_count())]
    return result


def main():
    from number_prediction import configure_cli
    configure_cli()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--require-cuda", action="store_true")
    args = parser.parse_args()
    result = probe()
    if args.out:
        atomic_json(args.out, result)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if args.require_cuda and not result["cuda_available"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
