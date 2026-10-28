from __future__ import annotations

import math
import re
from dataclasses import dataclass, field

from hackwatch.models import Hackathon

# Poids d'un mot-clé selon l'endroit où il apparaît, et selon qu'il est spécifique ou générique.
FIELD_WEIGHTS = {"titre": 1.0, "tags": 0.6, "description": 0.5}
GENERIC_WEIGHT = 0.4
SATURATION = 1.2  # axe = poids * (1 - exp(-raw / SATURATION)) : progressif, n'atteint jamais 1
MULTI_AXE_BONUS, MULTI_AXE_MIN, MULTI_AXE_MAX = 0.05, 0.2, 0.1

LOCAL_WORDS = ("paris", "france", "île-de-france", "ile-de-france")
BEGINNER_WORDS = ("beginner", "student", "étudiant")
EXCLUSION_PATTERNS = (
    r"\bUS residents only\b",
    r"\bU\.S\. residents only\b",
    r"\bmust be enrolled at\b",
    r"\bopen only to students of\b",
    r"\bcitizens only\b",
    r"\b(?:for|by) high ?schoolers\b",
    r"\bhigh ?schoolers across\b",
    r"\bhigh school students only\b",
    r"\bteens?\b",
)
# Qualification en ligne d'un CTF dont la finale a lieu sur place (presque toujours hors de France).
QUALIFIER_PATTERN = r"\b(?:qualif\w*|quals|prelims?)\b"
QUALIFIER_MALUS = 0.3
INR_TO_EUR = 0.011

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


def _token_regex(tok: str) -> str:
    """Mot en minuscules : insensible à la casse, pluriel en s accepté.
    Mot avec majuscules (acronyme, marque) : casse exacte ou tout en majuscules ("AI" ne matche pas "ai")."""
    if tok.islower():
        return f"(?i:{re.escape(tok)}s?)"
    variants = {re.escape(tok), re.escape(tok.upper())}
    plural = "s?" if tok.isupper() else ""
    return f"(?:{'|'.join(sorted(variants))}){plural}"


def keyword_regex(keyword: str) -> re.Pattern:
    body = r"[\s-]+".join(_token_regex(t) for t in keyword.split())
    return re.compile(rf"(?<!\w){body}(?!\w)")


def _has_word(word: str, text: str) -> bool:
    return re.search(rf"(?<!\w){re.escape(word)}(?!\w)", text, re.IGNORECASE) is not None


def parse_prize(text: str) -> float:
    """Meilleur effort : plus grand montant trouvé (€, $, ou ₹ converti en €), 0 sinon."""
    if not text:
        return 0.0
    inr = re.search(r"₹|\bINR\b|\bRs\.?\s", text)
    if not inr and not re.search(r"[€$]|\b(?:eur|usd)\b", text, re.IGNORECASE):
        return 0.0
    best = 0.0
    for m in re.finditer(r"(\d[\d\s.,  ]*)(\s*[kK]\b)?", text):
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
    return best * INR_TO_EUR if inr else best


def _axe_hits(h: Hackathon, cfg: dict) -> tuple[float, list[tuple[float, str]]]:
    fields = {"titre": h.title, "tags": " | ".join(h.tags), "description": h.description}
    hits = []
    for kws, kw_weight in ((cfg.get("mots_cles", []), 1.0), (cfg.get("mots_generiques", []), GENERIC_WEIGHT)):
        for kw in kws:
            rx = keyword_regex(kw)
            where = max((FIELD_WEIGHTS[f] for f, txt in fields.items() if rx.search(txt)), default=0.0)
            if where:
                hits.append((kw_weight * where, kw))
    hits.sort(reverse=True)
    return sum(w for w, _ in hits), hits


def score(h: Hackathon, profile: dict) -> Scored:
    axes = {}
    for axe, cfg in profile["objectifs"].items():
        raw, hits = _axe_hits(h, cfg)
        axes[axe] = (cfg["poids"] * (1 - math.exp(-raw / SATURATION)), hits)
    best_axe = max(axes, key=lambda a: axes[a][0])
    total, best_hits = axes[best_axe]
    raisons = []
    if best_hits:
        raisons.append(f"axe {AXE_LABELS.get(best_axe, best_axe)} : {', '.join(k for _, k in best_hits[:4])}")

    others = [a for a, (v, _) in axes.items() if a != best_axe and v >= MULTI_AXE_MIN]
    if others:
        total += min(MULTI_AXE_MAX, MULTI_AXE_BONUS * len(others))
        raisons.append("aussi " + ", ".join(AXE_LABELS.get(a, a) for a in others))
    loc = h.location.lower()
    if any(w in loc for w in LOCAL_WORDS):
        total += 0.15
        raisons.insert(1, f"lieu : {h.location}")
    prize = parse_prize(h.prize)
    if prize >= 1000:
        total += 0.1 if prize >= 10000 else 0.05
        raisons.append(f"prize {h.prize}")
    text = " ".join([h.title, *h.tags, h.description])
    if any(_has_word(w, text) for w in BEGINNER_WORDS):
        total += 0.05
    if any(re.search(p, f"{h.title} {h.description}", re.IGNORECASE) for p in EXCLUSION_PATTERNS):
        total -= 0.5
        raisons.insert(0, "restriction d'éligibilité")
    if re.search(QUALIFIER_PATTERN, h.title, re.IGNORECASE) and not any(w in loc for w in LOCAL_WORDS):
        total -= QUALIFIER_MALUS
        raisons.insert(0, "qualification, finale sur place à l'étranger")
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
