from __future__ import annotations

import json
import re
from datetime import datetime, timezone

import httpx

from hackwatch.models import Hackathon

URL = "https://mlh.io/seasons/2027/events"
HEADERS = {"User-Agent": "hackwatch/0.1 (veille perso de hackathons ; usage non commercial)"}
_PAGE = re.compile(r'<script data-page="app" type="application/json">(.*?)</script>', re.S)


def _dt(raw: str | None) -> datetime | None:
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).replace(tzinfo=None) if raw else None
    except ValueError:
        return None


def parse(page: str, now: datetime | None = None) -> list[Hackathon]:
    """Page Inertia de MLH (JSON embarqué). formatType : physical, hybrid_physical, digital.
    Seul « digital » est marqué en ligne ; un hybride garde son lieu brut (doute : pas en ligne)."""
    m = _PAGE.search(page)
    if not m:
        raise ValueError("données Inertia introuvables sur la page MLH")
    props = json.loads(m.group(1))["props"]
    now = now or datetime.now(timezone.utc).replace(tzinfo=None)
    out = []
    for e in props.get("upcomingEvents", []):
        fmt = e.get("formatType") or ""
        end = _dt(e.get("endsAt"))
        online = fmt == "digital"
        out.append(
            Hackathon(
                title=e["name"].strip(),
                url=(e.get("websiteUrl") or f"https://www.mlh.com/events/{e['slug']}").strip(),
                source="mlh",
                start=_dt(e.get("startsAt")),
                end=end,
                location="Online" if online else (e.get("location") or "").strip(),
                is_online=online,
                tags=["MLH", fmt] if fmt else ["MLH"],
                description=f"MLH hackathon {fmt.replace('_', ' ')} ({e.get('region') or '?'})".strip(),
                registration_open=e.get("status") != "ended" and bool(end and end > now),
            )
        )
    return out


def fetch(client: httpx.Client | None = None) -> list[Hackathon]:
    client = client or httpx.Client(headers=HEADERS, timeout=30, follow_redirects=True)
    r = client.get(URL)
    r.raise_for_status()
    return parse(r.text)
