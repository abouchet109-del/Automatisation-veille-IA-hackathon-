from hackwatch.models import Hackathon


def test_hackathon_defaults():
    h = Hackathon(title="T", url="https://x.y", source="test")
    assert h.tags == [] and h.registration_open and not h.is_online
