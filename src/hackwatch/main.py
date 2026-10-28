from __future__ import annotations

import argparse
import json
import sys

from hackwatch import filters, llm, notify, scoring
from hackwatch.models import Hackathon
from hackwatch.sources import ctftime, devpost
from hackwatch.scoring import Scored
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


def load_profile(path: str = "profile.json") -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def rank(items: list[Hackathon], profile: dict) -> list[Scored]:
    scored = [scoring.score(h, profile) for h in items]
    return llm.rescore(scored, profile)  # inerte sans ANTHROPIC_API_KEY


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="hackwatch")
    p.add_argument("--dry-run", action="store_true", help="afficher au lieu d'envoyer")
    p.add_argument("--all", action="store_true",
                   help="avec --dry-run : montrer aussi les éléments sous le seuil ou déjà envoyés (calibrage)")
    args = p.parse_args(argv)
    sys.stdout.reconfigure(encoding="utf-8")

    profile = load_profile()
    notif = profile["notification"]
    score_min = notif["score_min"]
    kept = [h for h in collect() if filters.keep(h)]
    store = Store()
    try:
        new = store.new_items(kept)  # n'écrit que first_seen, jamais sent_at
        pool = kept if args.dry_run and args.all else new
        scored = rank(pool, profile)
        to_send, below = scoring.select(scored, score_min, notif.get("max_total", 15),
                                        notif.get("max_ctftime", 3))
        if args.dry_run:
            print(f"{len(kept)} retenus, {len(new)} nouveaux, seuil {score_min} : "
                  f"{len(to_send)} à envoyer, {len(below)} en dessous/écartés")
            for s in to_send + (sorted(below, key=lambda s: -s.score) if args.all else []):
                mark = "*" if s in to_send else " "
                h = s.hackathon
                print(f"{mark} {s.score:.3f} [{s.axe}] [{h.source}] {h.title} | {h.location} | "
                      f"{h.prize or '-'}")
                print(f"      {'; '.join(s.raisons) or '-'} | {h.url}")
            return 0
        if not to_send:
            print(f"Rien de pertinent ({len(below)} sous le seuil).")
            return 0
        notify.send(to_send, len(below))
        store.mark_sent([s.hackathon for s in to_send])  # les sous-seuil restent non envoyés
        print(f"{len(to_send)} hackathons envoyés.")
        return 0
    finally:
        store.close()
