"""Generate Kubuntu systemd user units; does not start downloads or run sudo."""
import argparse
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


def quoted(value):
    return '"' + str(value).replace("\\", "\\\\").replace('"', '\\"').replace("%", "%%") + '"'


def units(repo, root, python):
    control, monitor = repo / "tools/control.py", repo / "tools/monitor.py"
    collector = f'''[Unit]
Description=loto resumable year-by-year history collector

[Service]
Type=simple
WorkingDirectory={quoted(root)}
Environment=PYTHONUTF8=1
ExecCondition={quoted(python)} {quoted(control)} should-run --root {quoted(root)}
ExecStart={quoted(python)} -u {quoted(repo / "history.py")} run --root {quoted(root)}
TimeoutStopSec=45
KillSignal=SIGINT
Restart=on-failure
RestartSec=60
UMask=0077
# Shutdown and crash recovery must not create a durable user STOP marker.
# Use stop-history.sh when the user intentionally wants collection to stay stopped.

[Install]
WantedBy=default.target
'''
    watcher = f'''[Unit]
Description=loto quiet progress check

[Service]
Type=oneshot
WorkingDirectory={quoted(root)}
Environment=PYTHONUTF8=1
ExecStart={quoted(python)} {quoted(monitor)} --root {quoted(root)}
UMask=0077
'''
    timer = '''[Unit]
Description=Check loto progress every 30 minutes

[Timer]
OnBootSec=5min
OnUnitActiveSec=30min
Persistent=true

[Install]
WantedBy=timers.target
'''
    return {"loto-history.service": collector, "loto-monitor.service": watcher, "loto-monitor.timer": timer}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root", type=Path, default=REPO)
    p.add_argument("--output", type=Path)
    p.add_argument("--replace", action="store_true")
    args = p.parse_args()
    if os.name == "nt" and args.output is None:
        p.error("Run on Kubuntu, or use --output to generate reviewable units only")
    root = args.root.resolve()
    destination = args.output or Path.home() / ".config/systemd/user"
    generated = units(REPO, root, Path(sys.executable).resolve())
    if not args.replace:
        for name in generated:
            if (destination / name).exists():
                raise SystemExit("Existing unit left unchanged; inspect it before using --replace: " + name)
    destination.mkdir(parents=True, exist_ok=True)
    for name, text in generated.items():
        path = destination / name
        if path.exists():
            path.with_suffix(path.suffix + ".bak").write_bytes(path.read_bytes())
        path.write_text(text, encoding="utf-8", newline="\n")
    print("Units written to " + str(destination))
    print("Review, then run: systemctl --user daemon-reload")
    print("Enable reboot/login resume: systemctl --user enable loto-history.service")
    print("Enable quiet monitoring: systemctl --user enable --now loto-monitor.timer")


if __name__ == "__main__":
    main()
