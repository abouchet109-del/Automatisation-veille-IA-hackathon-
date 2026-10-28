from __future__ import annotations

import re
import unicodedata

from hackwatch.models import Hackathon

# Seuls lieux de présentiel acceptés : Paris et l'Île-de-France (écrits sans accents, comparés sans accents).
IDF_WORDS = ("paris", "ile-de-france", "idf", "station f", "la defense", "saclay", "orsay", "palaiseau",
             "gif-sur-yvette", "cergy", "versailles", "nanterre", "boulogne", "issy", "saint-denis",
             "montreuil", "vincennes", "ivry", "creteil", "massy", "evry", "marne-la-vallee", "noisy",
             "rueil", "levallois", "neuilly", "puteaux", "courbevoie", "clichy")
# Homonymes hors Île-de-France.
NOT_IDF = ("boulogne-sur-mer", "montreuil-sur-mer", "reunion")
ONLINE_WORDS = ("online", "en ligne", "distanciel", "remote", "virtual", "hybrid", "hybride")


def normalize(text: str) -> str:
    """Minuscules, sans accents, tirets et espaces unifiés ("Île de France" -> "ile-de-france")."""
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()
    return re.sub(r"\s*-\s*", "-", re.sub(r"\s+", " ", text)).strip()


def _has_any(words: tuple[str, ...], text: str) -> bool:
    return any(re.search(rf"(?<!\w){re.escape(w)}(?!\w)", text) for w in words)


def is_idf(location: str) -> bool:
    loc = normalize(location)
    loc = loc.replace("ile de france", "ile-de-france")
    if _has_any(NOT_IDF, loc):
        return False
    return _has_any(IDF_WORDS, loc)


def is_online(h: Hackathon) -> bool:
    """En ligne, y compris un hybride indiqué comme participable à distance."""
    return h.is_online or _has_any(ONLINE_WORDS, normalize(h.location))


def keep(h: Hackathon) -> bool:
    """Inscriptions ouvertes ET (en ligne OU présentiel à Paris / Île-de-France)."""
    if not h.registration_open:
        return False
    return is_online(h) or is_idf(h.location)
