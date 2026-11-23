"""The Resume Screener's parts one at a time: Gmail read through the proxy (text or HTML, attachments inline or
fetched, the kinds and sizes left out, labels kept), resumes read and their fields, the signals, the sender checks,
what the person hands in, the probe's reference measured (and a decision with no precedent), the verdicts as inbox
labels, a seed set named that Glyphh does not ship, and the built-in tools called by a bot on a rrotor."""

import json
import uuid
from types import SimpleNamespace
from typing import Any

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_server.errors import Invalid
from glyphh_server.ops.bots import applicants, builtins, gmail, probe, resumes, seeds, signals, verdicts
from glyphh_server.ops.bots.pipedream import Pipedream
from tests.bots.conftest import BOTS, inbox
from tests.bots.mailbox import FakeGmail, b64, docx, message, pdf
from tests.bots.remote import OnRrotor, out, rrotor_fixture  # noqa: F401 (the fixture)


def _gmail(fake: FakeGmail) -> gmail.Gmail:
    pd = Pipedream(httpx.AsyncClient(transport=httpx.MockTransport(fake.handle)), BOTS)
    return gmail.Gmail(pd, uuid.uuid4(), "apn_1")


async def test_a_message_is_read_whole_and_labels_are_made_once() -> None:
    fake = FakeGmail()
    m = message("m1", "A <a@b.co>", "Hi", "plain", files=(("cv.pdf", pdf(["Ann Lee"])), ("cat.png", b"x")))
    m["payload"]["parts"][0] = {"mimeType": "text/html", "filename": "", "body": {"data": b64(b"<p>Hi &amp; bye</p>")}}
    huge = {"attachmentId": "z", "size": gmail.ATTACHMENT_MAX + 1}
    m["payload"]["parts"] += [
        {"mimeType": "text/plain", "filename": "note.txt", "body": {"data": b64(b"inline")}},
        {"filename": "huge.docx", "body": huge},
        {"filename": "empty.txt", "body": {}},
    ]
    m["payload"]["headers"] += [{"name": "Received", "value": "one"}, {"name": "Received", "value": "two"}]
    fake.inbox = [m]
    g = _gmail(fake)
    assert await g.ids("q", 5) == ["m1"]
    read = await g.read("m1")
    assert read.text.strip() == "Hi & bye" and read.headers["received"] == "one; two"
    assert [(n, k) for n, k, _ in read.files] == [("cv.pdf", "pdf"), ("note.txt", "text")]
    assert gmail.kind_of("README") is None and gmail.text_of({"mimeType": "text/plain"}) == ""
    assert await g.label({"Screened": ["m1"]}) == {"Screened": 1}
    assert await g.label({"Screened": ["m1"], "Screened/Pass": ["m1"]}) == {"Screened": 1, "Screened/Pass": 1}
    assert fake.labels == {"Screened": "L1", "Screened/Pass": "L2"}


def test_resumes_read_and_their_fields() -> None:
    assert "Ann" in resumes.text("pdf", pdf(["Ann Lee"])) and resumes.text("docx", docx(["One", "Two"])) == "One\nTwo"
    assert resumes.text("text", "hé".encode()) == "hé"
    with pytest.raises(ValueError, match="pdf file could not be read"):
        resumes.text("pdf", b"not a pdf")
    with pytest.raises(ValueError, match="docx file could not be read"):
        resumes.text("docx", b"PK not a zip")
    said = "\n".join(
        ["Dev, Acme (2010 - 2014)", "Lead at Beta (2012 - 2016)", "Future Co (2030 - 2031)",
         "Intern, Gamma (2011 - 2013)", "Skills: Go; Rust | sql"]
    )  # fmt: skip
    assert (resumes.years(said), resumes.years("I have 7 years of SQL"), resumes.years("none")) == (6, 7, 0)
    assert resumes.skills(said) == ["go", "rust", "sql"] and resumes.titles(said) == "Dev; Lead; Future Co; Intern"
    got = resumes.fields("dev at acme\nno email here", "Sender Name", "s@x.co")
    assert (got["name"], got["email"], got["education"]) == ("Sender Name", "s@x.co", "none")
    assert resumes.education("PhD in physics, M.Sc. too") == "phd"


def test_a_too_big_word_file_is_not_read(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(resumes, "DOCX_XML_MAX", 10)
    with pytest.raises(ValueError, match="could not be read: ValueError"):
        resumes.text("docx", docx(["A long paragraph"]))


def test_signals_and_the_sender_checks() -> None:
    assert signals.burstiness("Too short.") == 50 and signals.measured("see https://a.co", "")["links"] == 1
    assert applicants.sender("x@uni.edu")[3] == "edu" and applicants.sender("nobody")[3] == "unknown"
    assert applicants.item("i", "", "s", "", False, "hi", "", "none") == (
        None, {"id": "i", "from": "", "subject": "s", "why": "it has no sender"})  # fmt: skip
    assert applicants.item("i", "a@b.co", "s", "", False, " ", "", "none")[1]["why"].startswith("there is nothing")
    assert applicants.authed("spf=pass spf=fail dkim=neutral") == {"spf": "pass", "dkim": "neutral", "dmarc": "none"}
    assert applicants.bulk_of({"precedence": "Bulk"}) and applicants.bulk_of({"auto-submitted": "auto-replied"})
    assert not applicants.bulk_of({})


def test_an_unreadable_attachment_is_said_and_the_next_one_read() -> None:
    heads = {"from": "Ann <ann@b.co>", "subject": "Data Analyst", "received-spf": "pass (ok)"}
    files = [("bad.pdf", "pdf", b"junk"), ("cv.docx", "docx", docx(["Ann Lee", "Skills: sql"]))]
    mail = gmail.Mail("m", heads, "Hello", files)
    got, why = applicants.of_mail(mail)
    assert why is None and got is not None
    assert (got["resume_kind"], got["skills"], got["auth"][0]) == ("docx", ["sql"], "spf:pass")
    assert got["resume_problems"][0].startswith("bad.pdf: the pdf file could not be read")


@pytest.mark.parametrize(
    ("given", "handed"),
    [('{"resume": "R"}', {"resume": "R"}), ("{not json", {"resume": "{not json"}), ("cv", {"resume": "cv"}),
     ({"letter": "L"}, {"letter": "L"}), ({"role": "x"}, None), ("", None), (None, None), (7, None)],
)  # fmt: skip
def test_what_the_person_hands_in(given: Any, handed: dict[str, str] | None) -> None:
    assert builtins.handed(given) == handed


async def test_the_inbox_tools_without_gmail_say_so() -> None:
    tools = builtins.made(Pipedream(httpx.AsyncClient(), BOTS), uuid.uuid4(), None)
    with pytest.raises(ValueError, match="no Gmail connection"):
        await tools["inbox_applications"]({"most": 500})
    with pytest.raises(ValueError, match="no Gmail connection"):
        await tools["inbox_label"]({"verdicts": [{"id": "m1", "verdict": "poor"}]})
    handed_only = {"verdicts": [{"id": "given-1", "verdict": "poor"}], "rejected": [{"id": "given-2"}]}
    assert await tools["inbox_label"](handed_only) == {"labelled": {}}
    handed = await tools["inbox_applications"]({"given": {"letter": "I'd like the job."}})
    assert (handed["applications"][0]["has_resume"], handed["polled"]) == ("no", 0)


def test_verdicts_become_inbox_labels_and_what_is_not_a_screened_message_gets_none() -> None:
    given = {
        "verdicts": [{"id": "m1", "verdict": "strong"}, {"id": "m2", "verdict": "spam"}, {"id": 7, "verdict": "poor"},
                     {"id": "m3", "verdict": "waiting"}, {"id": "given-1", "verdict": "poor"}, {"verdict": "poor"},
                     "m9", None],
        "rejected": [{"id": "m4", "why": "it has no sender"}, {"id": "given-2"}, {}, "m8"],
    }  # fmt: skip
    assert verdicts.marks(given) == {
        "Screened": ["m1", "m2", "7", "m4"], "Screened/Strong": ["m1"], "Screened/Poor": ["7"],
        "Screened/Spam": ["m2", "m4"],
    }  # fmt: skip
    assert verdicts.marks({}) == {} and verdicts.marks({"verdicts": "all strong", "rejected": None}) == {}


def test_a_seed_set_glyphh_does_not_ship_is_refused() -> None:
    seeds.named({"gates": {"g": {"case": {}}}})
    with pytest.raises(Invalid, match="g: nope is not one"):
        seeds.named({"gates": {"g": {"seed_from": "nope"}, "h": {"seed_from": "resume-screener"}}})


def test_the_probes_reference_is_measured_over_cases_and_a_decision_with_no_precedent_has_no_nearest() -> None:
    held: dict[str, str] = {}
    sims = {"a": [{"sim": 0.2}, {"sim": 0.9}, "junk"], "b": [{"sim": 0.4}], "c": [{"sim": "x"}], "d": None}
    model = SimpleNamespace(decide=lambda case: SimpleNamespace(receipts=sims[case["id"]]))
    runner = SimpleNamespace(
        ada=SimpleNamespace(model=lambda name: model),
        bot=SimpleNamespace(gate_model=lambda name: f"bot-x-gate-{name}"),
        store=SimpleNamespace(set_state=held.__setitem__),
    )
    assert probe.nearest(model, {"id": "a"}) == 0.9 and probe.nearest(model, {"id": "c"}) is None
    assert probe.nearest(model, {"id": "d"}) is None  # it holds no precedent: nothing is near
    reference = probe.measure(runner, "made", [{"data": {"id": k}} for k in sims])
    assert reference == {"p5": 0.4, "p25": 0.4, "p50": 0.4, "p75": 0.9, "p95": 0.9, "n": 2}
    assert json.loads(held[probe.KEY + "made"]) == reference
    assert probe.spread([]) == {"n": 0} and probe.spread([0.2, 0.9])["p5"] == 0.2


async def test_a_bot_on_a_rrotor_calls_a_built_in_tool(on_rrotor: OnRrotor, engine: AsyncEngine) -> None:
    spec = inbox(builtins=["inbox_applications", "inbox_label", "probe_generated", "screen_verdicts"])
    _, _, run = await out(on_rrotor, engine, spec=spec)
    assert {"inbox_applications", "inbox_label"} <= {t["name"] for t in on_rrotor.call().inputs["tools"]}
    got = await on_rrotor.tool(run["id"], "inbox_applications", {"given": {"letter": "I'd like the job."}})
    assert (got["result"]["applications"][0]["has_resume"], got["result"]["polled"]) == ("no", 0)
    assert "no Gmail connection" in (await on_rrotor.tool(run["id"], "inbox_applications", {}))["error"]
    asked = await on_rrotor.tool(run["id"], "inbox_label", {"verdicts": [{"id": "m1", "verdict": "poor"}]})
    assert asked == {"ask": True, "question": "Label the screened mail?"}  # an action: the person is asked first
    for gone in ("probe_generated", "screen_verdicts"):  # no longer tools: the agent decides with `decide`
        assert (await on_rrotor.tool(run["id"], gone, {"applications": []}))["error"].startswith("There is no tool")
