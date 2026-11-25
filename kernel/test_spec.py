import pytest

import glyphh_nsm as nsm
from glyphh_kernel import Space
from glyphh_spec import Model, Spec, SpecError

TICKETS = {
    "name": "tickets",
    "temporal_source": "meta.time.opened",
    "layers": [
        {"name": "issue", "segments": [
            {"name": "body", "roles": [
                {"name": "title", "text_encoding": "bag_of_words"},
                {"name": "component", "lexicons": ["area"]},
                {"name": "severity", "numeric_config": {"min_value": 0, "max_value": 10, "bin_width": 1}},
                {"name": "labels"},
                {"name": "id", "key_part": True, "similarity_weight": 0}]}]},
        {"name": "meta", "security_weight": 0.8, "segments": [
            {"name": "time", "roles": [{"name": "opened"}]},
            {"name": "owner", "roles": [{"name": "team"}]}]},
    ],
}


def ticket(i, title, component, severity, team="infra", opened="2026-10-01T12:00:00Z"):
    return {"issue": {"body": {"title": title, "area": component, "severity": severity, "id": i}},
            "meta": {"time": {"opened": opened}, "owner": {"team": team}}}


# ── the spec itself ─────────────────────────────────────────────────

def test_a_spec_round_trips_and_has_a_content_address():
    spec = Spec.from_json(TICKETS)
    again = Spec.from_json(spec.to_json())
    assert again == spec and again.spec_id == spec.spec_id
    assert Spec.from_json({**TICKETS, "seed": 7}).spec_id != spec.spec_id


@pytest.mark.parametrize("mutate, where", [
    (lambda s: s.update(colour="red"), "unknown field(s): colour"),
    (lambda s: s["layers"][0].update(weight=1), "layers[0]: unknown field(s): weight"),
    (lambda s: s["layers"][0]["segments"][0]["roles"][0].update(similarity_weight=1.5), "similarity_weight"),
    (lambda s: s["layers"][0]["segments"][0]["roles"].append({"name": "title"}), "'title' is named twice"),
    (lambda s: s["layers"][0]["segments"][0]["roles"].append({"name": "x", "lexicons": ["area"]}),
     "'area' is named twice"),
    (lambda s: s.update(temporal_source="meta.time.nope"), "temporal_source"),
    (lambda s: s.update(output={"report": ["issue.nope"]}), "output.report"),
    (lambda s: s["layers"][0]["segments"][0]["roles"][2]["numeric_config"].update(bin_width=0), "bin_width > 0"),
    (lambda s: s.update(layers=[]), "at least one layer"),
])
def test_a_spec_that_does_not_match_is_refused_naming_where(mutate, where):
    import copy
    bad = copy.deepcopy(TICKETS)
    mutate(bad)
    with pytest.raises(SpecError, match=where.replace("(", r"\(").replace(")", r"\)").replace("[", r"\[")
                       .replace("]", r"\]").replace(".", r"\.")):
        Spec.from_json(bad)


def test_data_takes_the_spec_shape_exactly():
    spec = Spec.from_json(TICKETS)
    s = spec.situation(ticket("K-1", "Pods crash on boot, pods!", "kubelet", 7))
    body = s["issue"]["body"]
    assert body["title"] == [["boot", 1.0], ["crash", 1.0], ["on", 1.0], ["pods", 1.0]]  # a bag: a weighted set, read through the lexicon
    assert body["component"] == "kubelet", "a lexicon name lands on its role"
    assert body["severity"] == ["0", "1", "2", "3", "4", "5", "6", "7"]
    with pytest.raises(SpecError, match="issue.body.colour: no such role"):
        spec.situation({"issue": {"body": {"colour": "red"}}})
    with pytest.raises(SpecError, match="issue.body.severity: a numeric role takes a finite number"):
        spec.situation({"issue": {"body": {"severity": "high"}}})
    with pytest.raises(SpecError, match="given twice"):
        spec.situation({"issue": {"body": {"component": "a", "area": "b"}}})


# ── reads ───────────────────────────────────────────────────────────

def test_near_numbers_match_closer_than_far_ones():
    m = Model(Spec.from_json(TICKETS))
    m.record(ticket("A", "x", "c", 6), "low")
    m.record(ticket("B", "x", "c", 1), "high")
    q = {"issue": {"body": {"severity": 7}}}
    top = m.facts(q, top=2)
    assert [t["outcome"] for t in top] == ["low", "high"]
    assert top[0]["score"] > top[1]["score"]


def test_a_query_scores_only_the_roles_it_gives():
    m = Model(Spec.from_json(TICKETS))
    m.record(ticket("A", "pods crash", "kubelet", 7, team="infra"), "restart")
    full = m.facts({"issue": {"body": {"component": "kubelet"}}}, top=1)[0]
    assert full["score"] == pytest.approx(1.0), "the one role given matches; the rest weigh 0"


def test_clearance_hides_roles_from_the_score_and_the_tree():
    m = Model(Spec.from_json(TICKETS))
    m.record(ticket("A", "pods crash", "kubelet", 7, team="infra"), "restart")
    m.record(ticket("B", "pods crash", "kubelet", 7, team="web"), "page")
    q = ticket("Q", "pods crash", "kubelet", 7, team="web")

    cleared = m.facts(q, clearance=1.0, top=1)[0]
    assert cleared["outcome"] == "page", "the team decides, for a reader who may see it"
    layers = [n["key"] for n in cleared["tree"]["children"]]
    assert layers == ["issue", "meta"]

    low = m.facts(q, clearance=0.5, top=2)
    assert {t["score"] for t in low} == {low[0]["score"]}, "without meta both precedents tie"
    assert [n["key"] for n in low[0]["tree"]["children"]] == ["issue"]
    assert "infra" not in str(low) and "web" not in str(low)


def test_a_model_above_the_readers_clearance_answers_nothing():
    m = Model(Spec.from_json({**TICKETS, "security_weight": 0.9}))
    m.record(ticket("A", "x", "c", 1), "y")
    with pytest.raises(SpecError, match="above the reader's clearance"):
        m.facts({"issue": {"body": {"component": "c"}}}, clearance=0.5)


def test_output_report_keeps_only_the_named_paths():
    m = Model(Spec.from_json({**TICKETS, "output": {"report": ["issue.body.component"]}}))
    m.record(ticket("A", "pods crash", "kubelet", 7), "restart")
    tree = m.facts(ticket("Q", "pods crash", "kubelet", 7), top=1)[0]["tree"]
    assert [(l["key"], s["key"], r["key"]) for l in tree["children"] for s in l["children"]
            for r in s["children"]] == [("issue", "body", "component")]


def test_a_key_part_replaces_the_record_and_the_time_comes_from_its_role():
    m = Model(Spec.from_json(TICKETS))
    first = m.record(ticket("K-1", "x", "c", 1), "old")
    again = m.record(ticket("K-1", "x", "c", 1, opened="2026-10-02T00:00:00Z"), "new")
    assert first == again and len(m) == 1
    assert m.space._outcomes == ["new"]
    assert m.space._ts == [1_790_899_200.0]


def test_a_record_with_no_outcome_is_memory_that_never_votes(tmp_path):
    s = Space(path=str(tmp_path / "s.db"), min_sim=0.0)
    s.record({"a": "x", "b": "y"})
    s.record({"a": "x", "b": "z"}, "act")
    answer = s.query({"a": "x", "b": "y"})
    assert answer.top == "act" and answer.count == 1
    facts = s.facts({"a": "x", "b": "y"}, top=2)
    assert facts[0].outcome is None and facts[0].probability == 0.0
    reopened = Space(path=str(tmp_path / "s.db"))
    assert reopened._outcomes == [None, "act"]


# ── the NSM default ─────────────────────────────────────────────────

def test_text_decomposes_to_primes_deterministically():
    assert nsm.decompose("I wanted to know why the build failed yesterday, 3 times") == [
        "I", "WANT", "KNOW", "BECAUSE", "DO", "BAD", "BEFORE", "WHEN", "MUCH"]
    assert sum(len(p) for p in nsm.PRIMES.values()) == 64


def test_the_nsm_model_takes_bare_text_and_finds_it_by_meaning():
    m = Model(nsm.SPEC, min_sim=0.0)
    m.record(nsm.data("the deploy failed because the database was down"))
    m.record(nsm.data("we are happy with the new home"))
    top = m.facts(nsm.data("why did the release break?"), top=1)[0]
    assert top["outcome"] is None
    assert "deploy" in str(top["tree"])
