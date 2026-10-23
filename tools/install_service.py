"""Generate Kubuntu systemd user units; does not start downloads or run sudo."""
import argparse
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


def quoted(value):
    return '"' + str(value).replace("\\", "\\\\").replace('"', '\\"').replace("%", "%%") + '"'


def units(repo, root, python, region="xsmn"):
    if region not in ("xsmn", "xsmt"):
        raise ValueError("Unknown region")
    suffix = "" if region == "xsmn" else " --region xsmt"
    prefix = "loto" if region == "xsmn" else "loto-xsmt"
    # WorkingDirectory= is a single path directive, not an Exec command line:
    # quotes are literal path characters here. Spaces need no shell quoting.
    directory = str(root).replace("%", "%%")
    if not root.is_absolute() or any(c in directory for c in ('\n', '\r')):
        raise ValueError("Service root must be an absolute single-line path")
    control, monitor = repo / "tools/control.py", repo / "tools/monitor.py"
    collector = f'''[Unit]
Description=loto resumable year-by-year history collector

[Service]
Type=simple
WorkingDirectory={directory}
Environment=PYTHONUTF8=1
ExecCondition={quoted(python)} {quoted(control)} should-run --root {quoted(root)}{suffix}
ExecStart={quoted(python)} -u {quoted(repo / "history.py")} run --root {quoted(root)}{suffix}
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
WorkingDirectory={directory}
Environment=PYTHONUTF8=1
ExecStart={quoted(python)} {quoted(monitor)} --root {quoted(root)}{suffix}
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
    return {prefix + "-history.service": collector, prefix + "-monitor.service": watcher, prefix + "-monitor.timer": timer}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root", type=Path, default=REPO)
    p.add_argument("--region", choices=["xsmn", "xsmt"], default="xsmn")
    p.add_argument("--output", type=Path)
    p.add_argument("--replace", action="store_true")
    args = p.parse_args()
    if os.name == "nt" and args.output is None:
        p.error("Run on Kubuntu, or use --output to generate reviewable units only")
    root = args.root.resolve()
    destination = args.output or Path.home() / ".config/systemd/user"
    generated = units(REPO, root, Path(sys.executable).resolve(), args.region)
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
    prefix = "loto" if args.region == "xsmn" else "loto-xsmt"
    print(f"Enable reboot/login resume: systemctl --user enable {prefix}-history.service")
    print(f"Enable quiet monitoring: systemctl --user enable --now {prefix}-monitor.timer")


if __name__ == "__main__":
    main()
