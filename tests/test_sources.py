import json
from datetime import datetime
from pathlib import Path

from hackwatch import filters
from hackwatch.sources import agorize, ctftime, devevents, devfolio, devpost, lablab, luma, mlh, unstop

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


def test_agorize_parse_open_only():
    fx = load("agorize.json")
    assert len(fx["data"]) == 6
    items = agorize.parse(fx, now=datetime(2026, 10, 28))
    assert len(items) == 5  # le challenge clos est exclu
    h = items[0]
    assert h.source == "agorize" and h.url.startswith("https://www.agorize.com/fr/challenges/")
    assert h.is_online and h.registration_open and h.end > h.start
    assert all(filters.keep(x) for x in items)


def test_agorize_deadline_passed():
    fx = load("agorize.json")
    assert agorize.parse(fx, now=datetime(2027, 6, 1)) == []


def test_lablab_parse():
    page = (FX / "lablab.html").read_text(encoding="utf-8")
    assert len(lablab.extract(page)) == 4
    items = lablab.parse(page, now=datetime(2026, 10, 28))
    assert [h.title for h in items] == ["AMD AI League", "Vultr: Agent Rush Hackathon"]
    amd, vultr = items
    assert amd.is_online and amd.location == "Online" and amd.url == "https://lablab.ai/event/amd-lablab-ai-academy-challenge"
    # hybride : pas marqué « en ligne » d'office, mais le lieu « Hybrid » passe le filtre
    assert not vultr.is_online and "Hybrid" in vultr.location
    assert all(filters.keep(h) for h in items)


def test_lablab_all_past():
    page = (FX / "lablab.html").read_text(encoding="utf-8")
    assert lablab.parse(page, now=datetime(2027, 6, 1)) == []


def test_mlh_parse():
    page = (FX / "mlh.html").read_text(encoding="utf-8")
    items = mlh.parse(page, now=datetime(2026, 10, 28))
    assert len(items) == 3  # les événements passés (pastEvents) sont ignorés
    assert all(h.source == "mlh" and h.registration_open and not h.is_online for h in items)
    assert all(h.location and "MLH" in h.tags for h in items)
    assert not any(filters.keep(h) for h in items)  # aucun à Paris ni en ligne


def test_mlh_digital_and_ended():
    page = (FX / "mlh.html").read_text(encoding="utf-8")
    page = page.replace('"formatType": "physical"', '"formatType": "digital"')
    digital = mlh.parse(page, now=datetime(2026, 10, 28))
    assert any(h.is_online and h.location == "Online" and filters.keep(h) for h in digital)
    assert not any(h.registration_open for h in mlh.parse(page, now=datetime(2027, 6, 1)))


def test_devfolio_parse():
    page = (FX / "devfolio.html").read_text(encoding="utf-8")
    items = devfolio.parse(page, now=datetime(2026, 10, 28))
    assert len(items) == 4  # open (3) + upcoming (1), pas past
    assert all(h.url.endswith(".devfolio.co/") and h.source == "devfolio" for h in items)
    assert sum(h.is_online for h in items) == 1
    kept = [h for h in items if filters.keep(h)]
    assert len(kept) == 1 and kept[0].is_online  # lieu physique inconnu : écarté


def test_devfolio_registration_closed():
    page = (FX / "devfolio.html").read_text(encoding="utf-8")
    assert not any(h.registration_open for h in devfolio.parse(page, now=datetime(2027, 6, 1)))


def test_unstop_parse():
    items = unstop.parse(load("unstop.json"), now=datetime(2026, 10, 28))
    assert len(items) == 4
    online = [h for h in items if h.is_online]
    assert len(online) == 2 and all(h.location == "Online" for h in online)
    assert all(h.registration_open and h.url.startswith("https://unstop.com/") for h in items)
    assert any(h.prize for h in items) and all("<" not in h.description for h in items)
    # présentiel / hybride : lieu brut, jamais marqués en ligne
    assert all(not h.is_online and h.location for h in items if h not in online)
    assert [h.is_online for h in items if filters.keep(h)] == [True, True]


def test_unstop_registration_closed():
    assert not any(h.registration_open for h in unstop.parse(load("unstop.json"), now=datetime(2027, 6, 1)))


def test_devevents_parse():
    page = (FX / "devevents.html").read_text(encoding="utf-8")
    items = devevents.parse(page, now=datetime(2026, 10, 28, 12))
    names = {h.title for h in items}
    assert "The Principal Dev – Masterclass for Tech Leads" not in names  # pas un hackathon
    assert {"Nebius x NVIDIA Global AI Hackathon", "PayPal AI Hackathon"} <= names
    assert all(h.is_online and h.location == "Online" and h.source == "dev.events" for h in items)
    ended = [h for h in items if h.title == "AWS Communication Developer Services"]
    assert ended and not ended[0].registration_open  # fini à minuit


def test_devevents_filter():
    page = (FX / "devevents.html").read_text(encoding="utf-8")
    kept = [h for h in devevents.parse(page, now=datetime(2026, 10, 28, 12)) if filters.keep(h)]
    assert {h.title for h in kept} == {"Nebius x NVIDIA Global AI Hackathon", "PayPal AI Hackathon"}
