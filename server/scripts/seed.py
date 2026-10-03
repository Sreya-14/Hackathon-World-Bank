"""Seed a few SAMPLE listings around Wayanad so the map isn't empty before real hosts join.
They're marked seed=1 (shown as "Sample listing", contact disabled); the numbers are fake.

    .venv/bin/python -m scripts.seed
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

SERVER = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SERVER))

from app import db  # noqa: E402
from app.bot import snap_to_grid  # noqa: E402
from app.config import REPO, settings  # noqa: E402

SAMPLES = REPO / "app" / "public" / "data" / "sample-listings.json"


def main() -> None:
    db.db.init()
    features = json.loads(SAMPLES.read_text(encoding="utf-8"))["features"]
    for i, f in enumerate(features):
        p, (lon, lat) = f["properties"], f["geometry"]["coordinates"]
        if p["privacy"] == "area":
            lat, lon = snap_to_grid(lat, lon, settings.area_grid_m)
        listing = {
            "category": p["category"],
            "text": {lang: {"title": p["title"][lang], "description": p["description"][lang],
                            "price": p["price"] if lang == "en" else None, "hours": p["hours"] if lang == "en" else None,
                            "duration": None, "includes": [], "meeting_point": None} for lang in ("en", "de")},
            "machine_translated": [],
        }
        v = db.get_or_create_vendor(f"seed:+9100000001{i:02d}")
        checkin = (datetime.now(timezone.utc) - timedelta(days=p["days_since_checkin"] or 30)).isoformat(timespec="seconds")
        db.update_vendor(v["id"], state="LIVE", consented=1, live=1, hidden=0, seed=1, lat=lat, lon=lon,
                         privacy=p["privacy"], verified=int(p["verified"]), met_count=p["met_count"],
                         listing_json=json.dumps(listing, ensure_ascii=False), last_checkin=checkin)
    print(f"Seeded {len(features)} sample listings from {SAMPLES.name}.")


if __name__ == "__main__":
    main()
