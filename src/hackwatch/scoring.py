from __future__ import annotations

import re
from dataclasses import dataclass, field

from hackwatch.models import Hackathon

LOCAL_WORDS = ("paris", "france", "île-de-france", "ile-de-france")
BEGINNER_WORDS = ("beginner", "student", "étudiant")
EXCLUSION_PATTERNS = (
    r"\bUS residents only\b",
    r"\bU\.S\. residents only\b",
    r"\bmust be enrolled at\b",
    r"\bopen only to students of\b",
    r"\bcitizens only\b",
)
AXE_LABELS = {
    "ia_technique": "IA technique",
    "gains_entrepreneurial": "gains entrepreneuriaux",
    "opportunites_pro": "opportunités pro",
    "deeptech": "deeptech",
}


@dataclass
class Scored:
    hackathon: Hackathon
    score: float
    axe: str
    raisons: list[str] = field(default_factory=list)


def _has_word(word: str, text: str) -> bool:
    return re.search(rf"(?<!\w){re.escape(word)}(?!\w)", text, re.IGNORECASE) is not None


def parse_prize(text: str) -> float:
    """Meilleur effort : plus grand montant trouvé dans le texte (€ ou $), 0 sinon."""
    if not text or not re.search(r"[€$]|eur|usd", text, re.IGNORECASE):
        return 0.0
    best = 0.0
    for m in re.finditer(r"(\d[\d\s.,  ]*)(\s*[kK])?", text):
        raw = re.sub(r"[\s  ]", "", m.group(1))
        raw = re.sub(r"[.,](?=\d{3}(?:\D|$))", "", raw)  # séparateurs de milliers
        raw = raw.replace(",", ".").strip(".")
        try:
            val = float(raw)
        except ValueError:
            continue
        if m.group(2):
            val *= 1000
        best = max(best, val)
    return best


def score(h: Hackathon, profile: dict) -> Scored:
    text = " ".join([h.title, *h.tags, h.description])
    best_axe, best_val, best_hits = "", -1.0, []
    for axe, cfg in profile["objectifs"].items():
        hits = [k for k in cfg["mots_cles"] if _has_word(k, text)]
        val = min(1.0, len(hits) / 2) * cfg["poids"]
        if val > best_val:
            best_axe, best_val, best_hits = axe, val, hits
    total = max(best_val, 0.0)
    raisons = []
    if best_hits:
        raisons.append(f"axe {AXE_LABELS.get(best_axe, best_axe)} : {', '.join(best_hits[:4])}")

    loc = h.location.lower()
    if any(w in loc for w in LOCAL_WORDS):
        total += 0.15
        raisons.append(f"lieu : {h.location}")
    prize = parse_prize(h.prize)
    if prize >= 1000:
        total += 0.1
        raisons.append(f"prize {h.prize}")
    if any(_has_word(w, text) for w in BEGINNER_WORDS):
        total += 0.05
        raisons.append("accessible aux étudiants/débutants")
    if any(re.search(p, h.description, re.IGNORECASE) for p in EXCLUSION_PATTERNS):
        total -= 0.5
        raisons.append("restriction d'éligibilité")
    return Scored(h, round(min(1.0, max(0.0, total)), 3), best_axe, raisons[:3])


def select(scored: list[Scored], score_min: float, max_total: int = 15,
           max_ctftime: int = 3) -> tuple[list[Scored], list[Scored]]:
    """Renvoie (retenus, sous le seuil ou écartés par les plafonds). Seuls les retenus sont à marquer envoyés."""
    ranked = sorted(scored, key=lambda s: (s.score, parse_prize(s.hackathon.prize)), reverse=True)
    kept, rest, ctf = [], [], 0
    for s in ranked:
        if s.score < score_min or len(kept) >= max_total:
            rest.append(s)
        elif s.hackathon.source == "ctftime" and ctf >= max_ctftime:
            rest.append(s)
        else:
            ctf += s.hackathon.source == "ctftime"
            kept.append(s)
    return kept, rest
