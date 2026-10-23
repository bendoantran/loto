"""Full 100-class exports and compact ranked results, preserving label strings."""
import csv
import json
from pathlib import Path
import numpy as np


def export_forecasts(folder, records, top_k=10, unavailable=()):
    if not 1 <= top_k <= 100:
        raise ValueError("top-k must be between 1 and 100")
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=False)
    exported = []
    with (folder / "probabilities.csv").open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=["forecast_id", "region", "province", "prize", "date", "origin", "horizon", "day_index", "model_version", "training_cutoff", "latest_input_date", "forecast_timestamp", "baseline_status", "rank", "label", "probability"])
        writer.writeheader()
        for record in records:
            q, meta = record["query"], record["metadata"]
            order = np.argsort(-np.asarray(record["probabilities"]), kind="stable")
            ranks = [{"label": f"{k:02d}", "probability": record["probabilities"][k]} for k in order]
            exported.append({**record, "top_k": ranks[:top_k]})
            for rank, k in enumerate(order, 1):
                writer.writerow({"forecast_id": record["id"], **{key: q[key] for key in ("region", "province", "prize", "date", "origin", "horizon")},
                    **{key: meta[key] for key in ("day_index", "model_version", "latest_input_date", "forecast_timestamp", "baseline_status")},
                    "training_cutoff": meta["model_training_cutoff"], "rank": rank, "label": f"{k:02d}", "probability": record["probabilities"][k]})
    (folder / "forecasts.json").write_text(json.dumps({"forecasts": exported, "unavailable": list(unavailable)}, ensure_ascii=False, indent=2), encoding="utf-8")
