from __future__ import annotations

import json
import re
from datetime import datetime, timezone

import httpx

from hackwatch.models import Hackathon

URL = "https://devfolio.co/hackathons"
HEADERS = {"User-Agent": "hackwatch/0.1 (veille perso de hackathons ; usage non commercial)"}
_NEXT = re.compile(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', re.S)


def _dt(raw: str | None) -> datetime | None:
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).replace(tzinfo=None) if raw else None
    except ValueError:
        return None


def _lists(page: str) -> dict:
    m = _NEXT.search(page)
    if not m:
        raise ValueError("__NEXT_DATA__ introuvable sur la page Devfolio")
    queries = json.loads(m.group(1))["props"]["pageProps"]["dehydratedState"]["queries"]
    return next(q["state"]["data"] for q in queries if q["queryKey"] == "fetchAllHackathonTypes"
                or "open_hackathons" in (q["state"].get("data") or {}))


def parse(page: str, now: datetime | None = None) -> list[Hackathon]:
    """Listes open + upcoming. Le lieu des événements physiques n'est pas fourni par cette page :
    location reste vide (donc écarté par le filtre), seul le drapeau is_online fait foi."""
    now = now or datetime.now(timezone.utc).replace(tzinfo=None)
    data = _lists(page)
    out = []
    for h in data.get("open_hackathons", []) + data.get("upcoming_hackathons", []):
        reg_end = _dt((h.get("settings") or {}).get("reg_ends_at"))
        tz = h.get("timezone") or ""
        out.append(
            Hackathon(
                title=h["name"].strip(),
                url=f"https://{h['slug']}.devfolio.co/",
                source="devfolio",
                start=_dt(h.get("starts_at")),
                end=_dt(h.get("ends_at")),
                location="Online" if h.get("is_online") else "",
                is_online=bool(h.get("is_online")),
                tags=[t["theme"]["name"] for t in h.get("themes") or [] if t.get("theme")],
                tracks=[t["theme"]["name"] for t in h.get("themes") or [] if t.get("theme")],
                description=f"Hackathon Devfolio (fuseau {tz})" if tz else "Hackathon Devfolio",
                registration_open=bool(reg_end and reg_end > now),
            )
        )
    return out


def fetch(client: httpx.Client | None = None) -> list[Hackathon]:
    client = client or httpx.Client(headers=HEADERS, timeout=30)
    r = client.get(URL)
    r.raise_for_status()
    return parse(r.text)
