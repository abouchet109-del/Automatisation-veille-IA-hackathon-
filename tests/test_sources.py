import json
from pathlib import Path

from hackwatch import filters
from hackwatch.sources import ctftime, devpost

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
