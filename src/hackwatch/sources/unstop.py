from __future__ import annotations

import re
from datetime import datetime, timezone

import httpx

from hackwatch.models import Hackathon

API = "https://unstop.com/api/public/opportunity/search-result"
HEADERS = {"User-Agent": "hackwatch/0.1 (veille perso de hackathons ; usage non commercial)",
           "Accept": "application/json"}
MAX_PAGES = 5
PER_PAGE = 50
CURRENCIES = {"fa-rupee": "₹", "fa-dollar": "$", "fa-euro": "€"}


def _dt(raw: str | None) -> datetime | None:
    """ISO avec fuseau (+05:30) -> UTC naïf."""
    try:
        d = datetime.fromisoformat(raw) if raw else None
    except ValueError:
        return None
    if d is None:
        return None
    return d.astimezone(timezone.utc).replace(tzinfo=None) if d.tzinfo else d


def _prize(prizes: list[dict]) -> str:
    """Plus gros montant en espèces, avec sa devise ('₹ 35000'), sinon vide."""
    cash = [p for p in prizes or [] if p.get("cash")]
    if not cash:
        return ""
    best = max(cash, key=lambda p: p["cash"])
    sym = CURRENCIES.get(best.get("currency"), best.get("currencyCode") or "")
    return f"{sym} {best['cash']}".strip()


def _location(item: dict) -> str:
    if item.get("region") == "online":
        return "Online"
    addr = item.get("address_with_country_logo") or {}
    country = (addr.get("country") or {}).get("name", "")
    return ", ".join(p for p in (addr.get("address"), addr.get("city"), addr.get("state"), country) if p)


def parse(data: dict, now: datetime | None = None) -> list[Hackathon]:
    """Réponse de search-result. region : online / offline / hybrid. Seul « online » est marqué en
    ligne ; un hybride garde son lieu brut (doute : pas en ligne)."""
    now = now or datetime.now(timezone.utc).replace(tzinfo=None)
    out = []
    for x in data["data"]["data"]:
        reg_end = _dt((x.get("regnRequirements") or {}).get("end_regn_dt"))
        text = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", x.get("details") or "")).strip()
        org = (x.get("organisation") or {}).get("name", "")
        out.append(
            Hackathon(
                title=x["title"].strip(),
                url=x.get("seo_url") or f"https://unstop.com/{x['public_url']}",
                source="unstop",
                end=_dt(x.get("end_date")),
                location=_location(x),
                is_online=x.get("region") == "online",
                prize=_prize(x.get("prizes")),
                tags=[s["skill_name"] for s in x.get("required_skills") or [] if s.get("skill_name")][:8],
                description=f"{org}. {text}"[:600].strip(". "),
                registration_open=x.get("status") == "LIVE" and bool(x.get("regn_open"))
                and (reg_end is None or reg_end > now),
            )
        )
    return out


def fetch(client: httpx.Client | None = None) -> list[Hackathon]:
    client = client or httpx.Client(headers=HEADERS, timeout=30)
    results: list[Hackathon] = []
    for page in range(1, MAX_PAGES + 1):
        r = client.get(API, params={"opportunity": "hackathons", "oppstatus": "open",
                                    "per_page": PER_PAGE, "page": page})
        r.raise_for_status()
        data = r.json()
        batch = parse(data)
        if not batch:
            break
        results += batch
        if page >= data["data"].get("last_page", page):
            break
    return results
