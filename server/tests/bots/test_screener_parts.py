"""The Resume Screener's parts one at a time: Gmail read through the proxy (text or HTML, attachments inline or
fetched, the kinds and sizes left out, labels kept), resumes read and their fields, the signals, the sender checks,
what the person hands in, the probe with no reference or no precedent, the verdicts put together, a seed set named
that Glyphh does not ship, and built-in tools called by a bot on a rrotor."""

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
from tests.bots.conftest import BOTS
from tests.bots.mailbox import FakeGmail, b64, docx, message, pdf
from tests.bots.remote import OnRrotor, rrotor_fixture  # noqa: F401 (the fixture)
from tests.bots.test_tool_calls import _call, _out


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


def test_verdicts_waiting_and_confidence_unknown() -> None:
    apps = [{"id": "a"}, {"id": "b"}, {"id": "c"}]
    got = verdicts.merged({"applications": apps, "source": [{"key": "b", "outcome": "real", "by": "default"},
                                                          {"key": "c", "outcome": "real", "by": "ada", "p": 0.8}],
                           "fit": [{"key": "c", "outcome": None, "by": "deferred"}]})  # fmt: skip
    assert [v["verdict"] for v in got["verdicts"]] == ["waiting", "waiting", "waiting"]
    assert got["verdicts"][1]["source"] == {"outcome": "real", "confidence": None, "by": "default"}
    assert got["summary"] == "3 waiting" and verdicts.marks(got) == {}


def test_a_seed_set_glyphh_does_not_ship_is_refused() -> None:
    seeds.named({"gates": {"g": {"case": {}}}})
    with pytest.raises(Invalid, match="g: nope is not one"):
        seeds.named({"gates": {"g": {"seed_from": "nope"}, "h": {"seed_from": "resume-screener"}}})


def test_the_probe_unseeded_sends_all_on_and_one_with_no_precedent_is_human() -> None:
    held: dict[str, str] = {}
    model = SimpleNamespace(decide=lambda case: SimpleNamespace(receipts=[{"sim": "x"}]))
    bot = SimpleNamespace(gates={"made": {"case": {"x": "$item.id"}}}, gate_model=lambda name: "m")
    ctx = SimpleNamespace(bot=bot, state=held.get, ada=SimpleNamespace(model=lambda name: model))
    apps = {"applications": [{"id": "a"}, "junk"], "gate": "made"}
    assert probe.probed(ctx, apps) == {"generated": [{"id": "a"}], "human": [], "reference": None}
    assert probe.probed(ctx, "junk") == {"generated": [], "human": [], "reference": None}
    held[probe.KEY + "made"] = json.dumps({"p5": 0.5, "n": 3})
    assert probe.probed(ctx, apps)["human"] == [{"id": "a", "nearest": None}]
    assert probe.spread([]) == {"n": 0} and probe.spread([0.2, 0.9])["p5"] == 0.2


async def test_a_bot_on_a_rrotor_calls_a_built_in_tool(on_rrotor: OnRrotor, engine: AsyncEngine) -> None:
    _, _, run_id, token = await _out(on_rrotor, engine)
    status, got = await _call(on_rrotor, run_id, token, "screen_verdicts", {"applications": []})
    assert (status, got["result"]["summary"]) == (200, "no new applications")
    status, got = await _call(on_rrotor, run_id, token, "probe_generated", {"applications": [{"id": "a"}]})
    assert (status, got["result"]["generated"], got["result"]["reference"]) == (200, [{"id": "a"}], None)
