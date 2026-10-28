from hackwatch import main as m
from hackwatch.models import Hackathon


def _boom():
    raise RuntimeError("panne")


def test_collect_reports_failed_sources(monkeypatch):
    ok = lambda: [Hackathon(title="A", url="u", source="x")]
    monkeypatch.setattr(m, "SOURCES", {"bon": ok, "casse": _boom})
    items, failed = m.collect()
    assert [h.title for h in items] == ["A"] and failed == ["casse"]


def test_all_sources_failing_exits_nonzero(monkeypatch):
    monkeypatch.setattr(m, "SOURCES", {"a": _boom, "b": _boom})
    assert m.main([]) == 1


def test_nothing_new_sends_no_email(monkeypatch, tmp_path):
    monkeypatch.setattr(m, "SOURCES", {"a": lambda: []})
    monkeypatch.setenv("HACKWATCH_DB", str(tmp_path / "t.db"))
    monkeypatch.setattr(m.notify, "send", lambda *a, **k: (_ for _ in ()).throw(AssertionError("email envoyé")))
    assert m.main([]) == 0


from datetime import date

from hackwatch import notify
from hackwatch.scoring import Scored


def _setup(monkeypatch, tmp_path, n=3):
    hs = [Hackathon(title=f"H{i}", url=f"u{i}", source="x", is_online=True) for i in range(n)]
    monkeypatch.setattr(m, "SOURCES", {"a": lambda: hs})
    monkeypatch.setattr(m.filters, "keep", lambda h: True)
    monkeypatch.setattr(m, "load_profile", lambda: {"notification": {"score_min": 0.5, "max_total": 15}})
    scores = {"H0": 0.9, "H1": 0.3, "H2": 0.4}
    monkeypatch.setattr(m, "rank", lambda items, p: [Scored(h, scores[h.title], "", []) for h in items])
    monkeypatch.setenv("HACKWATCH_DB", str(tmp_path / "t.db"))
    return hs


def test_send_marks_main_and_others(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    sent = []
    monkeypatch.setattr(m.notify, "send", lambda items, others, failed: sent.append((items, others)))
    assert m.main([]) == 0
    items, others = sent[0]
    assert [s.hackathon.title for s in items] == ["H0"]
    assert [s.hackathon.title for s in others] == ["H2", "H1"]  # tri décroissant
    assert m.main([]) == 0 and len(sent) == 1  # plus rien de nouveau


def test_only_others_still_sends(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    monkeypatch.setattr(m, "load_profile", lambda: {"notification": {"score_min": 0.95}})
    sent = []
    monkeypatch.setattr(m.notify, "send", lambda items, others, failed: sent.append(len(others)))
    m.main([])
    assert sent == [3]


def test_preview_marks_nothing(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    monkeypatch.setattr(m.notify, "send", lambda *a: (_ for _ in ()).throw(AssertionError("envoi")))
    out = tmp_path / "a.html"
    assert m.main(["--preview", str(out)]) == 0
    assert "H0" in out.read_text(encoding="utf-8")
    assert len(m.Store().new_items([Hackathon(title="H0", url="u0", source="x")])) == 1


def test_others_section_eligibility_and_truncation():
    mk = lambda i, r: Scored(Hackathon(title=f"T{i}", url=f"u{i}", source="x"), 0.1, "", r)
    others = [mk(0, ["restriction d'éligibilité"])] + [mk(i, []) for i in range(1, 200)]
    h = notify.render([], others)
    assert h.count("⚠ éligibilité restreinte") == 1
    assert "… et 50 autres" in h and "T149" in h and "T150" not in h
