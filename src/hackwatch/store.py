from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

from hackwatch.models import Hackathon

SCHEMA = """
CREATE TABLE IF NOT EXISTS hackathons (
    url TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    source TEXT NOT NULL,
    first_seen TEXT NOT NULL,
    sent_at TEXT
)"""


class Store:
    def __init__(self, path: str = "hackwatch.db"):
        self.db = sqlite3.connect(path)
        self.db.execute(SCHEMA)

    def new_items(self, items: list[Hackathon]) -> list[Hackathon]:
        """Enregistre tout, renvoie ceux jamais envoyés (dédoublonnés par URL)."""
        now = datetime.now(timezone.utc).isoformat()
        for h in items:
            self.db.execute(
                "INSERT OR IGNORE INTO hackathons (url, title, source, first_seen) VALUES (?,?,?,?)",
                (h.url, h.title, h.source, now),
            )
        self.db.commit()
        seen, out = set(), []
        for h in items:
            if h.url in seen:
                continue
            seen.add(h.url)
            row = self.db.execute("SELECT sent_at FROM hackathons WHERE url=?", (h.url,)).fetchone()
            if row and row[0] is None:
                out.append(h)
        return out

    def mark_sent(self, items: list[Hackathon]) -> None:
        now = datetime.now(timezone.utc).isoformat()
        self.db.executemany("UPDATE hackathons SET sent_at=? WHERE url=?", [(now, h.url) for h in items])
        self.db.commit()

    def close(self) -> None:
        self.db.close()
