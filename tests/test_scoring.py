import json

import pytest

from hackwatch import llm
from hackwatch.models import Hackathon
from hackwatch.scoring import Scored, keyword_regex, parse_prize, score, select
from hackwatch.sources.ctftime import parse as ctftime_parse
from hackwatch.sources.ctftime import short_prize

PROFILE = {
    "objectifs": {
        "ia_technique": {"poids": 1.0, "description": "d", "mots_cles": ["LLM", "agentic", "red teaming"],
                         "mots_generiques": ["AI"]},
        "opportunites_pro": {"poids": 0.9, "description": "d", "mots_cles": ["NVIDIA", "Meta"]},
        "deeptech": {"poids": 0.7, "description": "d", "mots_cles": ["quantum"], "mots_generiques": ["health"]},
    },
    "notification": {"score_min": 0.6},
}


def hk(title="x", **kw):
    return Hackathon(title=title, url=kw.pop("url", title), source=kw.pop("source", "devpost"), **kw)


def sc(title="x", **kw):
    return score(hk(title, **kw), PROFILE)


def test_echelle_progressive_sans_saturation():
    one, two, three = sc("LLM"), sc("LLM agentic"), sc("LLM agentic red teaming")
    assert 0 < one.score < two.score < three.score < 1.0  # chaque mot-clé compte, sans plafond à 2 hits


def test_titre_pese_plus_que_description():
    assert sc("LLM").score > sc("x", tags=["LLM"]).score > 0
    assert sc("LLM").score > sc("x", description="LLM").score > 0


def test_generique_pese_moins_que_specifique():
    assert sc("AI").score < sc("agentic").score
    assert sc("health").axe == "deeptech" and sc("health").score < sc("quantum").score


def test_bonus_multi_axes():
    solo = sc("agentic")
    multi = sc("agentic", description="NVIDIA")
    assert multi.axe == "ia_technique" and multi.score > solo.score
    assert any("aussi opportunités pro" in r for r in multi.raisons)


def test_limites_de_mots_et_casse_des_acronymes():
    assert sc("MAIL training").score == 0  # "AI" dans "MAIL" ne compte pas
    assert sc("Hawaii ai club", description="said meta-analysis").score == 0  # acronymes et marques : casse exacte
    assert sc("AI/LLM track").score > 0 and sc("LLMs").score == sc("LLM").score  # séparateur "/", pluriel
    assert sc("Agentic").score == sc("agentic").score  # mot en minuscules : insensible à la casse
    assert keyword_regex("red teaming").search("Red-Teaming challenge")
    assert sc("META HACKATHON").axe == "opportunites_pro"


def test_bonus_prize_progressif_et_plafond():
    base = sc("LLM hackathon").score
    assert sc("LLM hackathon", location="Paris, France").score == pytest.approx(base + 0.15)
    assert sc("LLM hackathon", prize="$5,000").score == pytest.approx(base + 0.05)
    assert sc("LLM hackathon", prize="$50,000").score == pytest.approx(base + 0.1)
    assert sc("LLM hackathon", tags=["student"]).score == pytest.approx(base + 0.05)
    full = sc("LLM agentic red teaming NVIDIA quantum", location="Paris", prize="$50,000", tags=["student"])
    assert full.score == 1.0 and 1 <= len(full.raisons) <= 3


def test_malus_eligibilite():
    ok = sc("LLM agentic").score
    bad = sc("LLM agentic", description="US residents only")
    assert bad.score == pytest.approx(ok - 0.5) and "restriction d'éligibilité" in bad.raisons
    assert sc("LLM agentic", description="built for high schoolers across Australia").score < ok


def test_malus_qualification_hors_france():
    ok = sc("LLM CTF 2026").score
    for title in ("Russian CTF Cup X Qualifier", "HKCERT CTF 2026 (Qualifying Round)", "LakeCTF Quals 26-27",
                  "2026 Qiangwang Challenge Qualification"):
        s = sc(f"LLM {title}")
        assert s.score == pytest.approx(max(0, ok - 0.3), abs=0.06) and "qualification" in s.raisons[0]
    assert sc("LLM CTF Qualifier", location="Paris").score >= ok  # qualif en France : pas de malus


def test_parse_prize():
    assert parse_prize("$25,000") == 25000
    assert parse_prize("5 000 €") == 5000
    assert parse_prize("€997") == 997
    assert parse_prize("USD 2,500 Guaranteed") == 2500
    assert parse_prize("₹ 100,000") == pytest.approx(1100)  # roupies converties en euros
    assert parse_prize("TBA") == 0


def test_short_prize_ctftime():
    raw = "USD 2,500 Guaranteed Cash Prize Pool\r\n+ Additional Sponsored Rewards\r\n\r\nCASH PRIZES: 1st 1000$"
    out = short_prize(raw)
    assert "\n" not in out and len(out) <= 61 and out.startswith("USD 2,500") and out.endswith("…")
    assert short_prize("1st: 300 USD") == "1st: 300 USD"
    for placeholder in ("TBA", "To be announced!", "See https://example.org/prizes", "More TBA 1 year .xyz domains"):
        assert short_prize(placeholder) == ""


def test_ctftime_fixture_prizes_courts():
    events = json.load(open("tests/fixtures/ctftime.json", encoding="utf-8"))
    assert all("\n" not in h.prize and len(h.prize) <= 61 for h in ctftime_parse(events))


def test_top_departage_sur_fixture_devpost():
    from hackwatch.main import load_profile
    from hackwatch.sources.devpost import parse as devpost_parse
    items = devpost_parse(json.load(open("tests/fixtures/devpost.json", encoding="utf-8")))
    scores = [score(h, load_profile()).score for h in items]
    assert max(scores) < 1.0 and len(set(scores)) > len(scores) // 2


def test_selection_seuil_et_plafonds():
    def sc(t, v, src="devpost"):
        return Scored(hk(t, source=src), v, "ia_technique", [])
    items = [sc(f"c{i}", 0.9, "ctftime") for i in range(5)] + [sc("a", 0.8), sc("b", 0.3)]
    kept, rest = select(items, 0.6, max_total=15, max_ctftime=3)
    assert sum(s.hackathon.source == "ctftime" for s in kept) == 3
    assert {s.hackathon.title for s in kept} >= {"a"} and "b" not in {s.hackathon.title for s in kept}
    assert len(rest) == 3
    kept, _ = select([sc(str(i), 0.9) for i in range(20)], 0.6, max_total=15)
    assert len(kept) == 15


class FakeClient:
    def __init__(self, text=None, exc=None):
        self.messages, self._text, self._exc = self, text, exc

    def create(self, **kw):
        if self._exc:
            raise self._exc
        from types import SimpleNamespace as N
        return N(content=[N(type="text", text=self._text)])


def test_llm_remplace_le_score():
    s = [Scored(hk("a"), 0.7, "ia_technique", ["règle"])]
    out = llm.rescore(s, PROFILE, FakeClient('x [{"id":0,"score":0.2,"axe":"deeptech","raison":"hors sujet"}]'))
    assert (out[0].score, out[0].axe, out[0].raisons) == (0.2, "deeptech", ["hors sujet"])


def test_llm_repli_sur_erreur(monkeypatch):
    s = [Scored(hk("a"), 0.7, "ia_technique", ["règle"])]
    assert llm.rescore(s, PROFILE, FakeClient(exc=RuntimeError("boom"))) == s
    assert llm.rescore(s, PROFILE, FakeClient("pas du json")) == s
    monkeypatch.setattr(llm, "enabled", lambda: False)
    assert llm.rescore(s, PROFILE) == s  # inerte sans clé
