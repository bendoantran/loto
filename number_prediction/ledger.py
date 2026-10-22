"""Append-only local forecast and outcome-revision evidence; no collector writes."""
import json
import sqlite3
from datetime import datetime
from pathlib import Path
from .baselines import probabilities
from .data import canonical, digest


class ForecastLedger:
    def __init__(self, path):
        self.db = sqlite3.connect(Path(path))
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA synchronous=FULL")
        self.db.executescript('''
            CREATE TABLE IF NOT EXISTS forecasts(id TEXT PRIMARY KEY, payload TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS scores(forecast_id TEXT NOT NULL, revision TEXT NOT NULL,
                payload TEXT NOT NULL, PRIMARY KEY(forecast_id,revision));
            CREATE TRIGGER IF NOT EXISTS immutable_forecasts_update BEFORE UPDATE ON forecasts BEGIN SELECT RAISE(ABORT,'immutable forecast'); END;
            CREATE TRIGGER IF NOT EXISTS immutable_forecasts_delete BEFORE DELETE ON forecasts BEGIN SELECT RAISE(ABORT,'immutable forecast'); END;
            CREATE TRIGGER IF NOT EXISTS immutable_scores_update BEFORE UPDATE ON scores BEGIN SELECT RAISE(ABORT,'immutable score'); END;
            CREATE TRIGGER IF NOT EXISTS immutable_scores_delete BEFORE DELETE ON scores BEGIN SELECT RAISE(ABORT,'immutable score'); END;
        ''')

    def record(self, query, p, metadata):
        p = probabilities([p])[0]
        timestamp = datetime.fromisoformat(metadata["forecast_timestamp"])
        if timestamp.tzinfo is None:
            raise ValueError("Forecast timestamp requires a timezone")
        if not metadata.get("simulated"):
            if timestamp >= datetime.fromisoformat(query["draw_start"]):
                raise ValueError("Prospective forecast must precede draw start")
            from zoneinfo import ZoneInfo
            if timestamp.astimezone(ZoneInfo("Asia/Ho_Chi_Minh")).date().isoformat() < query["origin"]:
                raise ValueError("Origin is later than timestamp")
        if metadata["latest_input_date"] is not None and metadata["latest_input_date"] >= query["origin"]:
            raise ValueError("Input cutoff crosses date boundary")
        key = {k: query[k] for k in ("region", "province", "date", "origin", "prize", "horizon")}
        key.update(model_version=metadata["model_version"], simulated=bool(metadata.get("simulated")))
        forecast_id = digest(canonical(key))
        record = {"id": forecast_id, "query": query, "metadata": metadata, "probabilities": p.tolist()}
        with self.db:
            self.db.execute("INSERT INTO forecasts VALUES (?,?)", (forecast_id, canonical(record).decode()))
        return record

    def score(self, forecast_id, label, revision, validated=True):
        if not validated or not revision or not 0 <= label < 100:
            raise ValueError("Scoring requires a validated class and a source revision/hash")
        row = self.db.execute("SELECT payload FROM forecasts WHERE id=?", (forecast_id,)).fetchone()
        if row is None:
            raise ValueError("Record forecast before revealing/scoring outcome")
        record = json.loads(row[0])
        from .evaluation import metrics
        result = {"label": f"{label:02d}", "source_revision": revision,
                  "metrics": metrics([label], [record["probabilities"]])}
        with self.db:
            self.db.execute("INSERT INTO scores VALUES (?,?,?)", (forecast_id, revision, canonical(result).decode()))
        return result

    def close(self):
        self.db.close()
