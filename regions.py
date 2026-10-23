"""Explicit source profiles and read-only checkpoint identity checks."""
import re
from datetime import date

PROFILES = {
    "xsmn": {"page": "https://xosodaiphat.com/xsmn-xo-so-mien-nam.html", "tokens": "XSMN|SXMN"},
    "xsmt": {"page": "https://xosodaiphat.com/xsmt-xo-so-mien-trung.html", "tokens": "XSMT|SXMT"},
}


def source_url(day, region="xsmn"):
    if region not in PROFILES:
        raise ValueError("Unknown source region: " + region)
    return f"https://xosodaiphat.com/{region}-" + date.fromisoformat(day).strftime("%d-%m-%Y") + ".html"


def dated_heading(heading, day, region):
    target = date.fromisoformat(day).strftime("%d/%m/%Y")
    return bool(re.search(rf"\b(?:{PROFILES[region]['tokens']})\s+{re.escape(target)}\b", heading, re.I))


def validate_checkpoint(db, region="xsmn", start=None, end=None):
    """Validate identity and URLs before a caller writes anything or downloads."""
    if region not in PROFILES:
        raise ValueError("Unknown source region: " + region)
    stored = dict(db.execute("SELECT key,value FROM settings"))
    if not stored:
        raise ValueError("Checkpoint has no saved settings")
    saved_region = stored.get("region", "xsmn")
    if saved_region != region:
        raise ValueError(f"Checkpoint region is {saved_region}, requested {region}; use a separate root")
    if (start and start != stored["start"]) or (end and end != stored["end"]):
        raise ValueError("Existing archive date range differs; use its saved range or a separate root")
    for day, url in db.execute("SELECT date,source_url FROM days"):
        if url != source_url(day, region):
            raise ValueError("Checkpoint contains a wrong-region/date source URL: " + day)
    return stored
