"""The fixed steps from an email to a verdict (screener/steps.py), with Ada's answers written by hand: what is
tested is the code's part (what is read, what each model is asked, and the verdict's rule), not Ada. The fixtures
are generated applications, not real people's."""

import json
from pathlib import Path
from typing import Any

from screener import attachments, mail, others, sections, steps, writing

FIXTURES: Path = Path(__file__).resolve().parent / "fixtures"
SURE_FINE: dict[str, Any] = {"outcome": "fine", "probabilities": {"fine": 0.93, "suspect": 0.07}, "ask": False}
SURE_SUSPECT: dict[str, Any] = {"outcome": "suspect", "probabilities": {"fine": 0.1, "suspect": 0.9}, "ask": False}
UNSURE: dict[str, Any] = {"outcome": "fine", "probabilities": {"fine": 0.5, "suspect": 0.5}, "ask": True}
FIT: dict[str, Any] = {"outcome": "strong", "probabilities": {"strong": 0.88}, "ask": False}
HOPS: bytes = (b"Received: from a.example by mx.example with ESMTPS id 1; Sun, 22 Nov 2026 17:43:40 +0000\r\n"
               b"Received: from me by a.example with ESMTPSA id 0; Sun, 22 Nov 2026 17:43:30 +0000\r\n")  # fmt: skip


def read(name: str = "strong-backend.eml", hops: bytes = HOPS) -> dict[str, Any]:
    return steps.read(mail.read(hops + (FIXTURES / name).read_bytes(), name))


def tree(who: list[str], part: str) -> dict[str, Any]:
    """A fact tree as Ada answers one, cut to what the step reads: the part's `who` record."""
    return {"key": "root", "children": [{"key": f"{part}_who", "record": [json.dumps(who)]}]}


def test_the_email_is_read_and_the_resume_told_from_the_cover_letter() -> None:
    got = read()
    raw = got["raw"]
    assert raw["name"] == "Keisha Dubois" and raw["role"] == "senior backend engineer" and raw["resume_kind"] == "pdf"
    assert "Dear Ledgerline hiring team" in raw["text"]["letter"] and "EXPERIENCE" in raw["text"]["resume"].upper()
    assert raw["timing"]["flags"] == ["none"] and raw["timing"]["hops"] == 2
    assert [a["part"] for a in steps.asks(got)] == ["history", "words", "contact", "when"]
    assert steps.asks(got)[0]["data"]["history"]["s"]["spans"] == ["2021-present", "2018-2021"]
    files = [("a.pdf", "pdf", "Dear team,\nSincerely, Ann"), ("b.pdf", "pdf", "Ann Lee\nExperience\nSkills: sql")]
    assert attachments.pick(files) == (1, [0])


def test_a_word_resume_and_pasted_words_are_read_the_same_way() -> None:
    words = "Hi, my resume is attached.\n\nKeisha"
    got = steps.read(mail.pasted(words, [("resume.docx", (FIXTURES / "strong-backend-resume.docx").read_bytes())]),
                     "Senior Backend Engineer")  # fmt: skip
    assert got["raw"]["resume_kind"] == "docx" and got["raw"]["role"] == "senior backend engineer"
    assert got["raw"]["auth"] == ["spf:given", "dkim:given", "dmarc:given"] and "when" not in got["others"]
    app = steps.compare(got, {})
    assert not steps.checked(app, "timing") and steps.checked(app, "files") and steps.checked(app, "others")
    assert steps.verdict(app, {})["person"]["signals"][0]["says"] == "not checked"


def test_a_message_whose_domain_did_not_vouch_for_it_stops_at_the_first_step() -> None:
    refused = read(hops=b"Received-SPF: fail (no)\r\n")
    assert refused["refused"]["why"].startswith("the sender's domain did not vouch for it")


def test_each_model_is_asked_its_own_case_and_what_is_unknown_is_left_out() -> None:
    app = steps.compare(read(), {})
    cases = steps.cases(app)
    assert sorted(cases) == ["files", "fit", "made", "timing"]
    assert cases["fit"]["role"]["s"]["title"] == "senior backend engineer" and cases["fit"]["key"]["s"]["id"]
    assert cases["timing"]["t"]["s"]["first_gap"] == 3 and cases["timing"]["t"]["s"]["flags"] == ["none"]
    assert cases["files"]["f"]["s"]["kind"] == "pdf" and "letter_stock" in cases["made"]["letter"]["s"]
    bare = steps.cases(steps.compare(read(hops=b""), {}))["timing"]["t"]["s"]
    assert "longest_gap" not in bare and bare["flags"] == ["no_hops"]
    spec_roles = {r["name"] for r in steps.models()["timing"]["spec"]["layers"][0]["segments"][0]["roles"]}
    assert set(cases["timing"]["t"]["s"]) <= spec_roles
    assert sections.named("Senior Backend Engineer", "backend engineer") == 100
    assert writing.part("I can't wait!! i am keen.")["slips"] > 0


def test_a_record_from_greenhouse_adds_its_own_case() -> None:
    record = {"candidate": {"created_at": "2026-11-22T17:40:00Z", "email_addresses": [{"value": "k@x.example"}],
                            "phone_numbers": [], "tags": ["Referral"], "time_zone": "America/Chicago"},
              "application": {"created_at": "2026-11-22T17:41:00Z", "source_id": 12, "referrer_id": None,
                              "prospect": False, "answers": [{"question": "Why?", "answer": "I like billing"},
                                                             {"question": "Visa?", "answer": ""}]}}  # fmt: skip
    app = steps.compare(read(), {}, record)
    case = steps.cases(app)["greenhouse"]["g"]["s"]
    assert (case["source"], case["referred"], case["questions"], case["answered"], case["answer_words"]) == ("12", "no", 2, 1, 3)
    assert (case["emails"], case["phones"], case["new_candidate"], case["tags"]) == (1, 0, "yes", ["referral"])
    assert app["found"]["greenhouse"] == ["source 12; 1 of 2 questions answered; 1 email, 0 phone, 0 links"]
    assert [ln["signal"] for ln in steps.verdict(app, {})["person"]["signals"]] == ["timing", "files", "others", "greenhouse"]


def test_the_others_step_names_what_adas_nearest_show() -> None:
    got = read()
    twin = ["avery abara", "Avery Abara - senior backend engineer", "other-1"]
    me = json.loads(got["others"]["history"]["s"]["history_who"])
    facts = {
        "history": [{"score": 0.97, "tree": tree(twin, "history")}, {"score": 1.0, "tree": tree(me, "history")}],
        "words": {"facts": [{"score": 0.4, "tree": tree(twin, "words")}]},  # a connector's wrapped answer
        "when": [{"score": 1.0, "tree": tree([f"n{i}", f"N{i}", f"w{i}"], "when")} for i in range(3)],
    }
    app = steps.compare(got, facts)
    assert app["others"]["flags"] == ["same_history"] and app["others"]["together"] == 3
    assert app["found"]["others"] == ["the same work history as Avery Abara - senior backend engineer, under another name"]
    assert app["others"]["near"]["history"] == {"sim": 0.97, "who": twin[1], "id": "other-1"}
    assert app["timing"]["flags"] == ["burst"] and app["timing"]["burst"] == 3
    again = steps.compare(got, {"history": [{"score": 0.99, "tree": tree([me[0], "Keisha, earlier", "old"], "history")}]})
    assert again["others"]["flags"] == ["applied_before"]
    assert steps.verdict(again, {"timing": SURE_FINE})["person"]["verdict"] == "real person"
    assert others.contacts("call (239) 555-0148 or kei.dub8@x.example, www.site.example/me")["handles"] == ["keidub"]


def test_the_examples_that_ship_are_each_models_cases_and_a_setup_loads_them_once() -> None:
    import seed

    loaded = {name: seed.examples(name) for name in steps.models()}
    assert {name: len(cases) for name, cases in loaded.items()} == {
        "files": 0, "fit": 1980, "greenhouse": 0, "made": 1980, "others": 1980, "timing": 0}  # fmt: skip
    assert {c["outcome"] for c in loaded["fit"]} == {"strong", "borderline", "poor"}
    assert {c["outcome"] for c in loaded["made"]} == {"some", "mostly", "fully"}
    assert {c["outcome"] for c in loaded["others"]} == {"alone"} and all("when" not in c["data"] for c in loaded["others"])
    assert len({c["data"]["key"]["s"]["id"] for c in loaded["fit"]}) == 1980  # each its own id: loading twice adds none

    class Model:
        def __init__(self, held: list[Any]) -> None:
            self.held, self.learned = held, 0

        def record_many(self, cases: list[Any]) -> None:
            self.held += cases

        def learn(self) -> None:
            self.learned += 1

    class Ada:
        def __init__(self) -> None:
            self.made: dict[str, Model] = {}

        def models(self) -> list[Any]:
            return [type("Info", (), {"name": name})() for name in self.made]

        def create_model(self, name: str, spec: dict[str, Any]) -> None:
            assert spec["name"] == name and name not in self.made
            self.made[name] = Model([])

        def model(self, name: str) -> Model:
            return self.made[name]

    ada, said = Ada(), []
    seed.setup(ada, "mine-", said.append)
    assert sorted(ada.made) == [f"mine-{n}" for n in ("files", "fit", "greenhouse", "made", "others", "timing")]
    assert (len(ada.made["mine-fit"].held), ada.made["mine-fit"].learned, ada.made["mine-others"].learned) == (1980, 1, 0)
    assert "mine-fit: learned" in said and "mine-files: made" in said
    seed.setup(ada, "mine-", said.append)  # again: nothing is made twice, the examples are sent again, learning runs
    assert "mine-fit: already there" in said and ada.made["mine-fit"].learned == 2


def test_one_request_on_standard_input_is_screened_without_touching_the_disk(monkeypatch: Any, capsys: Any) -> None:
    import base64
    import io
    import sys
    import types

    import run

    asked: list[tuple[str, str]] = []

    class Model:
        def __init__(self, name: str) -> None:
            self.name = name

        def facts(self, data: Any, top: int = 0) -> Any:
            asked.append((self.name, "facts"))
            return types.SimpleNamespace(data=[])

        def decide(self, data: Any) -> Any:
            asked.append((self.name, "decide"))
            return types.SimpleNamespace(outcome="strong", probabilities={"strong": 0.8}, ask=False)

        def record(self, data: Any, outcome: str) -> None:
            asked.append((self.name, "record"))

    fake = types.ModuleType("glyphh")
    fake.Ada = lambda: types.SimpleNamespace(model=Model)  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "glyphh", fake)
    resume = base64.b64encode((FIXTURES / "strong-backend-resume.docx").read_bytes()).decode()
    request = {"email": "Hi, my resume is attached.\n\nKeisha", "role": "Backend Engineer",
               "files": [{"name": "resume.docx", "base64": resume}]}  # fmt: skip
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(request)))
    monkeypatch.setattr(sys, "argv", ["run.py", "--stdin", "--prefix", "demo-screener-"])
    monkeypatch.setattr("pathlib.Path.write_text", lambda *a, **k: (_ for _ in ()).throw(AssertionError("wrote a file")))
    run.main()
    said = json.loads(capsys.readouterr().out)
    assert said["role"] == "backend engineer" and said["fit"]["outcome"] == "strong" and said["person"]["verdict"] == "real person"
    assert said["person"]["signals"][0]["says"] == "not checked"  # no headers were pasted: timing has nothing to check
    assert {name for name, _ in asked} == {f"demo-screener-{n}" for n in ("others", "fit", "files", "timing", "made")}
    assert "record" not in {what for _, what in asked}  # nothing is kept without --keep


def test_the_verdict_is_real_person_suspect_or_unsure_by_its_rule() -> None:
    clean = steps.compare(read(), {})
    real = steps.verdict(clean, {"fit": FIT, "timing": UNSURE, "files": UNSURE})
    assert real["person"]["verdict"] == "real person" and real["person"]["ask"] == []
    assert real["fit"] == {"outcome": "strong", "confidence": 0.88, "ask": False, "found": clean["found"]["content"]}
    assert real["made"]["outcome"] == "no answer" and real["made"]["ask"] is True
    learned = steps.verdict(clean, {"files": SURE_SUSPECT})["person"]
    assert learned["verdict"] == "suspect" and learned["signals"][1] | {"found": []} == {
        "signal": "files", "title": "The files themselves", "found": [], "says": "suspect", "by": "ada", "confidence": 0.9}  # fmt: skip
    flagged = steps.compare(read(hops=b""), {})  # no server timestamps: the timing check found something
    asked = steps.verdict(flagged, {"timing": UNSURE})["person"]
    assert asked["verdict"] == "unsure" and asked["ask"] == ["timing"] and asked["signals"][0]["by"] == "rule"
    assert steps.verdict(flagged, {"timing": SURE_FINE})["person"]["verdict"] == "real person"
    told = steps.verdict(flagged, {"timing": UNSURE}, {"timing": "suspect"})["person"]
    assert told["verdict"] == "suspect" and told["signals"][0]["by"] == "you"
    assert steps.fill({"a": {"b": "$item.x.y", "c": "$item.none"}, "d": "$item.z"}, {"x": {"y": 0}}) == {"a": {"b": 0}}
