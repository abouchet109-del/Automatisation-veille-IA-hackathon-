from __future__ import annotations

import argparse
import sys

from hackwatch import filters, notify
from hackwatch.models import Hackathon
from hackwatch.sources import ctftime, devpost
from hackwatch.store import Store

SOURCES = {"devpost": devpost.fetch, "ctftime": ctftime.fetch}


def collect() -> list[Hackathon]:
    items: list[Hackathon] = []
    for name, fetch in SOURCES.items():
        try:
            items += fetch()
        except Exception as e:  # une source cassée ne bloque pas les autres
            print(f"[warn] source {name} en échec : {e}", file=sys.stderr)
    return items


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="hackwatch")
    p.add_argument("--dry-run", action="store_true", help="afficher au lieu d'envoyer")
    args = p.parse_args(argv)
    sys.stdout.reconfigure(encoding="utf-8")

    kept = [h for h in collect() if filters.keep(h)]
    store = Store()
    try:
        new = store.new_items(kept)  # n'écrit que first_seen, jamais sent_at
        if args.dry_run:
            print(f"{len(kept)} retenus, {len(new)} à envoyer")
            for h in new:
                print(f"- [{h.source}] {h.title} | {h.location} | {h.prize or '-'} | {h.url}")
            return 0
        if not new:
            print("Rien de nouveau.")
            return 0
        notify.send(new)
        store.mark_sent(new)
        print(f"{len(new)} nouveautés envoyées.")
        return 0
    finally:
        store.close()
