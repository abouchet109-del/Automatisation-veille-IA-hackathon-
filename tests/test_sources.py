import json
from pathlib import Path

from hackwatch import filters
from hackwatch.sources import ctftime, devpost, luma

FX = Path(__file__).parent / "fixtures"


def load(name):
    return json.loads((FX / name).read_text(encoding="utf-8"))


def test_devpost_parse():
    items = devpost.parse(load("devpost.json"))
    assert len(items) == 5
    h = items[0]
    assert h.source == "devpost" and h.url.endswith("/") and h.is_online
    assert h.start and h.end and h.start < h.end
    assert "<" not in h.prize


def test_devpost_dates():
    s, e = devpost.parse_dates("Oct 01 - 30, 2026")
    assert (s.month, s.day, e.month, e.day) == (10, 1, 10, 30)
    s, e = devpost.parse_dates("Aug 23, 2026 - Jan 02, 2027")
    assert (e.year, e.month) == (2027, 1)
    assert devpost.parse_dates("n/a") == (None, None)


def test_ctftime_parse():
    items = ctftime.parse(load("ctftime.json"))
    assert len(items) == 3
    assert items[0].is_online is False and items[1].is_online
    assert all(h.source == "ctftime" for h in items)


def test_filter():
    d = devpost.parse(load("devpost.json"))
    kept = [h for h in d if filters.keep(h)]
    assert all(h.is_online for h in kept) and kept


def test_luma_parse():
    fx = load("luma.json")
    items = luma.parse(fx["feed"], fx["details"])
    assert [h.title for h in items] == ["Horror Demo Night - Generathon #3 × Paris Creator Week"]
    h = items[0]
    assert h.source == "luma" and h.url.startswith("https://luma.com/") and not h.is_online
    assert "Paris" in h.location and filters.keep(h)
    assert "Generathon" in h.description and h.start and h.end


def test_luma_keywords_and_candidates():
    fx = load("luma.json")
    assert luma.candidates(fx["feed"]) == ["evt-cQE6HSoYAsRauAk"]
    # sans détail : le titre suffit encore
    assert len(luma.parse(fx["feed"])) == 1
    # mot-clé dans la description seulement
    feed = json.loads(json.dumps(fx["feed"]))
    other = feed["entries"][0]["event"]["api_id"]
    details = {other: {"description_mirror": {"type": "doc", "content": [
        {"type": "paragraph", "content": [{"type": "text", "text": "A 24h hackathon"}]}]}}}
    assert len(luma.parse(feed, details)) == 2


def test_luma_registration_closed():
    fx = load("luma.json")
    feed = json.loads(json.dumps(fx["feed"]))
    for e in feed["entries"]:
        e["registration_availability"] = "sold-out"
    assert not luma.parse(feed)[0].registration_open
