"""Versioned prospective schedules, never inferred from observed historical draws."""
import json
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo


class Schedule:
    def __init__(self, path=None):
        self.data = json.loads(Path(path or Path(__file__).with_name("schedules.json")).read_text(encoding="utf-8"))

    def resolve(self, province, region=None):
        matches = [r for r, spec in self.data["regions"].items() if any(province in day for day in spec["weekdays"]) and (region is None or region == r)]
        if len(matches) != 1:
            raise ValueError("Unknown/ambiguous province or unsupported alias; choose a verified identity")
        return matches[0]

    def dates(self, province, forecast_time, region=None, scope="next"):
        if scope not in ("next", "five-day"):
            raise ValueError("Unknown forecast scope")
        region = self.resolve(province, region)
        if forecast_time.tzinfo is None:
            raise ValueError("Forecast timestamp must include its timezone")
        local = forecast_time.astimezone(ZoneInfo(self.data["timezone"]))
        spec = self.data["regions"][region]
        result = []
        days = 5 if scope == "five-day" else 8
        for offset in range(days):
            day = local.date() + timedelta(days=offset)
            if province not in spec["weekdays"][day.weekday()]:
                continue
            start = datetime.fromisoformat(f"{day}T{spec['draw_start']}").replace(tzinfo=local.tzinfo)
            if start <= local:
                continue
            if not self.data["valid_from"] <= str(day) <= self.data["valid_through"]:
                raise ValueError("Schedule not verified for requested date; refresh the versioned schedule")
            result.append({"date": str(day), "region": region, "province": province,
                           "origin": str(local.date()), "horizon": offset + 1,
                           "draw_start": start.isoformat(), "schedule_version": self.data["version"]})
            if scope == "next":
                break
        return result
