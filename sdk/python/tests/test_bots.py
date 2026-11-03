"""Bots: a package is checked whole; the runner walks the loop (code steps, learned gates, lean Claude steps, approvals,
hard ends), keeps its runs, carries on after a question and takes corrections; the orchestrator makes bots through
its builder, decides trust and keep from records, and learns from every run. Ada and `claude` are fakes."""

from __future__ import annotations

import datetime as dt
import json
import subprocess
from pathlib import Path
from typing import Any, Dict, List

import pytest

from conftest import DIGEST_PROGRAM, FakeAda, FakeClaude, digest_spec, write_bot
from glyphh.bots import (
    USER_AGENT,
    Bot,
    BotError,
    Claude,
    Orchestrator,
    api_key,
    calendar,
    check_model_name,
    fill,
    memory_context,
    model_name,
    slug_of,
)
from glyphh.bots import routine as routines
from glyphh.bots.orchestrator import EXAMPLE, EXAMPLE_ITEMS, FIRST_RULE

REPO = Path(__file__).resolve().parents[3]
EXAMPLES = REPO / "examples" / "bots"
ITEMS = {"items": [{"title": "one"}, {"title": "two"}]}


class World:
    """What a bot's code reaches, and what it tells the person."""

    def __init__(self, answer: Any = ITEMS) -> None:
        self.answer, self.asked, self.notified = answer, [], []

    def fetch(self, req: Any, timeout: float) -> Any:
        self.asked.append((req.full_url, dict(req.header_items())))
        return self.answer

    def notify(self, title: str, text: str) -> None:
        self.notified.append((title, text))


@pytest.fixture
def world() -> World:
    return World()


@pytest.fixture
def orch(fake_ada: FakeAda, fake_claude: FakeClaude, bots_home: Path, world: World) -> Orchestrator:
    return Orchestrator(fake_ada, root=bots_home, claude=Claude(run=fake_claude), fetch=world.fetch,
                        notify=world.notify, today=lambda: dt.date(2026, 11, 3))


@pytest.fixture
def digest(orch: Orchestrator, bot_folder: Path) -> Orchestrator:
    orch.install(bot_folder)
    return orch


# the package


def test_the_examples_load_and_the_builders_examples_are_launch_watch_and_hn_reader_as_shipped():
    for name in ("launch_watch", "lab", "coder", "hn_reader"):
        bot = Bot.load(EXAMPLES / name)
        assert bot.slug == name and all(len(m) <= 63 for m in bot.models())
    for folder, name, skill in ((EXAMPLE, "launch_watch", "launch-summary"), (EXAMPLE_ITEMS, "hn_reader", "hn-digest")):
        shipped = sorted(p.relative_to(folder) for p in folder.rglob("*") if p.is_file() and "__pycache__" not in p.parts)
        assert shipped == [Path("agent.md"), Path("bot.json"), Path("program.py"), Path(f"skills/{skill}/SKILL.md")]
        for rel in shipped:
            assert (folder / rel).read_text() == (EXAMPLES / name / rel).read_text(), rel


def test_a_package_names_its_models_within_adas_63():
    bot = Bot.load(EXAMPLES / "launch_watch")
    assert bot.gate_model("worth_sending") == "bot-launch-watch-gate-worth-sending"
    assert bot.memory_model("instructions") == "bot-launch-watch-instructions"
    assert model_name("orch", "make_bot") == "orch-make-bot"
    assert check_model_name("a" * 63) is None and "64 characters" in str(check_model_name("a" * 64))
    assert "lower case" in str(check_model_name("Bot-X"))


def problems(folder: Path) -> List[str]:
    with pytest.raises(BotError) as e:
        Bot.load(folder)
    assert e.value.code == "E_BOT"
    return e.value.problems or [e.value.message]


def test_every_problem_with_a_package_is_said_at_once(tmp_path):
    spec = digest_spec(slug="Digest", name="", touches="tweets", hosts="x", seed={"mood": []}, limits={"seconds": 0},
                       routine={"cron": "daily"})
    spec["gates"]["worth"]["outcomes"] = ["send"]
    spec["gates"]["Bad Gate"] = {}
    spec["gates"]["x"] = {"case": 3, "outcomes": ["a", "a"], "spec": {}}
    spec["loop"][1]["on"] = {"send": "nowhere"}
    spec["loop"][2]["skill"] = "missing"
    spec["loop"].append({"id": "gx", "gate": "x", "on": {}})
    spec["loop"].append({"id": "both", "run": "fetch", "agent": "x"})
    spec["loop"].append({"id": "ghost", "gate": "nope", "on": {}})
    spec["loop"].append({"id": "empty", "run": ""})
    spec["loop"].append({"id": "say", "run": "deliver", "approval": ""})
    found = " | ".join(problems(write_bot(tmp_path / "bad", spec)))
    for said in ("slug must be snake_case", "name is missing", "touches must be one of", "hosts must be",
                 "seed must map", "limits must be", "routine must be", "outcomes must be two or more",
                 "gate Bad Gate: its name", "gate x: case must", "gate x: outcomes must differ", "gate x: spec",
                 "on must map each", "on send goes to nowhere", "no skills/missing", "exactly one of run, gate, agent or ladder", "no gate nope",
                 "run must be a non-empty", "approval must say"):
        assert said in found, said


def test_a_package_that_would_act_outward_unasked_is_refused(tmp_path):
    spec = digest_spec()
    del spec["loop"][3]["approval"]
    assert any("act outward unasked" in p for p in problems(write_bot(tmp_path / "d", spec)))


def test_a_package_with_a_long_slug_or_gate_is_refused(tmp_path):
    spec = digest_spec(slug="d" * 47)
    assert any("too long" in p for p in problems(write_bot(tmp_path / "long", spec)))
    spec = digest_spec()
    spec["gates"]["g" * 50] = spec["gates"]["worth"]
    assert any("at most 63" in p for p in problems(write_bot(tmp_path / "gate", spec)))


def test_a_package_whose_program_lacks_a_function_or_does_not_import_is_refused(tmp_path):
    assert any("no function fetch" in p for p in problems(write_bot(tmp_path / "a", program="def worth_case(c, d): pass\n")))
    assert any("does not import" in p for p in problems(write_bot(tmp_path / "b", program="import nothing_here\n")))
    folder = write_bot(tmp_path / "c")
    (folder / "program.py").unlink()
    (folder / "agent.md").write_text("no frontmatter")
    found = problems(folder)
    assert "there is no program.py" in found and "agent.md has no frontmatter name" in found


def test_what_is_not_a_package_is_said(tmp_path):
    assert "not a bot" in problems(tmp_path)[0]
    (tmp_path / "bot.json").write_text("{nope")
    assert "not JSON" in problems(tmp_path)[0]
    (tmp_path / "bot.json").write_text("[]")
    assert "not a JSON object" in problems(tmp_path)[0]
    (tmp_path / "bot.json").write_text(json.dumps(digest_spec(loop=[])))
    assert any("loop must be" in p for p in problems(tmp_path))
    (tmp_path / "bot.json").write_text(json.dumps(digest_spec(loop=[{"run": "x"}], gates=[])))
    found = problems(tmp_path)
    assert any("gates must be an object" in p for p in found) and any("with an id" in p for p in found)
    (tmp_path / "bot.json").write_text(json.dumps(digest_spec(loop=[{"id": "a", "run": "fetch"}, {"id": "a", "run": "fetch"}])))
    assert any("step ids must differ" in p for p in problems(tmp_path))


def test_fill_puts_earlier_steps_data_in():
    data = {"a": {"n": 1}, "b": "text"}
    assert fill("$a", data) == {"n": 1}
    assert fill("A: $a, B: $b, C: $c", data) == 'A: {"n": 1}, B: "text", C: $c'
    assert fill(None, data) is None and fill(3, data) == 3


# the runner


def test_a_first_run_asks_at_the_gate_then_at_the_approval_and_learns(digest, fake_ada, fake_claude, world):
    runner = digest.runner("digest")
    first = runner.run(routine=True)
    assert first.status == "needs_input" and first.options == ["send", "skip"] and "Worth it?" in first.question
    assert "no precedents yet" in first.question and world.notified == [("Digest", "needs_input at worth: glyphh bot continue digest")]
    url, headers = world.asked[0]
    assert url == "https://api.example.com/items" and headers["User-agent"] == USER_AGENT

    second = runner.resume("send")
    assert second.status == "needs_input" and second.options == ["yes", "no"] and "send the digest" in second.question
    gate = "bot-digest-gate-worth"
    assert fake_ada.outcomes(gate) == ["send"]
    case = fake_ada.cases[gate][0][0]
    assert case == {"d": {"s": {"new": 2, "run": first.run_id}}}

    argv, cwd = fake_claude.calls[0]
    for flag in ("--tools", "--strict-mcp-config", "--no-session-persistence", "--setting-sources"):
        assert flag in argv
    assert argv[argv.index("--tools") + 1] == "" and argv[argv.index("--max-turns") + 1] == "2"
    assert json.loads(argv[argv.index("--agents") + 1])["digest"]["model"] == "sonnet"
    prompt = argv[-1]
    assert "Lead with the count." in prompt and "Short." in prompt and "One line per item." in prompt
    assert '"title": "one"' in prompt

    third = runner.resume("yes")
    assert third.status == "done" and third.run_id == first.run_id
    assert (digest.root / "digest" / "out" / "digest.md").read_text() == "an answer"
    assert third.data["deliver"]["today"] == "2026-11-03" and runner.store.state("last") == first.run_id
    assert any("approval send the digest: yes" in line for line in third.log)
    assert any("an answer" in m for m in fake_ada.outcomes("bot-digest-memory"))
    assert any("bot digest" in m and "worth send by person" in m for m in fake_ada.outcomes("orch-memory"))


def test_a_gate_ada_is_sure_of_decides_without_asking(digest, fake_ada):
    fake_ada.cases["bot-digest-gate-worth"].append(({}, "skip"))
    fake_ada.sure["bot-digest-gate-worth"] = "skip"
    result = digest.runner("digest").run()
    assert result.status == "done" and result.reason == "gate worth said skip: the run ends here"
    assert result.data["_gates"]["worth"]["by"] == "ada" and fake_ada.outcomes("bot-digest-gate-worth") == ["skip"]


def test_an_answer_at_the_terminal_is_asked_until_it_is_one_of_the_options(digest, fake_ada):
    said = iter(["maybe", "SEND\n", "yes"])
    asked: List[str] = []

    def ask(question: str, options: List[str]) -> str:
        asked.append(question)
        return next(said)

    digest.ask = ask
    result = digest.runner("digest").run()
    assert result.status == "done" and len(asked) == 3 and fake_ada.outcomes("bot-digest-gate-worth") == ["send"]


def test_the_program_ends_a_run_and_a_no_stops_the_outward_step(digest, fake_ada, world):
    world.answer = {"items": []}
    ended = digest.runner("digest").run()
    assert ended.status == "done" and ended.reason == "the program ended the run: nothing new"
    world.answer = ITEMS
    digest.ask = lambda q, o: "send" if "send" in o else "no"
    refused = digest.runner("digest").run()
    assert refused.status == "done" and refused.reason == "the person said no to send the digest"
    assert not (digest.root / "digest" / "out").exists()


def test_a_trusted_bot_acts_without_the_approval(digest):
    digest.verdict("digest", "trust", "autonomous")
    digest.ask = lambda q, o: "send"
    result = digest.runner("digest").run()
    assert result.status == "done" and not any("approval" in line for line in result.log)


def test_a_failing_step_fails_the_run_said_plainly(orch, tmp_path, world, fake_claude):
    spec = digest_spec(loop=[{"id": "boom", "run": "boom"}], touches="read_only")
    orch.install(write_bot(tmp_path / "b" / "digest", spec))
    result = orch.runner("digest").run(routine=True)
    assert result.status == "failed" and result.reason == "boom: RuntimeError: it broke"
    assert world.notified == [("Digest", "failed at boom: glyphh bot continue digest")]

    fake_claude.fail = "rate limited"
    orch.install(write_bot(tmp_path / "c" / "digest", digest_spec(loop=[{"id": "w", "agent": "x"}], touches="read_only")))
    failed = orch.runner("digest").run()
    assert failed.status == "failed" and "Claude failed: rate limited" in failed.reason


def test_code_reaches_only_its_hosts_over_https(orch, tmp_path):
    program = DIGEST_PROGRAM + "\n\ndef away(ctx, i):\n    return ctx.http_json(i)\n\n\ndef gate_x(ctx, i):\n    return ctx.gate('nope')\n"
    for url in ("https://evil.example.com/x", "http://api.example.com/items"):
        spec = digest_spec(loop=[{"id": "a", "run": "away", "input": url}], touches="read_only")
        orch.install(write_bot(tmp_path / url.split(":")[0] / "digest", spec, program))
        result = orch.runner("digest").run()
        assert result.status == "failed" and "is not https on one of the bot's hosts" in result.reason
    orch.install(write_bot(tmp_path / "g" / "digest", digest_spec(loop=[{"id": "g", "run": "gate_x"}], touches="read_only"), program))
    assert orch.runner("digest").run().reason == "the bot has no gate nope"


def test_a_gate_looping_back_for_ever_is_stopped(orch, tmp_path, fake_ada):
    spec = digest_spec(loop=[{"id": "fetch", "run": "fetch"}, {"id": "worth", "gate": "worth", "on": {"send": "fetch", "skip": "end"}}],
                       limits={"steps": 7}, touches="read_only")
    orch.install(write_bot(tmp_path / "l" / "digest", spec))
    fake_ada.cases["bot-digest-gate-worth"].append(({}, "send"))
    fake_ada.sure["bot-digest-gate-worth"] = "send"
    assert orch.runner("digest").run().reason == "the run took more than 7 steps"


def test_continue_takes_only_an_answer_to_the_question(digest):
    runner = digest.runner("digest")
    with pytest.raises(BotError, match="no run is waiting"):
        runner.resume("send")
    runner.run(routine=True)
    with pytest.raises(BotError, match="waits for an answer: one of send, skip"):
        runner.resume()
    with pytest.raises(BotError, match="not an answer"):
        runner.resume("perhaps")
    digest.ask = lambda q, o: "skip"
    assert digest.runner("digest").resume().reason == "gate worth said skip: the run ends here"


def test_wrong_records_what_the_gate_should_have_said(digest, fake_ada):
    digest.ask = lambda q, o: "send" if "send" in o else "yes"
    runner = digest.runner("digest")
    run = runner.run()
    said = runner.wrong(run.run_id, "skip")
    assert said == {"bot": "digest", "run": run.run_id, "gate": "worth", "said": "send", "by": "person", "now": "skip"}
    assert fake_ada.outcomes("bot-digest-gate-worth") == ["send", "skip"]
    assert digest.record_of("digest")["overruled_pct"] == 100
    with pytest.raises(BotError, match="no run nope"):
        runner.wrong("nope", "skip")
    with pytest.raises(BotError, match="not one of gate worth"):
        runner.wrong(run.run_id, "later")
    with pytest.raises(BotError, match="did not pass gate other"):
        runner.wrong(run.run_id, "skip", gate="other")
    runner.store.save("two", "done", 0, {"_gates": {"a": {}, "b": {}}}, {}, "", [])
    with pytest.raises(BotError, match="several gates"):
        runner.wrong("two", "skip")
    runner.store.save("none", "done", 0, {}, {}, "", [])
    with pytest.raises(BotError, match="passed no gate"):
        runner.wrong("none", "skip")


def test_status_says_the_gates_memory_trust_and_last_runs(digest):
    digest.ask = lambda q, o: "skip"
    runner = digest.runner("digest")
    run = runner.run()
    got = runner.status()
    assert got["gates"] == {"worth": 1} and got["memory"]["personality"] == 1 and got["memory"]["instructions"] == 1
    assert got["trust"] == "ask_all" and got["keep"] == "keep" and got["touches"] == "sends"
    assert got["runs"][0] == {"run": run.run_id, "status": "done", "gates": {"worth": "skip by person"},
                              "reason": "gate worth said skip: the run ends here"}


def test_the_persons_glyphh_comes_before_the_agent(digest, fake_ada):
    mine = "me-0123456789ab-agentic-memory-instructions"
    fake_ada.create_model(mine, {"name": mine})
    fake_ada.cases[mine].append(({}, "Never use emoji."))
    bot = digest.bot("digest")
    known = memory_context(fake_ada, bot, "anything")
    assert known.index("The person's rules:\n- Never use emoji.") < known.index("Your rules:\n- Lead with the count.")
    bot.spec["reads_glyphh"] = False
    assert "Never use emoji" not in memory_context(fake_ada, bot, "anything")


def test_a_retired_bot_does_not_run(digest):
    digest.verdict("digest", "keep", "retire")
    with pytest.raises(BotError, match="retired"):
        digest.runner("digest").run()


# the orchestrator


def test_the_orchestrator_makes_its_models_once_with_its_first_rule(orch, fake_ada):
    made = orch.ensure()["made"]
    assert set(made) == {"orch-memory", "orch-instructions", "orch-personality", "orch-make-bot", "orch-trust-bot",
                         "orch-keep-bot"}
    assert orch.ensure()["made"] == [] and fake_ada.outcomes("orch-instructions") == [FIRST_RULE]
    assert fake_ada.specs["orch-trust-bot"]["output"]["ask_below"] == 0.8


def test_install_copies_the_package_and_takes_the_bot_on(orch, bot_folder, fake_ada):
    (bot_folder / "runs.sqlite").write_text("not copied")
    got = orch.install(bot_folder)
    assert got["made"] == ["bot-digest-gate-worth", "bot-digest-memory", "bot-digest-instructions", "bot-digest-personality"]
    assert got["trust"] == "ask_all" and got["seeded"] == 2 and (orch.root / "digest" / "program.py").exists()
    assert fake_ada.specs["bot-digest-gate-worth"]["output"]["ask_below"] == 0.7
    orch.verdict("digest", "trust", "ask_outward")
    again = orch.install("digest")
    assert again["made"] == [] and again["trust"] == "ask_outward"
    assert [b["bot"] for b in orch.adopted()] == ["digest"]
    with pytest.raises(BotError, match="no bot ghost"):
        orch.bot("ghost")
    with pytest.raises(BotError, match="trust is one of"):
        orch.adopt("digest", "x", "always")


def built(folder: Path, **over: Any) -> None:
    write_bot(folder, digest_spec(slug=folder.name, **{"touches": "read_only", **over}))


def test_new_asks_make_bot_then_the_builder_writes_a_bot_that_is_installed(orch, fake_ada, fake_claude):
    job = "Each morning, sum up the new items"
    waiting = orch.new(job, recurs=5, touches="sends")
    assert waiting["status"] == "needs_input" and waiting["options"] == ["make", "not_yet", "no"]
    assert "--answer" in waiting["answer_with"] and fake_claude.calls == []
    assert orch.new(job, answer="not_yet")["status"] == "not_made"

    fake_claude.build, fake_claude.answers = built, ["one gate, worth: is the day worth it"]
    made = orch.new(job, recurs=5, touches="sends", answer="make")
    assert made["status"] == "made" and made["bot"] == "morning_sum_up" and made["trust"] == "ask_all"
    argv, cwd = fake_claude.calls[0]
    assert cwd == str(orch.root / "morning_sum_up") and argv[argv.index("--tools") + 1] == "Read,Write"
    brief = argv[-1]
    assert "slug `morning_sum_up`" in brief and "How a bot is built" in brief and "=== program.py ===" in brief
    assert "This is the first bot you make." in brief and '"touches": "sends"' in brief
    assert fake_ada.outcomes("orch-make-bot") == ["not_yet", "make"]
    assert "bot-morning-sum-up-gate-worth" in fake_ada.specs
    assert any(m.startswith("made bot morning_sum_up") for m in fake_ada.outcomes("orch-memory"))

    second = orch.new(job, answer="make")
    assert second["bot"] == "morning_sum_up_2" and "made bot morning_sum_up" in fake_claude.calls[1][0][-1]
    with pytest.raises(BotError, match="touches is one of"):
        orch.new(job, touches="everything")
    with pytest.raises(BotError, match="not an answer to make_bot"):
        orch.new(job, answer="sure")


def test_make_bot_ada_is_sure_of_needs_no_answer(orch, fake_ada, fake_claude):
    orch.ensure()
    fake_ada.cases["orch-make-bot"].append(({}, "no"))
    fake_ada.sure["orch-make-bot"] = "no"
    assert orch.new("post my lunch online")["by"] == "ada"
    fake_claude.build = built
    orch.ask = lambda q, o: "make"
    del fake_ada.sure["orch-make-bot"]
    assert orch.new("post my lunch online")["status"] == "made"


def test_a_builders_bot_that_is_not_right_is_set_aside(orch, fake_claude):
    fake_claude.build = lambda folder: built(folder, touches="pays")
    with pytest.raises(BotError) as e:
        orch.new("pay my bills", touches="sends", answer="make")
    assert "more than the sends asked" in e.value.problems[0] and not (orch.root / "pay_bills").exists()
    assert len(list((orch.root / ".rejected").iterdir())) == 1
    fake_claude.build = lambda folder: write_bot(folder, digest_spec(slug="other"))
    with pytest.raises(BotError, match="its slug is other"):
        orch.new("pay my bills", touches="sends", answer="make")
    fake_claude.build = lambda folder: None
    with pytest.raises(BotError, match="has no bot.json"):
        orch.new("pay my bills", answer="make")


def test_review_decides_trust_and_keep_from_the_record(digest, fake_ada):
    digest.ask = lambda q, o: "skip"
    digest.runner("digest").run()
    digest.ask = None
    asked = digest.review()
    assert [(c["gate"], c["outcome"]) for c in asked] == [("trust_bot", None), ("keep_bot", None)]
    assert asked[0]["record"] == {"runs": 1, "ask_pct": 100, "overruled_pct": 0, "done_pct": 100}
    got = digest.review({"digest.trust_bot": "ask_outward", "digest.keep_bot": "keep"})
    assert [(c["outcome"], c["by"]) for c in got] == [("ask_outward", "person"), ("keep", "person")]
    assert digest.trust_of("digest") == "ask_outward"
    case = fake_ada.cases["orch-trust-bot"][0][0]["o"]["s"]
    assert case["touches"] == "sends" and case["runs"] == 1 and case["ask_pct"] == 100
    fake_ada.sure["orch-keep-bot"] = "fix"
    assert digest.review()[1] == {"bot": "digest", "gate": "keep_bot", "outcome": "fix", "by": "ada",
                                  "record": digest.record_of("digest")}
    assert digest.keep_of("digest") == "fix"
    with pytest.raises(BotError, match="trust or keep"):
        digest.verdict("digest", "mood", "happy")


def test_status_says_the_orchestrator_and_every_bot(digest):
    got = digest.status()
    assert got["gates"] == {"make_bot": 0, "trust_bot": 0, "keep_bot": 0} and got["memory"]["instructions"] == 1
    assert got["bots"][0]["bot"] == "digest" and got["bots"][0]["record"]["runs"] == 0
    digest.adopt("gone", "a bot whose folder went")
    assert digest.status()["bots"][1] == {"bot": "gone", "job": "a bot whose folder went", "trust": "ask_all",
                                          "keep": "keep", "missing": True}
    assert [c["bot"] for c in digest.review({})] == ["digest", "digest"]


def test_the_api_key_is_the_environments_or_the_bots_env(bots_home, monkeypatch):
    assert api_key(bots_home) is None
    bots_home.mkdir(parents=True)
    (bots_home / ".env").write_text("# kept 600\nexport GLYPHH_API_KEY='glyphh_ak_fromfile'\nOTHER=1\n")
    assert api_key() == "glyphh_ak_fromfile"
    monkeypatch.setenv("GLYPHH_API_KEY", "glyphh_ak_env")
    assert api_key(bots_home) == "glyphh_ak_env"


def test_a_slug_is_the_jobs_words_that_say_something():
    assert slug_of("Each morning, find me a Hacker News story") == "morning_find_hacker"
    assert slug_of("the 3 best") == "bot_3_best" and slug_of("!!") == "bot"


# routines


def test_cron_becomes_launchds_calendar():
    assert calendar("47 8 * * *") == [{"Minute": 47, "Hour": 8}]
    assert calendar("30 7 * * 1-5") == [{"Minute": 30, "Hour": 7, "Weekday": d} for d in range(1, 6)]
    assert len(calendar("*/15 9,17 * * *")) == 8 and calendar("* * * * *") == [{}]
    for bad in ("daily", "61 8 * * *", "* * * * * *"):
        with pytest.raises(BotError):
            calendar(bad)
    with pytest.raises(BotError, match="too often"):
        calendar("0-59 0-23 * * *")


def test_a_routine_is_a_launchd_job_on_a_mac(digest, tmp_path, monkeypatch):
    ran: List[List[str]] = []
    bot = digest.bot("digest")
    got = routines.install(bot, platform="darwin", agents=tmp_path / "agents", run=lambda argv, **kw: ran.append(argv))
    plist = Path(got["plist"]).read_text()
    assert got["installed"] and got["label"] == "ai.glyphh.bot.digest"
    assert "<string>bot</string><string>run</string><string>digest</string><string>--routine</string>" in plist
    assert "<key>Weekday</key><integer>5</integer>" in plist and f"<string>{digest.root}</string>" in plist
    assert [a[1] for a in ran] == ["bootout", "bootstrap"]
    gone = routines.install(bot, platform="darwin", agents=tmp_path / "agents", run=lambda argv, **kw: ran.append(argv),
                            remove=True)
    assert gone["removed"] and not Path(got["plist"]).exists()


def test_elsewhere_a_routine_is_the_cron_line_to_add(digest):
    bot = digest.bot("digest")
    bot.spec["routine"]["tz"] = "America/Chicago"
    got = routines.install(bot, platform="linux")
    assert not got["installed"] and got["cron_line"].startswith("30 7 * * 1-5 ") and "bot run digest --routine" in got["cron_line"]
    assert "America/Chicago" in got["note"]
    del bot.spec["routine"]
    with pytest.raises(BotError, match="no routine"):
        routines.install(bot, platform="linux")


# Claude


def test_claude_says_plainly_why_it_failed(tmp_path):
    def answering(**out: Any):
        return lambda argv, **kw: subprocess.CompletedProcess(argv, out.get("code", 0), out.get("stdout", ""), out.get("stderr", ""))

    def raising(err: Exception):
        def run(argv: List[str], **kw: Any) -> Any:
            raise err
        return run

    cases: Dict[str, Any] = {
        "is not installed": raising(FileNotFoundError()),
        "within 5 s": raising(subprocess.TimeoutExpired("claude", 5)),
        "Claude failed: exit 2": answering(code=2),
        "not JSON": answering(stdout="hello"),
        "not a JSON object": answering(stdout="[1]"),
        "Claude failed: max turns": answering(stdout=json.dumps({"is_error": True, "result": "max turns"})),
    }
    for said, run in cases.items():
        with pytest.raises(BotError, match=said):
            Claude(command="claude", run=run).agent("a", {"prompt": "p"}, "hi", seconds=5)
    ok = Claude(run=answering(stdout=json.dumps({"result": " done \n"})))
    assert ok.agent("a", {}, "hi") == "done" and ok.build("p", tmp_path) == "done"
