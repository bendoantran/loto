"""Create a new immutable modeling snapshot from configured canonical roots."""
import argparse
import json
from pathlib import Path
if __package__ in (None, ""):
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from number_prediction.data import make_snapshot


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path(__file__).with_name("config.json"))
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    config = json.loads(args.config.read_text())
    sources = [{**s, "root": str((args.config.resolve().parent / s["root"]).resolve())} for s in config["sources"]]
    manifest = make_snapshot(sources, args.out)
    print(json.dumps({k: manifest[k] for k in ("data_version", "rows", "decisions")}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
