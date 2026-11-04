from email.utils import getaddresses

from hackwatch.models import Hackathon
from hackwatch.notify import build_message
from hackwatch.scoring import Scored
from hackwatch.store import Store


def hk(url):
    return Hackathon(title="T <b>", url=url, source="x")


def test_store_dedup(tmp_path):
    s = Store(str(tmp_path / "t.db"))
    items = [hk("u1"), hk("u2"), hk("u1")]
    new = s.new_items(items)
    assert [h.url for h in new] == ["u1", "u2"]
    s.mark_sent(new)
    assert s.new_items(items + [hk("u3")]) == [hk("u3")]


def test_dry_run_does_not_mark(tmp_path):
    s = Store(str(tmp_path / "t.db"))
    s.new_items([hk("u1")])
    assert len(s.new_items([hk("u1")])) == 1


def test_message_escapes_html():
    m = build_message([Scored(hk("https://a.b"), 0.7, "ia_technique", ["r"])], "a@b.c", "d@e.f", [Scored(hk("https://o.p"), 0.1, "", [])] * 4)
    body = m.get_body(("html",)).get_content()
    assert "&lt;b&gt;" in body and "https://a.b" in body and ": 4</h2>" in body


def test_store_path_from_env(tmp_path, monkeypatch):
    monkeypatch.setenv("HACKWATCH_DB", str(tmp_path / "env.db"))
    Store().close()
    assert (tmp_path / "env.db").exists()


def test_message_shows_failed_sources():
    s = [Scored(hk("https://a.b"), 0.7, "ia_technique", ["r"])]
    body = build_message(s, "a@b.c", "d@e.f", [], ["luma", "mlh"]).get_body(("html",)).get_content()
    assert "Sources en échec : luma, mlh" in body
    assert "Sources en échec" not in build_message(s, "a@b.c", "d@e.f").get_body(("html",)).get_content()


def test_message_several_recipients():
    # EMAIL_TO accepte plusieurs adresses séparées par des virgules
    msg = build_message([], "a@b.c", "d@e.f, g@h.i")
    assert [a for _, a in getaddresses(msg.get_all("To"))] == ["d@e.f", "g@h.i"]
