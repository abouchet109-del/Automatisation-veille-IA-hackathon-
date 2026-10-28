from __future__ import annotations

import json
import re
from datetime import datetime, timezone

import httpx

from hackwatch.models import Hackathon

URL = "https://dev.events/hackathons/EU/FR"
HEADERS = {"User-Agent": "hackwatch/0.1 (veille perso de hackathons ; usage non commercial)"}
_LD = re.compile(r'<script type="application/ld\+json">(.*?)</script>', re.S)
HACK = re.compile(r"hack|\w+athon|game[ -]?jam", re.I)


def _dt(raw: str | None) -> datetime | None:
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).replace(tzinfo=None) if raw else None
    except ValueError:
        return None


def parse(page: str, now: datetime | None = None) -> list[Hackathon]:
    """JSON-LD schema.org de la page « hackathons accessibles depuis la France ». Les blocs
    (conférences, masterclass) dont ni le nom ni la description ne parlent de hackathon sont ignorés.
    endDate = fin de l'événement ou du dépôt : un événement terminé n'est plus ouvert."""
    now = now or datetime.now(timezone.utc).replace(tzinfo=None)
    out = []
    for block in _LD.findall(page):
        try:
            e = json.loads(block)
        except ValueError:
            continue
        if not isinstance(e, dict) or e.get("@type") != "EducationEvent":
            continue
        name, desc = e.get("name", "").strip(), e.get("description", "")
        if not (HACK.search(name) or HACK.search(desc)):
            continue
        end = _dt(e.get("endDate"))
        online = (e.get("eventAttendanceMode") or "").endswith("OnlineEventAttendanceMode")
        loc = (e.get("location") or {}).get("name") or (e.get("location") or {}).get("address") or ""
        out.append(
            Hackathon(
                title=name,
                url=e["url"],
                source="dev.events",
                start=_dt(e.get("startDate")),
                end=end,
                location="Online" if online else (loc if isinstance(loc, str) else ""),
                is_online=online,
                description=desc,
                registration_open=bool(end and end > now)
                and not (e.get("eventStatus") or "").endswith(("EventCancelled", "EventPostponed")),
            )
        )
    return out


def fetch(client: httpx.Client | None = None) -> list[Hackathon]:
    client = client or httpx.Client(headers=HEADERS, timeout=30)
    r = client.get(URL)
    r.raise_for_status()
    return parse(r.text)
