from __future__ import annotations

import time
from datetime import datetime

import httpx

from hackwatch.models import Hackathon

API = "https://ctftime.org/api/v1/events/"
HEADERS = {"User-Agent": "Mozilla/5.0 hackwatch"}


def parse(events: list[dict]) -> list[Hackathon]:
    out = []
    for e in events:
        online = not e.get("onsite", False)
        prizes = (e.get("prizes") or "").strip()
        out.append(
            Hackathon(
                title=e["title"],
                url=e.get("url") or e["ctftime_url"],
                source="ctftime",
                start=datetime.fromisoformat(e["start"]),
                end=datetime.fromisoformat(e["finish"]),
                location="Online" if online else e.get("location", ""),
                is_online=online,
                prize="" if prizes.upper() == "TBD" else prizes[:80],
                tags=["CTF", "cybersecurity", e.get("format", "")],
                description=(e.get("description") or "")[:500],
                registration_open=e.get("restrictions", "Open") == "Open",
            )
        )
    return out


def fetch(client: httpx.Client | None = None, days: int = 60) -> list[Hackathon]:
    client = client or httpx.Client(headers=HEADERS, timeout=30)
    now = int(time.time())
    r = client.get(API, params={"limit": 100, "start": now, "finish": now + days * 86400})
    r.raise_for_status()
    return parse(r.json())
