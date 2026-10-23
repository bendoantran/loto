#!/usr/bin/env bash
set -euo pipefail
task_root="$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)"
cd -- "$task_root"
export PYTHONUTF8=1 PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1
unset PYTHONHOME PYTHONPATH
if [[ "$(uname -s)" != Linux || "$(uname -m)" != x86_64 ]]; then
  echo 'This setup targets Linux x86_64 with glibc.' >&2; exit 2
fi
mkdir -p .server-downloads
task_version="$(sha256sum server-transfer/source-manifest.json | cut -d' ' -f1)"
if [[ -d .server-runtime ]]; then
  if [[ ! -f .server-runtime/clone-source-version || "$(cat .server-runtime/clone-source-version)" != "$task_version" ]]; then
    echo 'Existing server runtime is incomplete or uses different source. Preserve/rename .server-runtime before setting up a new version. Do not move an active run.' >&2
    exit 2
  fi
  bash .server-runtime/setup.sh
  exit
fi
task_runtime=.server-downloads/python-runtime.tar.gz
task_runtime_sha=6d7521138fd33afddc1ccd08abb007d9a2829e38117c2576f9efdc0ec73ce772
if [[ ! -f "$task_runtime" ]]; then
  task_url='https://github.com/astral-sh/python-build-standalone/releases/download/20261021/cpython-3.12.15%2B20261021-x86_64-unknown-linux-gnu-install_only_stripped.tar.gz'
  if command -v curl >/dev/null; then
    curl -fL --retry 3 -o "$task_runtime.partial" "$task_url"
  elif command -v wget >/dev/null; then
    wget -O "$task_runtime.partial" "$task_url"
  else
    echo 'Need curl or wget to download user-space Python; alternatively use the offline bundle.' >&2; exit 2
  fi
  mv -- "$task_runtime.partial" "$task_runtime"
fi
printf '%s  %s\n' "$task_runtime_sha" "$task_runtime" | sha256sum -c -
if [[ ! -x .server-downloads/runtime/python/bin/python3 ]]; then
  mkdir -p .server-downloads/runtime
  tar -xzf "$task_runtime" -C .server-downloads/runtime
fi
task_python="$task_root/.server-downloads/runtime/python/bin/python3"
"$task_python" - <<'PY'
import hashlib,json,pathlib
root=pathlib.Path.cwd()
for name, expected in json.loads((root/'server-transfer/source-manifest.json').read_text(encoding='utf-8')).items():
    with (root/name).open('rb') as stream:
        if hashlib.file_digest(stream,'sha256').hexdigest()!=expected:
            raise SystemExit('Clone source changed: '+name+'; preserve the installed version and use a clean checkout')
PY
"$task_python" tools/restore_prediction_transfer.py server-transfer/snapshot-manifest.json .server-downloads/payload
mkdir -p .server-downloads/wheelhouse
"$task_python" -I -m pip --isolated download --no-cache-dir --only-binary=:all: --require-hashes \
  --index-url https://pypi.org/simple --extra-index-url https://download.pytorch.org/whl/cu124 \
  --dest .server-downloads/wheelhouse -r server-transfer/wheel-lock.txt
"$task_python" number_prediction/build_server_bundle.py --out .server-runtime \
  --runtime "$task_runtime" --wheelhouse .server-downloads/wheelhouse \
  --data .server-downloads/payload/post-xsmt-20261022T1936 \
  --opencl .server-downloads/payload/native/libOpenCL.so.1 \
  --opencl-license .server-downloads/payload/native/OPENCL-COPYING
printf '%s\n' "$task_version" > .server-runtime/clone-source-version
bash .server-runtime/setup.sh
echo 'Ready: ./loto doctor --device cuda, then ./loto pilot --device cuda. No training has started.'
