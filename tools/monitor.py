"""Quiet progress monitor; report new year completions, final completion, or failures."""
import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
import history
from tools.control import start


def check(root, notify=True, repair=True):
    progress_path = root / "progress.json"
    if not progress_path.exists():
        return None
    p = json.loads(progress_path.read_text(encoding="utf-8"))
    state_file = root / "monitor-state.json"
    old = json.loads(state_file.read_text(encoding="utf-8")) if state_file.exists() else {}
    completed = [y for y in p["years"] if y["remaining"] == 0]
    new = [y for y in completed if y["year"] not in old.get("reported_years", [])]
    running = history.lock_held(root)
    messages = []
    for year in new:
        messages.append(f"{year['year']}: {year['processed']}/{year['total']} dates; "
                        f"flagged {year['flagged']}, no draw {year.get('no_draw', 0)}, "
                        f"unavailable {year['unavailable']}, review {year['review']}.")
    if p["state"] == "finished" and not old.get("final_reported", False):
        messages.append(f"Full collection checked: {p['processed_days']}/{p['total_days']} dates. "
                        f"Flagged {p['flagged_days']}; cancelled {p.get('no_draw_days', 0)}; "
                        f"unavailable {p['unavailable_days']}; review {p['review_days']}. Run the full archive audit.")
    previous_review = old.get("reported_review_count", len(old.get("known_review_notes", {})))
    if p["review_days"] - previous_review >= 5:
        messages.append(f"Review dates increased to {p['review_days']}; inspect yearly issues.jsonl and original HTML for a sustained source/parser issue.")
        old["reported_review_count"] = p["review_days"]
    unfinished = p["processed_days"] < p["total_days"]
    failure_key = None
    if unfinished and not running and not (root / "STOP").exists() and p["state"] not in ("stopped", "finished"):
        failure_key = p["state"] + ":" + str(p.get("message"))
        if repair:
            try:
                messages.append("Unexpected worker exit; " + start(root))
            except Exception as error:
                if failure_key != old.get("reported_failure"):
                    messages.append("Worker needs attention: " + str(error))
        elif failure_key != old.get("reported_failure"):
            messages.append("Worker unexpectedly exited; inspect history.log before restarting.")
    text = "\n".join(messages)
    old.update(updated_at_utc=history.utcnow(), reported_years=sorted({y["year"] for y in completed} | set(old.get("reported_years", []))),
               final_reported=bool(old.get("final_reported")) or p["state"] == "finished",
               last_processed_days=p["processed_days"], last_worker_running=history.lock_held(root), reported_failure=failure_key)
    history.atomic_write(state_file, json.dumps(old, ensure_ascii=False, indent=2))
    if text:
        event = {"time_utc": history.utcnow(), "message": text}
        with (root / "monitor-events.jsonl").open("a", encoding="utf-8") as f:
            f.write(json.dumps(event, ensure_ascii=False) + "\n")
        if notify and shutil.which("notify-send"):
            subprocess.run(["notify-send", "loto archive", text], check=False)
        print(text)
    return text or None


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root", type=Path, default=REPO)
    p.add_argument("--no-notify", action="store_true")
    p.add_argument("--no-restart", action="store_true")
    args = p.parse_args()
    check(args.root.resolve(), not args.no_notify, not args.no_restart)


if __name__ == "__main__":
    main()
