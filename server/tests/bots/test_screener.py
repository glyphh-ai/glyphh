"""The Resume Screener as a person uses it: installed from the marketplace once Gmail is connected, its gates seeded
with the template's past applicants, run on an inbox of applications (a PDF resume, a Word one, a spoofed sender, a
staffing agency's bulk mail), the applicant Ada is unsure of asked, the verdicts read off the run and labelled in
Gmail, one corrected and learned, the next poll finding nothing new, and a resume handed in directly. Gmail is faked
behind Pipedream's proxy and Ada is the suite's fake (real Ada scores the seed set in tests/ada/test_screener.py)."""

import json
from collections.abc import AsyncIterator
from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_server.ops.bots import package
from tests.bots.conftest import BOTS, Served, connected, serve
from tests.bots.mailbox import FakeGmail, docx, message, pdf
from tests.bots.test_runs import answered, started
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


def verdicts(run: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {v["id"]: v for v in run["data"]["verdicts"]["verdicts"]}


async def test_a_person_installs_runs_reads_corrects_and_screens_again(screening: Served, engine: AsyncEngine) -> None:
    s, ada = screening, await person(engine)
    bot = await installed(s, ada)
    assert (bot["slug"], bot["schedule_summary"], bot["connections"][0]["tools"]) == (SLUG, "Every hour", [])
    names, _ = rules(s), inbox(s)
    run = await started(s, ada, given="", slug=SLUG)
    assert [len(s.ada.cases[names[g]]) for g in GATES] == [156, 140, 80]  # the seed set's train split
    assert run["status"] == "needs_input", (run["error"], run["log"])
    assert [b["label"] for b in run["question"]["batch"]] == ["Lee Novak - product designer"]
    run = await answered(s, ada, run, f"{run['question']['batch'][0]['n']}=borderline")
    assert run["status"] == "done", run["error"]
    got = verdicts(run)
    assert set(got) == {"m-jane", "m-lee", "m-agency"}
    jane, lee = got["m-jane"], got["m-lee"]
    assert (jane["verdict"], jane["fit"], jane["generated"]) == (
        "strong", {"outcome": "strong", "confidence": 0.95, "by": "ada"},
        {"outcome": "human", "confidence": None, "by": "probe", "nearest": 0.2, "reference": 0.9})  # fmt: skip
    assert (jane["years"], jane["email"], "kubernetes" in jane["skills"]) == (11, "jane.okafor@fastmail.com", True)
    assert (lee["verdict"], lee["fit"]["by"], lee["generated"]["outcome"]) == ("borderline", "person", "mostly")
    assert got["m-agency"]["verdict"] == "spam" and run["data"]["probe"]["reference"]["n"] == 22
    assert [r["id"] for r in run["data"]["verdicts"]["rejected"]] == ["m-fake"]
    assert run["data"]["verdicts"]["summary"] == "1 strong, 1 borderline, 1 spam; 1 refused by the sender checks"
    assert s.pd.marked == {  # type: ignore[attr-defined]
        "m-jane": {"Screened", "Screened/Strong"}, "m-lee": {"Screened", "Screened/Borderline"},
        "m-agency": {"Screened", "Screened/Spam"}, "m-fake": {"Screened", "Screened/Spam"},
    }  # fmt: skip
    said = {"outcome": "poor", "gate": "fit", "item": "m-jane"}
    fixed = await s.http.post(f"/v1/bot-runs/{run['id']}/wrong", json=said, headers=ada.headers)
    assert (fixed.status_code, fixed.json()["said"], fixed.json()["now"]) == (200, "strong", "poor"), fixed.text
    assert s.ada.cases[names["fit"]][-1][1] == "poor" and s.ada.cases[names["fit"]][-1][0]["a"]["s"]["id"] == "m-jane"
    again = await started(s, ada, given="", slug=SLUG)
    assert (again["status"], again["data"]["verdicts"]["summary"]) == ("done", "no new applications")
    assert len(s.ada.cases[names["fit"]]) == 142  # seeded once: the seed set is not recorded again


async def test_a_resume_handed_in_is_screened_without_the_inbox(screening: Served, engine: AsyncEngine) -> None:
    s, ada = screening, await person(engine)
    await installed(s, ada)
    rules(s)
    handed = {"resume": "\n".join(JANE), "role": "Senior Backend Engineer", "sender": "jane.okafor@fastmail.com"}
    run = await started(s, ada, given=json.dumps(handed), slug=SLUG)
    assert run["status"] == "done", (run["error"], run["log"])
    (one,) = run["data"]["verdicts"]["verdicts"]
    assert (one["id"].startswith("given-"), one["verdict"], one["role"]) == (True, "strong", "senior backend engineer")
    assert run["data"]["label"] == {"labelled": {}}
    assert not [u for _, u, _ in s.pd.proxied if "/messages" in u]  # type: ignore[attr-defined]


async def test_the_screener_in_the_persons_glyphh_connection(screening: Served, engine: AsyncEngine) -> None:
    """All of it from Claude, through the connector: the template's tools listed by purpose, the inbox screened, the
    question answered, the applicants read with their verdicts, one corrected, a pasted resume screened."""
    s, ada = screening, await person(engine)
    _, auth = await granted(engine, ada)
    await installed(s, ada)
    names, _ = rules(s), inbox(s)
    listed = {t["name"] for t in (await rpc(s.http, auth, "tools/list"))["result"]["tools"]}
    assert {"screen_application", "screen_inbox", "applicants", "correct", "correct_generated"} <= listed
    asked = (await tool(s.http, auth, "screen_inbox"))["structuredContent"]
    assert asked["status"] == "needs_input" and asked["question"]["batch"][0]["label"] == "Lee Novak - product designer"
    n = asked["question"]["batch"][0]["n"]
    said = await tool(s.http, auth, "screener_answer", run_id=asked["run_id"], answer=f"{n}=poor")
    assert said["isError"] is False, said
    await s.settled()
    (latest,) = (await tool(s.http, auth, "applicants"))["structuredContent"]["runs"]
    assert latest["status"] == "done" and latest["verdicts"]["summary"].startswith("1 strong, 1 poor, 1 spam")
    shown = {v["id"]: (v["verdict"], (v["generated"] or {}).get("outcome")) for v in latest["verdicts"]["verdicts"]}
    assert shown == {"m-jane": ("strong", "human"), "m-lee": ("poor", "mostly"), "m-agency": ("spam", None)}
    fixed = await tool(s.http, auth, "correct_generated", run_id=asked["run_id"], outcome="fully", item="m-lee")
    assert fixed["content"][0]["text"] == "Gate made said mostly; it learned fully.", fixed
    assert s.ada.cases[names["made"]][-1][1] == "fully"
    pasted = await tool(s.http, auth, "screen_application", resume="\n".join(JANE), role="Senior Backend Engineer")
    (one,) = pasted["structuredContent"]["verdicts"]["verdicts"]
    got = (pasted["structuredContent"]["status"], one["verdict"], one["fit"]["confidence"], one["generated"]["by"])
    assert got == ("done", "strong", 0.95, "probe")
