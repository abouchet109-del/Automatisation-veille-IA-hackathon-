from __future__ import annotations

from hackwatch.models import Hackathon

FRANCE_WORDS = ("paris", "france", "île-de-france", "ile-de-france", "lyon", "marseille",
                "toulouse", "bordeaux", "lille", "nantes", "grenoble", "sophia", "orsay")


def keep(h: Hackathon) -> bool:
    """Inscriptions ouvertes ET (en ligne, Paris ou France)."""
    if not h.registration_open:
        return False
    loc = h.location.lower()
    return h.is_online or any(w in loc for w in FRANCE_WORDS)
