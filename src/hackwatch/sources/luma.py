from __future__ import annotations

import re
from datetime import datetime

import httpx

from hackwatch.models import Hackathon

# Flux public de la page https://luma.com/paris (même appel que le site, sans connexion).
FEED = "https://api.lu.ma/discover/get-paginated-events"
DETAIL = "https://api.lu.ma/event/get"
PARIS = "discplace-NdLrh1xJfeotJZC"
HEADERS = {"User-Agent": "hackwatch/0.1 (veille perso de hackathons ; usage non commercial)"}
KEYWORDS = re.compile(r"\b(hack|generathon|buildathon|datathon|ideathon|game[ -]?jam)", re.I)
MAX_DETAILS = 10  # une requête de plus par candidat (titre ou calendrier correspondant), plafonné


def _text(node) -> str:
    """Texte brut d'une description ProseMirror."""
    if isinstance(node, dict):
        if "text" in node:
            return node["text"]
        return " ".join(filter(None, (_text(c) for c in node.get("content", []))))
    if isinstance(node, list):
        return " ".join(filter(None, (_text(c) for c in node)))
    return ""


def _dt(raw: str | None) -> datetime | None:
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).replace(tzinfo=None) if raw else None
    except ValueError:
        return None


def _is_candidate(entry: dict) -> bool:
    name = entry["event"].get("name", "")
    return bool(KEYWORDS.search(name) or KEYWORDS.search((entry.get("calendar") or {}).get("name", "")))


def candidates(feed: dict) -> list[str]:
    return [e["event"]["api_id"] for e in feed.get("entries", []) if _is_candidate(e)]


def parse(feed: dict, details: dict[str, dict] | None = None) -> list[Hackathon]:
    """feed = réponse du flux Paris ; details = {api_id: réponse de /event/get} (optionnel)."""
    details = details or {}
    out = []
    for e in feed.get("entries", []):
        ev = e["event"]
        desc = _text((details.get(ev["api_id"]) or {}).get("description_mirror"))
        if not (_is_candidate(e) or KEYWORDS.search(desc)):
            continue
        geo = ev.get("geo_address_info") or {}
        online = ev.get("location_type") == "online"
        # Lieu : adresse complète pour que le filtre reconnaisse Paris / Île-de-France.
        loc = "Online" if online else (
            geo.get("full_address") or geo.get("city_state") or geo.get("address") or "")
        out.append(
            Hackathon(
                title=ev["name"],
                url=f"https://luma.com/{ev['url']}",
                source="luma",
                start=_dt(ev.get("start_at")),
                end=_dt(ev.get("end_at")),
                location=loc,
                is_online=online,
                description=" ".join(desc.split())[:1500] or (e.get("calendar") or {}).get("name", ""),
                registration_open=e.get("registration_availability") in ("open", "waitlist"),
            )
        )
    return out


def fetch(client: httpx.Client | None = None) -> list[Hackathon]:
    client = client or httpx.Client(headers=HEADERS, timeout=30)
    r = client.get(FEED, params={"discover_place_api_id": PARIS, "pagination_limit": 50})
    r.raise_for_status()
    feed = r.json()
    details = {}
    for api_id in candidates(feed)[:MAX_DETAILS]:
        d = client.get(DETAIL, params={"event_api_id": api_id})
        if d.status_code == 200:
            details[api_id] = d.json()
    return parse(feed, details)
