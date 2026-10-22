#!/usr/bin/env bash
set -euo pipefail
task_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
if [[ "${1:-}" == "--service" ]]; then
  if [[ -e "$task_root/STOP" ]]; then rm -- "$task_root/STOP"; fi
  systemctl --user start loto-history.service
else
  exec python3 "$task_root/tools/control.py" start --root "$task_root"
fi
