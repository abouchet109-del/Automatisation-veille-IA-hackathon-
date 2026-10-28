from __future__ import annotations

import json
import re
from datetime import datetime, timezone

import httpx

from hackwatch.models import Hackathon

URL = "https://lablab.ai/ai-hackathons"
HEADERS = {"User-Agent": "hackwatch/0.1 (veille perso de hackathons ; usage non commercial)"}
_PUSH = re.compile(r'self\.__next_f\.push\(\[1,"(.*?)"\]\)</script>', re.S)
_OBJ = re.compile(r'\{"id":"[a-z0-9]{20,}","name":')
LOCATIONS = {"ONLINE": "Online", "HYBRID": "Hybrid (online + on-site)", "ONSITE": "On-site"}


def _dt(raw: str | None) -> datetime | None:
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).replace(tzinfo=None) if raw else None
    except ValueError:
        return None


def extract(page: str) -> list[dict]:
    """Objets hackathon (ceux qui ont startAt) du flux RSC Next.js embarqué dans la page."""
    flux = "".join(json.loads(f'"{c}"') for c in _PUSH.findall(page))
    dec = json.JSONDecoder()
    out = []
    for m in _OBJ.finditer(flux):
        try:
            obj, _ = dec.raw_decode(flux[m.start():])
        except ValueError:
            continue
        if "startAt" in obj:
            out.append(obj)
    return out


def parse(page: str, now: datetime | None = None) -> list[Hackathon]:
    """Hackathons à venir ou en cours avec inscription ouverte. Hybride : le lieu « Hybrid » laisse
    le filtre accepter la participation à distance ; is_online reste False (doute)."""
    now = now or datetime.now(timezone.utc).replace(tzinfo=None)
    out = []
    for o in extract(page):
        end = _dt(o.get("endAt"))
        kind = o.get("eventType") or ""
        out.append(
            Hackathon(
                title=o["name"].strip(),
                url=f"https://lablab.ai/event/{o['slug']}",
                source="lablab",
                start=_dt(o.get("startAt")),
                end=end,
                location=LOCATIONS.get(kind, kind.title()),
                is_online=kind == "ONLINE",
                description=" ".join((o.get("description") or "").split()),
                registration_open=bool(end and end > now and o.get("signupActive") and o.get("active")),
            )
        )
    return [h for h in out if h.registration_open]


def fetch(client: httpx.Client | None = None) -> list[Hackathon]:
    client = client or httpx.Client(headers=HEADERS, timeout=30)
    r = client.get(URL)
    r.raise_for_status()
    return parse(r.text)
