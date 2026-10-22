#!/usr/bin/env bash
set -euo pipefail
task_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
exec watch --interval 2 --no-title cat -- "$task_root/PROGRESS.md"
