import json
from pathlib import Path

import httpx

from hackwatch import enrich, notify
from hackwatch.models import Hackathon
from hackwatch.scoring import Scored

FX = Path(__file__).parent / "fixtures"


def read(name):
    return (FX / name).read_text(encoding="utf-8")


def client(routes):
    """Client httpx sans réseau : routes = {sous-chaîne d'URL: (statut, contenu)}."""
    def handler(request):
        for key, (status, body) in routes.items():
            if key in str(request.url):
                return httpx.Response(status, text=body)
        return httpx.Response(404)
    return httpx.Client(transport=httpx.MockTransport(handler))


def hack(url, source, **kw):
    return Hackathon(title="Titre", url=url, source=source, **kw)


def test_summarize_cuts_at_sentence_or_word():
    s = "A" * 30 + ". " + "b" * 80 + ". " + "c" * 200
    assert enrich.summarize(s) == "A" * 30 + ". " + "b" * 80 + "."
    assert enrich.summarize("<p>Un  texte\n<b>propre</b></p>") == "Un texte propre"
    words = " ".join(["mot"] * 100)
    r = enrich.summarize(words)
    assert len(r) <= 200 and r.endswith("…") and not r.endswith(" …")


def test_clean_tracks_drops_generic_and_dupes():
    out = enrich.clean_tracks(["🥇 1st place : €5,500", "Best Use of AG Grid - 1st Place",
                               "Best Use of AG Grid - 2nd Place", "Grand Prize", "Coding Track Winner",
                               "Best Experience", "Best Experience Runner-up", "1 - Automatiser l'IA", "x" * 90])
    assert out == ["Best Use of AG Grid", "Coding Track", "Best Experience", "Automatiser l'IA", "x" * 59 + "…"]
    assert enrich.clean_tracks(["First Place", "Second Place", "Third Place"]) == []
    assert len(enrich.clean_tracks([f"Défi {i}" for i in range(9)])) == 5


def test_devpost_page_prizes_become_tracks():
    h = hack("https://paypalaihackathon.devpost.com/", "devpost")
    h.description = "PayPal"
    enrich.enrich([h], client({"devpost.com": (200, read("enrich_devpost.html"))}))
    assert "Best Use of PayPal + AI" in h.tracks and "Most Creative" in h.tracks
    assert not any("Place" in t for t in h.tracks) and len(h.tracks) <= 5
    assert "PayPal" in h.resume  # description trop courte : méta de la page


def test_devpost_nothing_found_keeps_source_themes_then_nothing():
    page = read("enrich_devpost_vide.html")  # seulement First / Second / Third Place
    h = hack("https://qloo.devpost.com/", "devpost", tracks=["Machine Learning/AI", "Web"])
    enrich.enrich([h], client({"devpost.com": (200, page)}))
    assert h.tracks == ["Machine Learning/AI", "Web"]
    h2 = hack("https://qloo.devpost.com/", "devpost")
    enrich.enrich([h2], client({"devpost.com": (200, page)}))
    assert h2.tracks == [] and h2.resume


def test_luma_page_resume_and_sections():
    page = read("enrich_luma.html")
    tracks, text = enrich.luma_page(page)
    assert tracks == [] and "Generathon" in text  # cette description n'a pas de section de tracks
    doc = {"type": "doc", "content": [
        {"type": "heading", "content": [{"type": "text", "text": "À propos"}]},
        {"type": "paragraph", "content": [{"type": "text", "text": "Blabla"}]},
        {"type": "heading", "content": [{"type": "text", "text": "Tracks"}]},
        {"type": "bullet_list", "content": [
            {"type": "list_item", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "Vidéo IA"}]}]},
            {"type": "list_item", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "Musique IA"}]}]}]},
        {"type": "heading", "content": [{"type": "text", "text": "Infos"}]},
        {"type": "bullet_list", "content": [
            {"type": "list_item", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "Parking"}]}]}]}]}
    assert enrich.prosemirror_sections(doc) == ["Vidéo IA", "Musique IA"]
    h = hack("https://luma.com/5dumglvo", "luma", description="x" * 5)
    enrich.enrich([h], client({"luma.com": (200, page)}))
    assert h.tracks == [] and h.resume.startswith("An Evening of AI Creation")


def test_agorize_categories():
    j = json.loads(read("enrich_agorize.json"))
    h = hack("https://www.agorize.com/fr/challenges/make-ai-happen", "agorize", description="court")
    enrich.enrich([h], client({"api/v2/challenges/make-ai-happen": (200, json.dumps(j))}))
    assert len(h.tracks) == 3 and h.tracks[0].startswith("Automatiser")


def test_html_sections_generic_page():
    page = ("<h2>About</h2><p>x</p><h2>Challenge tracks</h2><ul><li>Agents <b>IA</b></li><li>Sécurité</li></ul>"
            "<h2>Rules</h2><ul><li>Pas de triche</li></ul>")
    assert enrich.html_sections(page) == ["Agents IA", "Sécurité"]
    assert enrich.html_sections("<h2>Rules</h2><ul><li>a</li></ul>") == []


def test_failures_never_raise_and_page_budget():
    hs = [hack(f"https://x.test/{i}", "mlh", description="d" * 80, tracks=["Santé"]) for i in range(4)]
    enrich.enrich(hs, client({"x.test": (500, "")}))  # erreur serveur : thèmes de la source gardés
    assert all(h.tracks == ["Santé"] or h.tracks == [] for h in hs) and all(h.resume for h in hs)
    calls = []

    def handler(request):
        calls.append(1)
        return httpx.Response(200, text="<html></html>")

    hs = [hack(f"https://x.test/{i}", "mlh", description="d" * 80) for i in range(6)]
    enrich.enrich(hs, httpx.Client(transport=httpx.MockTransport(handler)), max_pages=2)
    assert len(calls) == 2 and all(h.resume for h in hs)


def test_notify_shows_tracks_and_resume_only_when_present():
    a = hack("https://a.test/", "devpost", tracks=["Agents", "Sécurité"], resume="Un résumé court.")
    b = hack("https://b.test/", "devpost")
    out = notify.render([Scored(a, 0.9, "ia_technique", []), Scored(b, 0.8, "ia_technique", [])])
    assert "Tracks :</b> Agents · Sécurité" in out and "Un résumé court." in out
    assert out.count("Tracks :") == 1


def test_clean_tracks_prize_amount_and_final_presentation():
    assert enrich.clean_tracks(["Most viral : €300 in credits for the video", "Final Presentation & Awards"]) == ["Most viral"]
