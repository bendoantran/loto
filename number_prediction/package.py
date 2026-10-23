"""Create a portable private deployment ZIP after verifying native model hashes."""
import argparse
import json
import zipfile
from pathlib import Path
if __package__ in (None, ""):
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from number_prediction.pipeline import Predictor
from number_prediction.data import canonical, digest


def main():
    from number_prediction import configure_cli
    configure_cli()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    model = Predictor.load(args.model)
    root = Path(__file__).resolve().parent
    files = {"number_prediction/" + p.name: p.read_bytes() for p in root.glob("*.py")}
    for pattern in ("*.json", "requirements*.txt", "README.md"):
        files.update({"number_prediction/" + p.name: p.read_bytes() for p in root.glob(pattern)})
    for p in args.model.rglob("*"):
        if p.is_file():
            files["model/" + str(p.relative_to(args.model)).replace("\\", "/")] = p.read_bytes()
    manifest = {"model_version": model.model_version, "files": {k: digest(v) for k, v in files.items()},
                "tested_environment": model.metadata, "privacy": "Private archive and model state; transfer through the owner's private channel."}
    with zipfile.ZipFile(args.out, "x", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, content in files.items():
            archive.writestr(name, content)
        archive.writestr("deployment-manifest.json", canonical(manifest))
    print(json.dumps({"model_version": model.model_version, "files": len(files), "archive_sha256": digest(args.out.read_bytes())}))


if __name__ == "__main__":
    main()
