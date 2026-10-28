"""Tracks et résumé des hackathons principaux (sans LLM).

Appelé seulement sur les principaux, après la sélection : au plus MAX_PAGES pages téléchargées par
lancement. Toute erreur est avalée : l'enrichissement ne doit jamais empêcher l'envoi.
"""
from __future__ import annotations

import html as htmllib
import json
import re
import sys

import httpx

from hackwatch.models import Hackathon

HEADERS = {"User-Agent": "hackwatch/0.1 (veille perso de hackathons ; usage non commercial)"}
TIMEOUT = 10
MAX_PAGES = 15
MAX_TRACKS = 5
TRACK_LEN = 60
RESUME_LEN = 200

SECTION = re.compile(r"\b(?:tracks?|themes?|challenges?|categories|prizes?|d[ée]fis|th[ée]matiques?|cat[ée]gories)\b",
                     re.I)
# Intitulés sans information : classements, « sans thème », etc.
GENERIC = re.compile(
    r"^(?:(?:grand|first|second|third|1st|2nd|3rd|runner[- ]?up|overall|winner|winners|top)\b.*"
    r"|\d+(?:st|nd|rd|th)\b.*|prizes?|prize pool|no restrictions?|other|others|general|open[- ]ended"
    r"|honou?rable mention.*|participation.*|final presentation.*|awards?|all|none)$", re.I)
PLACE_SUFFIX = re.compile(r"\s*[-–:|]\s*(?:1st|2nd|3rd|\d+(?:st|nd|rd|th)|first|second|third)\b.*$", re.I)
RANK_SUFFIX = re.compile(r"\s*[-–]?\s*(?:winners?|runners?[- ]?up)$", re.I)


def plain(text: str | None) -> str:
    """Texte sans HTML ni sauts de ligne."""
    text = re.sub(r"<[^>]+>", " ", text or "")
    return re.sub(r"\s+", " ", htmllib.unescape(text)).strip()


def _cut(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    cut = text[:limit - 1]
    return cut[:cut.rfind(" ")].rstrip(" ,;:-–") + "…" if " " in cut else cut + "…"


def summarize(text: str | None, limit: int = RESUME_LEN) -> str:
    """Début du texte nettoyé, coupé à la fin d'une phrase si possible, sinon à un mot."""
    text = plain(text)
    if len(text) <= limit:
        return text
    head = text[:limit]
    ends = [m.end() for m in re.finditer(r"[.!?](?=\s|$)", head)]
    if ends and ends[-1] >= limit * 0.4:
        return head[:ends[-1]].strip()
    return _cut(text, limit)


def clean_tracks(items: list[str]) -> list[str]:
    """Nettoie, dédoublonne, écarte les intitulés génériques (classements, « Grand Prize »…)."""
    seen: set[str] = set()
    good: list[str] = []
    for raw in items:
        t = RANK_SUFFIX.sub("", PLACE_SUFFIX.sub("", plain(raw)))
        t = re.sub(r"^\W+", "", t)  # emojis et puces en tête
        t = re.sub(r"\s+:\s+[^:]*[€$£].*$", "", t)  # « Most viral : €300 en crédits… » -> « Most viral »
        t = re.sub(r"^\s*(?:\d+|[A-Za-z])\s*[-–.):]\s+", "", t).strip(" -–:·•")
        if not t or t.lower() in seen:
            continue
        seen.add(t.lower())
        if not GENERIC.match(t):
            good.append(_cut(t, TRACK_LEN))
    return good[:MAX_TRACKS]


# --- extraction par source -------------------------------------------------------------------------

def devpost_prizes(page: str) -> list[str]:
    """Noms des prix (souvent « Best Use of X ») ; les classements génériques sont filtrés ensuite."""
    return [plain(m) for m in re.findall(r'<div class="prize-title">(.*?)</div>\s*</h6>', page, re.S)]


def meta_description(page: str) -> str:
    m = (re.search(r'<meta[^>]+(?:property="og:description"|name="description")[^>]*content="([^"]*)"', page)
         or re.search(r'<meta[^>]+content="([^"]*)"[^>]*(?:property="og:description"|name="description")', page))
    return plain(m.group(1)) if m else ""


def html_sections(page: str) -> list[str]:
    """Intitulés (éléments de liste, sinon sous-titres) qui suivent un titre h1-h4 « tracks / themes /
    challenges / categories / prizes / défis… »."""
    page = re.sub(r"<(script|style)\b.*?</\1>", "", page, flags=re.S | re.I)
    heads = [(m.start(), m.end(), int(m.group(1)), plain(m.group(2)))
             for m in re.finditer(r"<h([1-4])\b[^>]*>(.*?)</h\1>", page, re.S | re.I)]
    for i, (_, end, level, title) in enumerate(heads):
        if not SECTION.search(title) or len(title) > 60:
            continue
        stop = next((s for s, _, lv, _ in heads[i + 1:] if lv <= level), len(page))
        block = page[end:min(stop, end + 8000)]
        items = [plain(x) for x in re.findall(r"<li\b[^>]*>(.*?)</li>", block, re.S | re.I)]
        if not items:
            items = [plain(x) for x in re.findall(r"<h[2-6]\b[^>]*>(.*?)</h[2-6]>", block, re.S | re.I)]
        items = [x for x in items if 2 < len(x) <= 120]
        if clean_tracks(items):
            return items
    return []


def prosemirror_sections(doc: dict | None) -> list[str]:
    """Même idée pour une description Luma (ProseMirror) : éléments de liste sous un titre pertinent."""
    blocks: list[tuple[str, str]] = []

    def walk(n):
        if not isinstance(n, dict):
            return
        t = n.get("type")
        if t == "heading":
            blocks.append(("h", _pm_text(n)))
        elif t == "list_item" or t == "listItem":
            blocks.append(("li", _pm_text(n)))
        else:
            for c in n.get("content", []) or []:
                walk(c)

    walk(doc)
    out: list[str] = []
    active = False
    for kind, text in blocks:
        if kind == "h":
            if out:
                break
            active = bool(SECTION.search(text))
        elif active:
            out.append(text)
    return out


def _pm_text(node) -> str:
    if isinstance(node, dict):
        if "text" in node:
            return node["text"]
        return " ".join(filter(None, (_pm_text(c) for c in node.get("content", []))))
    return ""


def luma_page(page: str) -> tuple[list[str], str]:
    m = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', page, re.S)
    data = json.loads(m.group(1))["props"]["pageProps"]["initialData"]["data"]
    doc = data.get("description_mirror")
    return prosemirror_sections(doc), plain(_pm_text(doc))


def agorize_categories(j: dict) -> list[str]:
    return [x["attributes"].get("name", "") for x in j.get("included", []) if x.get("type") == "categories"]


# --- orchestration ---------------------------------------------------------------------------------

def _get(client: httpx.Client, url: str) -> httpx.Response:
    r = client.get(url, follow_redirects=True)
    r.raise_for_status()
    return r


def enrich_one(h: Hackathon, client: httpx.Client) -> None:
    """Remplit h.tracks et h.resume. Les erreurs de réseau ou de format remontent à enrich()."""
    found: list[str] = []
    page_text = ""
    if h.source == "agorize":
        slug = h.url.rstrip("/").rsplit("/", 1)[-1]
        found = agorize_categories(_get(client, f"https://www.agorize.com/api/v2/challenges/{slug}").json())
    elif h.source == "luma":
        found, page_text = luma_page(_get(client, h.url).text)
    else:
        page = _get(client, h.url).text
        found = devpost_prizes(page) if "devpost.com" in h.url else []
        found = found or html_sections(page)
        page_text = meta_description(page)
    tracks = clean_tracks(found) or clean_tracks(h.tracks)  # sinon : thèmes donnés par la source
    h.tracks = tracks
    own = plain(h.description)
    h.resume = summarize(own if len(own) >= 60 else (page_text or own))
    if plain(h.resume).lower() == plain(h.title).lower():  # simple répétition du titre : inutile
        h.resume = ""


def enrich(items: list[Hackathon], client: httpx.Client | None = None, max_pages: int = MAX_PAGES) -> None:
    """Enrichit en place ; au plus max_pages téléchargements ; jamais d'exception."""
    own_client = client is None
    client = client or httpx.Client(headers=HEADERS, timeout=TIMEOUT)
    try:
        for n, h in enumerate(items):
            h.tracks = clean_tracks(h.tracks)
            if n >= max_pages:
                h.resume = h.resume or summarize(h.description)
                continue
            try:
                enrich_one(h, client)
            except Exception as e:  # échec réseau, page inattendue : on garde ce que la source a donné
                print(f"[warn] enrichissement de {h.title!r} impossible : {e}", file=sys.stderr)
                h.resume = h.resume or summarize(h.description)
    finally:
        if own_client:
            client.close()
