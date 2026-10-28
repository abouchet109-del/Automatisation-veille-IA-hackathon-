from hackwatch.models import Hackathon
from hackwatch.notify import build_message
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
    m = build_message([hk("https://a.b")], "a@b.c", "d@e.f")
    body = m.get_body(("html",)).get_content()
    assert "&lt;b&gt;" in body and "https://a.b" in body
