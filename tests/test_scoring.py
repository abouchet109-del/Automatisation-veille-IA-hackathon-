from hackwatch import llm
from hackwatch.models import Hackathon
from hackwatch.scoring import Scored, parse_prize, score, select

PROFILE = {
    "objectifs": {
        "ia_technique": {"poids": 1.0, "description": "d", "mots_cles": ["AI", "LLM", "agents"]},
        "deeptech": {"poids": 0.7, "description": "d", "mots_cles": ["quantum", "health"]},
    },
    "notification": {"score_min": 0.6},
}


def hk(title="x", **kw):
    return Hackathon(title=title, url=kw.pop("url", title), source=kw.pop("source", "devpost"), **kw)


def test_mots_cles_poids_et_limites_de_mots():
    s = score(hk("Quantum health sprint"), PROFILE)
    assert s.axe == "deeptech" and s.score == 0.7
    assert score(hk("MAIL training"), PROFILE).score == 0  # "AI" dans "MAIL" ne compte pas
    assert score(hk("LLM", description="ai"), PROFILE).score == 1.0  # insensible à la casse
    assert score(hk("LLM"), PROFILE).score == 0.5  # un seul hit = moitié


def test_bonus_et_plafond():
    base = score(hk("LLM hackathon"), PROFILE).score
    assert score(hk("LLM hackathon", location="Paris, France"), PROFILE).score == base + 0.15
    assert score(hk("LLM hackathon", prize="$5,000"), PROFILE).score == base + 0.1
    assert score(hk("LLM hackathon", tags=["student"]), PROFILE).score == base + 0.05
    full = score(hk("AI LLM", location="Paris", prize="$5,000", tags=["student"]), PROFILE)
    assert full.score == 1.0 and 1 <= len(full.raisons) <= 3


def test_malus_eligibilite():
    ok = score(hk("AI LLM"), PROFILE).score
    bad = score(hk("AI LLM", description="US residents only"), PROFILE)
    assert bad.score == ok - 0.5 and "restriction d'éligibilité" in bad.raisons


def test_parse_prize():
    assert parse_prize("$25,000") == 25000
    assert parse_prize("5 000 €") == 5000
    assert parse_prize("€997") == 997
    assert parse_prize("TBA") == 0


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
