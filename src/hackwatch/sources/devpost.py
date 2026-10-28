from __future__ import annotations

import html
import re
from datetime import datetime

import httpx

from hackwatch.models import Hackathon

API = "https://devpost.com/api/hackathons"
HEADERS = {"User-Agent": "Mozilla/5.0 hackwatch"}
MAX_PAGES = 40


def parse_dates(text: str) -> tuple[datetime | None, datetime | None]:
    """'Oct 16 - Nov 20, 2026', 'Oct 01 - 30, 2026', 'Aug 23, 2026 - Jan 02, 2027'."""
    left, _, right = text.partition(" - ")
    m = re.search(r"(\d{4})\s*$", right)
    if not m:
        return None, None
    year_r = m.group(1)
    m = re.search(r"(\d{4})", left)
    year_l = m.group(1) if m else year_r
    try:
        start = datetime.strptime(f"{left.split(',')[0].strip()} {year_l}", "%b %d %Y")
        end_txt = right.split(",")[0].strip()
        if end_txt.isdigit():  # 'Oct 01 - 30, 2026' : même mois
            end_txt = f"{start.strftime('%b')} {end_txt}"
        end = datetime.strptime(f"{end_txt} {year_r}", "%b %d %Y")
        return start, end
    except ValueError:
        return None, None


def _prize(raw: str) -> str:
    amount = html.unescape(re.sub(r"<[^>]+>", "", raw or "")).strip()
    return amount if re.search(r"[1-9]", amount) else ""  # "$0", "€0", "₹ 0" : pas de prize


def parse(data: dict) -> list[Hackathon]:
    out = []
    for h in data.get("hackathons", []):
        loc = (h.get("displayed_location") or {}).get("location", "")
        start, end = parse_dates(h.get("submission_period_dates", ""))
        out.append(
            Hackathon(
                title=h["title"],
                url=h["url"].rstrip("/") + "/",
                source="devpost",
                start=start,
                end=end,
                location=loc,
                is_online=loc.lower() == "online",
                prize=_prize(h.get("prize_amount", "")),
                tags=[t["name"] for t in h.get("themes", [])],
                description=h.get("organization_name") or "",
                registration_open=h.get("open_state") in ("open", "upcoming")
                and not h.get("invite_only"),
            )
        )
    return out


def fetch(client: httpx.Client | None = None) -> list[Hackathon]:
    client = client or httpx.Client(headers=HEADERS, timeout=30)
    results: list[Hackathon] = []
    for page in range(1, MAX_PAGES + 1):
        r = client.get(API, params=[("status[]", "upcoming"), ("status[]", "open"), ("page", page)])
        r.raise_for_status()
        batch = parse(r.json())
        if not batch:
            break
        results += batch
    return results
