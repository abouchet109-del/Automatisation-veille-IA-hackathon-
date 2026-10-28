from __future__ import annotations

import re
import time
from datetime import datetime

import httpx

from hackwatch.models import Hackathon

API = "https://ctftime.org/api/v1/events/"
HEADERS = {"User-Agent": "Mozilla/5.0 hackwatch"}
PRIZE_MAX = 60
CURRENCY = re.compile(r"[$€£₹]|\b(?:USD|EUR|INR)\b", re.IGNORECASE)


def short_prize(raw: str) -> str:
    """Texte libre CTFtime -> une ligne d'environ 60 caractères ; vide s'il n'annonce aucun montant."""
    text = re.sub(r"\s+", " ", raw or "").strip()
    if not CURRENCY.search(text):
        return ""  # "TBA", "See https://…", récompenses non monétaires
    if len(text) <= PRIZE_MAX:
        return text
    return text[:PRIZE_MAX].rsplit(" ", 1)[0].rstrip(" ,;:+-(") + "…"


def parse(events: list[dict]) -> list[Hackathon]:
    out = []
    for e in events:
        online = not e.get("onsite", False)
        out.append(
            Hackathon(
                title=e["title"],
                url=e.get("url") or e["ctftime_url"],
                source="ctftime",
                start=datetime.fromisoformat(e["start"]),
                end=datetime.fromisoformat(e["finish"]),
                location="Online" if online else e.get("location", ""),
                is_online=online,
                prize=short_prize(e.get("prizes") or ""),
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
