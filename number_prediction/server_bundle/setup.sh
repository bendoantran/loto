#!/usr/bin/env bash
set -euo pipefail
task_root="$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)"
cd -- "$task_root"
if [[ "$(uname -s)" != Linux || "$(uname -m)" != x86_64 ]]; then
  echo 'This bundle requires Linux x86_64 (glibc), such as Ubuntu 24.04/26.04.' >&2
  exit 2
fi
export PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1 PYTHONUTF8=1
unset PYTHONHOME PYTHONPATH
"$task_root/runtime/python/bin/python3" verify_bundle.py
if [[ -e .venv && ! -f .venv/loto-setup-complete.json ]]; then
  echo 'An incomplete environment exists. Preserve it by renaming .venv, then rerun setup.sh.' >&2
  exit 2
fi
if [[ ! -d .venv ]]; then
  task_free_kb="$(df -Pk . | awk 'END {print $4}')"
  if (( task_free_kb < 10485760 )); then
    echo 'Setup requires at least 10 GiB free in this directory.' >&2
    exit 2
  fi
  "$task_root/runtime/python/bin/python3" -m venv .venv
  .venv/bin/python -I -m pip --isolated install --no-index --no-cache-dir --only-binary=:all: --require-hashes --find-links wheelhouse -r wheel-lock.txt
  .venv/bin/python -I -m pip --isolated --no-cache-dir check
  # Reuse the OpenMP runtime already shipped with the pinned Torch wheel.
  # LightGBM can then load on a minimal host without installing libgomp system-wide.
  .venv/bin/python -I - <<'PY'
import pathlib
p = pathlib.Path.cwd()
lib = next((p / '.venv/lib/python3.12/site-packages/torch/lib').glob('libgomp*.so.1'))
link = p / 'native/lib/libgomp.so.1'
target = pathlib.Path('../..') / lib.relative_to(p)
if link.is_symlink():
    assert link.readlink() == target, 'Unexpected OpenMP runtime link; preserve and inspect it'
elif link.exists():
    raise RuntimeError('Unexpected OpenMP runtime file; preserve and inspect it')
else:
    link.symlink_to(target)
PY
  .venv/bin/python -I -c 'import json,pathlib,sys; pathlib.Path(".venv/loto-setup-complete.json").write_text(json.dumps({"python":sys.version,"root":str(pathlib.Path.cwd())}),encoding="utf-8")'
fi
./loto python -m pip --isolated --no-cache-dir check
echo 'Setup complete. Next: ./loto doctor --device cuda (or --device cpu). No training has started.'
