"""The Resume Screener as a person uses it: installed from the marketplace once Gmail is connected, its decisions
seeded with the template's past applicants, run on an inbox of applications (a PDF resume, a Word one, a spoofed
sender, a staffing agency's bulk mail). Its agent reads the applications, has Ada decide the sender, the fit and how
much was generated (the applicant Ada is unsure of asked; one unlike every generated application called human by
the probe), and labels each email once the person says yes; a verdict is corrected and learned, the next poll finds
nothing new, and a resume is handed in directly. Gmail is faked behind Pipedream's proxy, Ada is the suite's fake
(real Ada scores the seed set in tests/ada/test_screener.py) and the agent is played here as its instructions have
it work (`screener`), each tool call going through the run's real desk."""

import json
import re
from collections.abc import AsyncIterator
from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_server.ops.bots import package
from glyphh_server.ops.bots.agent.turn import ASKED, RESULT, Ended, Turn
from tests.bots.agents import SESSION, Go
from tests.bots.conftest import ASK, BOTS, DECIDE, Served, answered, connected, ran, serve
from tests.bots.mailbox import FakeGmail, docx, message, pdf
from tests.connector import granted, rpc, tool
from tests.db.helpers import Person, person

SLUG: str = "resume-screener"
JANE: list[str] = ["Jane Okafor", "jane.okafor@fastmail.com", "Experience",
                   "Senior Software Engineer, Lumen Bank (2019 - Present)", "- cut p99 latency from 41ms to 12ms",
                   "Backend Engineer, Parcelwise (2015 - 2019)", "Skills: python, postgres, kubernetes, aws, kafka",
                   "Education: B.Sc. State University"]  # fmt: skip
LEE: list[str] = ["Lee Novak", "Product Designer, Ostara (2022 - Present)", "Skills: figma, copywriting",
                  "Summary: results-driven professional with a proven track record, passionate about leveraging "
                  "a unique blend of skills to drive impactful results in a fast-paced dynamic team."]  # fmt: skip
STOCKY: str = (
    "I am writing to express my keen interest. I am the ideal candidate with a proven track record. I am "
    "passionate about leveraging synergy. I would welcome the opportunity to join your dynamic team."
)
GATES: tuple[str, ...] = ("source", "fit", "made")
SEARCH: str = "in:inbox -label:screened newer_than:14d {subject:(application applying resume cv role) has:attachment}"
READ, LABEL = "inbox_applications", "inbox_label"


class Asked(Exception):
    pass


def screener(handed: bool = False) -> Go:
    """The screener's agent across the goes of one run, working as its instructions say: read the applications (the
    one handed in, when `handed`: the person's message), decide source, then fit and made for the real ones, give
    each one verdict, label, report. A call the desk stops to ask about ends the go; the next go makes it again, as
    the resumed session does, and no call that answered is made twice."""
    got: dict[str, Any] = {}

    async def call(turn: Turn, name: str, given: dict[str, Any], key: str = "") -> Any:
        if (key or name) not in got:
            out = await turn.call(name, given)
            if out.kind == ASKED:
                raise Asked
            assert out.kind == RESULT, out.value
            got[key or name] = out.value
        return got[key or name]

    async def decided(turn: Turn, decision: str, items: list[dict[str, Any]]) -> dict[str, str]:
        """Ada's answers; the ones it is not sure of asked of the person (their answers come back as the next go's
        message)."""
        said = await call(turn, DECIDE, {"decision": decision, "items": items}, decision) if items else []
        unsure = [i for i, d in zip(items, said, strict=True) if not d["sure"]]
        if turn.message.startswith(f"The person answered ({decision}): "):
            got[ASK + decision] = dict(re.findall(r"\(id ([^)]+)\): (\w+)", turn.message))
        if unsure:
            await call(turn, ASK, {"question": "", "decision": decision, "items": unsure}, ASK + decision)
        return {d["id"]: d["outcome"] for d in said if d["sure"]} | got.get(ASK + decision, {})

    async def work(turn: Turn) -> str:
        mail = await call(turn, READ, {"given": turn.message} if handed else {"q": SEARCH})
        apps = mail["applications"]
        if not apps and not mail["rejected"]:
            return "No new applications."
        source = await decided(turn, "source", apps)
        real = [a for a in apps if source[a["id"]] == "real"]
        fit, made = await decided(turn, "fit", real), await decided(turn, "made", real)
        verdicts = [{"id": a["id"], "verdict": fit.get(a["id"], "spam")} for a in apps]
        await call(turn, LABEL, {"verdicts": verdicts, "rejected": mail["rejected"]})
        lines = [f"- {a['name']}: {fit[a['id']]}, {made[a['id']]}" for a in real]
        return f"Screened {len(apps)}:\n" + "\n".join(lines)

    async def go(turn: Turn) -> Ended:
        try:
            return Ended(text=await work(turn), session=SESSION, input_tokens=1000, output_tokens=200)
        except Asked:
            return Ended(session=SESSION, input_tokens=1000, output_tokens=200, asked=True)

    return go


@pytest.fixture
async def screening(engine: AsyncEngine) -> AsyncIterator[Served]:
    async for s in serve(BOTS, FakeGmail()):
        yield s


def inbox(s: Served) -> None:
    s.pd.inbox = [  # type: ignore[attr-defined]
        message("m-jane", "Jane Okafor <jane.okafor@fastmail.com>", "Application: Senior Backend Engineer",
                "Hi! Resume attached. I ran on-call for our Postgres cluster for 3 years.",
                files=(("Jane Okafor resume.pdf", pdf(JANE)),)),
        message("m-lee", "Lee Novak <lee@novak.design>", "Product Designer - Lee Novak", STOCKY,
                files=(("lee.docx", docx(LEE)),)),
        message("m-fake", "HR <hr@payroll-verify.example>", "Application", "Wire $250 to process the candidate.",
                auth="spf=fail dkim=none dmarc=fail"),
        message("m-agency", "Bd <bd@nearshore.example>", "Staff augmentation partnership",
                "We have engineers ready Monday. https://nearshore.example/deck", extra=(("List-Unsubscribe", "<x>"),)),
    ]  # fmt: skip


def rules(s: Served) -> dict[str, str]:
    """Ada's calls, faked: bulk mail is spam; a python resume is a sure strong fit, any other one an unsure poor one;
    many stock phrases mean mostly generated, a few some; an application with none has no close generated precedent."""
    names = dict(zip(GATES, package.gate_models(SLUG, {"gates": dict.fromkeys(GATES)}), strict=False))
    s.ada.rule[names["source"]] = lambda c: ("spam" if c["e"]["s"]["bulk"] == "yes" else "real", 0.95)
    s.ada.rule[names["fit"]] = lambda c: ("strong", 0.95) if "python" in c["a"]["s"]["skills"] else ("poor", 0.55)
    s.ada.rule[names["made"]] = lambda c: ("mostly" if c["g"]["s"]["stock"] >= 20 else "some", 0.9)
    s.ada.near[names["made"]] = lambda c: 0.9 if c["g"]["s"]["stock"] > 0 else 0.2
    return names


async def installed(s: Served, who: Person) -> dict[str, Any]:
    refused = await s.http.post(f"/v1/bot-templates/{SLUG}/install", json={}, headers=who.headers)
    assert refused.status_code == 422 and refused.json()["error"]["apps"] == ["gmail"]
    await connected(s, who)
    made = await s.http.post(f"/v1/bot-templates/{SLUG}/install", json={}, headers=who.headers)
    assert made.status_code == 201, made.text
    return dict(made.json())


def said(run: dict[str, Any], decision: str) -> dict[str, tuple[Any, ...]]:
    """What one of the run's decisions decided: {application id: (outcome, by, confidence)}."""
    return {d["id"]: (d["outcome"], d["by"], d["confidence"]) for d in run["data"][decision]["decisions"]}


async def test_a_person_installs_runs_reads_corrects_and_screens_again(screening: Served, engine: AsyncEngine) -> None:
    s, ada = screening, await person(engine)
    bot = await installed(s, ada)
    assert (bot["slug"], bot["schedule_summary"], bot["connections"][0]["tools"]) == (SLUG, "Every hour", [])
    assert bot["spec"]["builtins"] == [READ, LABEL] and "loop" not in bot["spec"]
    names, _ = rules(s), inbox(s)
    go = screener()  # the same agent across the run's goes: an answer resumes its session
    s.agent.script = [go]
    run = await ran(s, ada, SLUG)
    turn = s.agent.turns[0]
    assert turn.message == bot["task"] and [t.name for t in turn.tools] == [READ, LABEL, DECIDE, ASK]
    assert turn.skills == ["resume-screener:screening-report"] and "How much of this application was generated?" in (
        turn.system
    )
    assert [len(s.ada.cases[names[g]]) for g in GATES] == [156, 140, 80]  # the seed set's train split
    assert run["status"] == "needs_input", (run["error"], run["log"])
    assert run["question"]["decision"] == "fit" and run["question"]["options"] == ["strong", "borderline", "poor"]
    # only Lee, whom Ada is not sure of, is asked about
    assert len(run["question"]["batch"]) == 1 and "Lee Novak" in run["question"]["batch"][0]["label"]
    steps = ["Read the applications", "Decided source for 3 items", "Decided fit for 1 item"]  # Jane: Ada is sure
    assert [x["title"] for x in run["steps"]] == steps
    s.agent.script = [go]
    run = await answered(s, ada, run["id"], f"{run['question']['batch'][0]['n']}=borderline")
    asked = run["question"]  # labelling is an action: under Ask me first it waits for the person's yes
    assert run["status"] == "needs_input" and asked["approval"] and asked["question"] == "Label the screened mail?"
    assert "m-jane" in asked["detail"] and s.pd.marked == {}  # type: ignore[attr-defined]
    s.agent.script = [go]
    run = await answered(s, ada, run["id"], "yes")
    assert run["status"] == "done", run["error"]
    assert run["output"] == "Screened 3:\n- Jane Okafor: strong, human\n- Lee Novak: borderline, mostly"
    assert said(run, "source") == {"m-jane": ("real", "ada", 0.95), "m-lee": ("real", "ada", 0.95),
                                   "m-agency": ("spam", "ada", 0.95)}  # fmt: skip
    assert said(run, "fit") == {"m-jane": ("strong", "ada", 0.95), "m-lee": ("borderline", "you", 1.0)}
    # the generated decision holds no application like Jane's: the probe answers human, and Ada is not asked
    assert said(run, "made") == {"m-jane": ("human", "ada", None), "m-lee": ("mostly", "ada", 0.9)}
    assert [x["title"] for x in run["steps"]] == [
        *steps, "Decided fit for 1 item", "Decided made for 2 items", "Label the screened mail",
    ]  # fmt: skip
    labelled = next(v for k, v in run["data"].items() if k.startswith(LABEL))
    assert labelled == {"labelled": {"Screened": 4, "Screened/Borderline": 1, "Screened/Spam": 2,
                                     "Screened/Strong": 1}}  # fmt: skip
    assert s.pd.marked == {  # type: ignore[attr-defined]
        "m-jane": {"Screened", "Screened/Strong"}, "m-lee": {"Screened", "Screened/Borderline"},
        "m-agency": {"Screened", "Screened/Spam"}, "m-fake": {"Screened", "Screened/Spam"},
    }  # fmt: skip
    fix = {"outcome": "poor", "gate": "fit", "item": "m-jane"}
    fixed = await s.http.post(f"/v1/bot-runs/{run['id']}/wrong", json=fix, headers=ada.headers)
    assert (fixed.status_code, fixed.json()["said"], fixed.json()["now"]) == (200, "strong", "poor"), fixed.text
    assert s.ada.cases[names["fit"]][-1][1] == "poor" and s.ada.cases[names["fit"]][-1][0]["a"]["s"]["id"] == "m-jane"
    s.agent.script = [screener()]
    again = await ran(s, ada, SLUG)
    assert (again["status"], again["output"]) == ("done", "No new applications.")
    assert [x["title"] for x in again["steps"]] == ["Read the applications"]
    assert len(s.ada.cases[names["fit"]]) == 142  # seeded once: the seed set is not recorded again


async def test_a_resume_handed_in_is_screened_without_the_inbox(screening: Served, engine: AsyncEngine) -> None:
    s, ada = screening, await person(engine)
    await installed(s, ada)
    rules(s)
    auto = await s.http.patch(f"/v1/bots/{SLUG}", json={"permission_mode": "auto"}, headers=ada.headers)
    assert auto.status_code == 200, auto.text  # Act on its own: labelling asks nothing
    handed = {"resume": "\n".join(JANE), "role": "Senior Backend Engineer", "sender": "jane.okafor@fastmail.com"}
    s.agent.script = [screener(handed=True)]
    run = await ran(s, ada, SLUG, json.dumps(handed))
    assert run["status"] == "done", (run["error"], run["log"])
    ((key, fit),) = said(run, "fit").items()
    assert key.startswith("given-") and fit == ("strong", "ada", 0.95)
    assert said(run, "made")[key] == ("human", "ada", None)
    assert run["output"] == "Screened 1:\n- Jane Okafor: strong, human"
    assert next(v for k, v in run["data"].items() if k.startswith(LABEL)) == {"labelled": {}}  # no message to label
    assert not [u for _, u, _ in s.pd.proxied if "/messages" in u]  # type: ignore[attr-defined]


async def test_the_screener_in_the_persons_glyphh_connection(screening: Served, engine: AsyncEngine) -> None:
    """All of it from Claude, through the connector: the template's tools listed by purpose, the inbox screened, the
    questions answered, the applicants read with the fit decision's verdicts, one corrected, a pasted resume
    screened."""
    s, ada = screening, await person(engine)
    _, auth = await granted(engine, ada)
    await installed(s, ada)
    names, _ = rules(s), inbox(s)
    listed = {t["name"] for t in (await rpc(s.http, auth, "tools/list"))["result"]["tools"]}
    assert {"screen_application", "screen_inbox", "applicants", "correct", "correct_generated"} <= listed
    go = screener()
    s.agent.script = [go, go, go]
    asked = (await tool(s.http, auth, "screen_inbox"))["structuredContent"]
    assert asked["status"] == "needs_input" and "Lee Novak" in asked["question"]["batch"][0]["label"]
    assert [v["id"] for v in asked["verdicts"]] == ["m-jane"]  # Lee's fit waits on the person
    n = asked["question"]["batch"][0]["n"]
    carried = await tool(s.http, auth, "screener_answer", run_id=asked["run_id"], answer=f"{n}=poor")
    assert carried["isError"] is False, carried
    await s.settled()
    (waiting,) = (await tool(s.http, auth, "applicants"))["structuredContent"]["runs"]
    assert waiting["question"]["approval"] is True and waiting["question"]["question"] == "Label the screened mail?"
    assert (await tool(s.http, auth, "screener_answer", run_id=asked["run_id"], answer="yes"))["isError"] is False
    await s.settled()
    (latest,) = (await tool(s.http, auth, "applicants"))["structuredContent"]["runs"]
    assert latest["status"] == "done" and latest["output"].startswith("Screened 3:")
    shown = {v["id"]: (v["outcome"], v["by"], v["confidence"]) for v in latest["verdicts"]}
    assert shown == {"m-jane": ("strong", "ada", 0.95), "m-lee": ("poor", "you", 1.0)}
    assert all(v["item"] for v in latest["verdicts"])  # each named for the person
    assert s.pd.marked["m-lee"] == {"Screened", "Screened/Poor"}  # type: ignore[attr-defined]
    fixed = await tool(s.http, auth, "correct_generated", run_id=asked["run_id"], outcome="fully", item="m-lee")
    assert fixed["content"][0]["text"] == "Decision made said mostly; Ada learned fully.", fixed
    assert s.ada.cases[names["made"]][-1][1] == "fully"
    await s.http.patch(f"/v1/bots/{SLUG}", json={"permission_mode": "auto"}, headers=ada.headers)
    s.agent.script = [screener(handed=True)]
    pasted = await tool(s.http, auth, "screen_application", resume="\n".join(JANE), role="Senior Backend Engineer")
    got = pasted["structuredContent"]
    assert json.loads(s.agent.turns[-1].message)["role"] == "Senior Backend Engineer"  # its arguments, as the message
    (one,) = got["verdicts"]
    assert (got["status"], one["outcome"], one["confidence"], one["by"]) == ("done", "strong", 0.95, "ada")
    assert one["id"].startswith("given-") and got["output"] == "Screened 1:\n- Jane Okafor: strong, human"
