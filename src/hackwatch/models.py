from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class Hackathon:
    title: str
    url: str
    source: str
    start: datetime | None = None
    end: datetime | None = None
    location: str = ""
    is_online: bool = False
    prize: str = ""
    tags: list[str] = field(default_factory=list)
    description: str = ""
    registration_open: bool = True
    tracks: list[str] = field(default_factory=list)  # thèmes / défis, remplis par enrich pour les principaux
    resume: str = ""  # une phrase, remplie par enrich
