"""Re-scoring optionnel par Claude Haiku. Inerte sans ANTHROPIC_API_KEY (repli sur les règles)."""
from __future__ import annotations

import json
import os
import re
import sys

from dotenv import load_dotenv

from hackwatch.scoring import Scored

MODEL = "claude-haiku-5-5"
TOP_N = 30

PROMPT = """Tu évalues des hackathons pour un étudiant ESSEC / L3 maths, débutant en code, \
qui vise des postes d'AI/ML engineer. Seuls comptent le distanciel, Paris et la France.

Profil et axes (avec poids) :
{axes}

Pour chaque hackathon ci-dessous, donne un score de pertinence entre 0 et 1, l'axe le plus adapté \
(une clé parmi {keys}) et une phrase de raison courte en français.
Réponds uniquement avec un tableau JSON : [{{"id": 0, "score": 0.0, "axe": "...", "raison": "..."}}, ...]

Hackathons :
{items}"""


def enabled() -> bool:
    load_dotenv()
    return bool(os.environ.get("ANTHROPIC_API_KEY"))


def _parse(text: str) -> list[dict]:
    m = re.search(r"\[.*\]", text, re.DOTALL)
    return json.loads(m.group(0))


def rescore(scored: list[Scored], profile: dict, client=None) -> list[Scored]:
    """Remplace le score des 30 meilleurs candidats par celui du LLM ; en cas d'erreur, renvoie les règles."""
    if client is None:
        if not enabled():
            return scored
        try:
            import anthropic
            client = anthropic.Anthropic()
        except ImportError:
            print("[warn] ANTHROPIC_API_KEY présent mais SDK absent (pip install -e .[llm])", file=sys.stderr)
            return scored
    top = sorted(scored, key=lambda s: s.score, reverse=True)[:TOP_N]
    if not top:
        return scored
    axes = "\n".join(f"- {k} (poids {c['poids']}) : {c['description']}" for k, c in profile["objectifs"].items())
    items = "\n".join(
        f"{i}. {s.hackathon.title} | {s.hackathon.location or ('en ligne' if s.hackathon.is_online else '?')} "
        f"| prize: {s.hackathon.prize or '-'} | {s.hackathon.description[:300]}"
        for i, s in enumerate(top)
    )
    try:
        resp = client.messages.create(
            model=MODEL,
            max_tokens=8000,
            output_config={"effort": "low"},
            messages=[{"role": "user", "content": PROMPT.format(
                axes=axes, keys=", ".join(profile["objectifs"]), items=items)}],
        )
        text = "".join(b.text for b in resp.content if b.type == "text")
        results = {int(r["id"]): r for r in _parse(text)}
        out = {}
        for i, s in enumerate(top):
            r = results.get(i)
            if r is None:
                continue
            axe = r["axe"] if r["axe"] in profile["objectifs"] else s.axe
            out[id(s)] = Scored(s.hackathon, round(min(1.0, max(0.0, float(r["score"]))), 3),
                                axe, [str(r["raison"])])
    except Exception as e:  # toute erreur : on garde les règles
        print(f"[warn] LLM en échec, repli sur les règles : {e}", file=sys.stderr)
        return scored
    return [out.get(id(s), s) for s in scored]
