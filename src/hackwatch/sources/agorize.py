from __future__ import annotations

from datetime import datetime, timezone

import httpx

from hackwatch.models import Hackathon

# API JSON publique utilisée par la page /fr/challenges (aucune connexion requise).
API = "https://www.agorize.com/api/v2/challenges"
HEADERS = {"User-Agent": "hackwatch/0.1 (veille perso de hackathons ; usage non commercial)"}
MAX_PAGES = 3
PER_PAGE = 100


def _dt(raw: str | None) -> datetime | None:
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).replace(tzinfo=None) if raw else None
    except ValueError:
        return None


def _is_open(a: dict, now: datetime) -> bool:
    deadline = _dt(a.get("current_deadline"))
    team = _dt(a.get("create_or_join_team_allowed_until"))
    return bool(deadline and deadline > now and (team is None or team > now))


def parse(data: dict, now: datetime | None = None) -> list[Hackathon]:
    """Challenges ouverts seulement. L'API n'a pas de lieu : les challenges Agorize se déposent sur la
    plateforme, donc marqués en ligne (les éventuelles finales physiques ne sont pas décrites)."""
    now = now or datetime.now(timezone.utc).replace(tzinfo=None)
    out = []
    for item in data.get("data", []):
        a = item["attributes"]
        if not _is_open(a, now):
            continue
        desc = " ".join(p.strip() for p in (a.get("client"), a.get("summary"), a.get("awards_catchline"))
                        if p and p.strip())
        out.append(
            Hackathon(
                title=" ".join((a.get("name") or "").split()),
                url=f"https://www.agorize.com/fr/challenges/{a['slug']}",
                source="agorize",
                start=_dt(a.get("start_at")),
                end=_dt(a.get("current_deadline")),
                location="Online (plateforme Agorize)",
                is_online=True,
                description=desc,
                registration_open=True,
            )
        )
    return out


def fetch(client: httpx.Client | None = None) -> list[Hackathon]:
    client = client or httpx.Client(headers=HEADERS, timeout=30)
    results: list[Hackathon] = []
    for page in range(1, MAX_PAGES + 1):
        r = client.get(API, params={"page": page, "per": PER_PAGE, "q[s]": "start_at desc"})
        r.raise_for_status()
        data = r.json()
        batch = parse(data)
        results += batch
        if not data.get("data") or (page > 1 and not batch):
            break
    return results
