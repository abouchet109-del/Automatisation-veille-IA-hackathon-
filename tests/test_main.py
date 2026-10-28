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
