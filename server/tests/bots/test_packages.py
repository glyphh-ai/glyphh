"""Bot templates as Claude plugin packages (docs/specs/bot-agent-loop.md, 7): the eight Glyphh ships load and say what
a template must, their decisions are the old templates' gates unchanged, and the validator refuses each thing wrong
with a package, all of them at once."""

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

from glyphh_server.errors import Invalid
from glyphh_server.ops.bots import packages

# each template's decisions, {name: (outcomes, digest)}: the digest is of the old template's gate as it was in
# library/<slug>.json (the weekly report's case reading `$item.x` where it read the loop's `$report.x`)
DECISIONS: dict[str, dict[str, tuple[list[str], str]]] = {
    "inbox-triage": {"worth": (["read", "skip"], "6fd7084d2a886f83")},
    "lead-scoring": {"score": (["hot", "warm", "cold"], "2a247982357f08a0")},
    "meeting-prep": {"prep": (["prep", "skip"], "7f031d9ab9875ee9")},
    "news-brief": {"read": (["read", "skip"], "3f13623876f70bf4")},
    "pr-review-digest": {"today": (["today", "later"], "b3d521fb2913501a")},
    "resume-screener": {
        "source": (["real", "spam"], "470fd57bb987e2f1"),
        "fit": (["strong", "borderline", "poor"], "e07a6f582b0ab99e"),
        "made": (["some", "mostly", "fully"], "629ea269231b37b0"),
    },
    "support-triage": {"urgency": (["urgent", "normal", "spam"], "3c4e0a26f65de725")},
    "weekly-report": {"ready": (["file", "hold"], "52147a4abeb040e1")},
}
SLUGS: list[str] = sorted(DECISIONS)
SKILL: str = "---\nname: digest\ndescription: How a digest is written. Use it to write one.\n---\n\nOne line each.\n"


def digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()[:16]


def sidecar(**changed: Any) -> dict[str, Any]:
    bot = {"name": "Digest", "tagline": "Writes a digest", "description": "It writes a digest.", "instructions": "Do.",
           "model": "claude-sonnet-5-5"}  # fmt: skip
    return {"bot": bot, "task": "Write the digest.", **changed}


def files(side: dict[str, Any] | None = None, **more: str | bytes) -> dict[str, str | bytes]:
    """A small package that fits, with this sidecar and these files added or replaced."""
    manifest = {"name": "digest-bot", "version": "1.2.3", "description": "A digest bot."}
    return {
        packages.MANIFEST: json.dumps(manifest), "skills/digest/SKILL.md": SKILL,
        packages.SIDECAR: json.dumps(side or sidecar()), **more,
    }  # fmt: skip


def refused(given: dict[str, str | bytes]) -> list[str]:
    with pytest.raises(Invalid) as e:
        packages.check(given)
    found: list[str] = e.value.detail["problems"]
    assert (
        e.value.detail["reason"] == "package" and e.value.message == f"The package does not fit: {len(found)} to fix."
    )
    return found


# the eight packages


def test_the_library_is_the_eight_packages_each_named_as_its_folder() -> None:
    lib = packages.library()
    assert sorted(lib) == SLUGS and packages.library() is lib
    for slug, p in lib.items():
        assert (packages.LIBRARY / slug / packages.MANIFEST).is_file() and p.version == "1.0.0" and p.description
        program = {"program.py"} if slug == "pr-review-digest" else set()  # a template with a program
        assert set(p.files) == {
            packages.MANIFEST,
            packages.SIDECAR,
            *program,
            *(f"skills/{s}/SKILL.md" for s in p.skills),
        }
        assert packages.check(p.files) == p  # what a bot keeps of it is a package too


@pytest.mark.parametrize("slug", SLUGS)
def test_a_package_says_what_a_template_must(slug: str) -> None:
    p = packages.library()[slug]
    s = p.sidecar
    assert p.slug == slug and p.runs_on == ["cloud", "rrotor"] == s.runs_on and not s.code and not s.folders
    assert s.bot.name and s.bot.tagline and s.bot.description and s.bot.look and s.bot.model.startswith("claude-")
    assert s.bot.effort == "medium" and s.task.endswith(".") and len(s.task) < 200
    assert 3 <= len(s.examples) <= 4 and all(0 < len(e) < 60 for e in s.examples)
    assert p.skills and all(f"the {name} skill" in s.bot.instructions for name in p.skills)
    words = s.bot.instructions
    assert (
        words.startswith(f"You are {s.bot.name}. Your job:")
        and "$" not in words
        and "decide with the decision" in words
    )
    assert "only greets you or asks what you can do, answer in a sentence or two and use no tool" in words
    assert "outside this job, say plainly" in words
    for r in s.requires:  # the agent's tool is the key with - as _
        assert all(key.replace("-", "_") in words for key in r.tools)
    assert all(f"`{name}`" in words for name in s.decisions)


@pytest.mark.parametrize("slug", SLUGS)
def test_a_packages_decisions_are_the_old_templates_gates(slug: str) -> None:
    decisions = packages.library()[slug].sidecar.decisions
    assert list(decisions) == list(DECISIONS[slug])
    for name, (outcomes, was) in DECISIONS[slug].items():
        d = decisions[name]
        assert d["outcomes"] == outcomes and d["spec"]["name"] == name and digest(d) == was
        assert "$item." in json.dumps(d["case"]) and "$report" not in json.dumps(d["case"])


def test_the_policies_and_seeds_the_gates_had_are_kept() -> None:
    lib = packages.library()
    kept = {s: {n: {k: v for k, v in d.items() if k not in ("case", "spec", "outcomes", "question")}
                for n, d in lib[s].sidecar.decisions.items()} for s in SLUGS}  # fmt: skip
    seeded = {"ask_below": 0.7, "seed_from": "resume-screener"}
    assert kept == {
        "inbox-triage": {"worth": {}},
        "lead-scoring": {"score": {"ask_below": 0.8, "default": "warm"}},
        "meeting-prep": {"prep": {"default": "skip"}},
        "news-brief": {"read": {"max_questions": 10, "default": "skip"}},
        "pr-review-digest": {"today": {"default": "later"}},
        "resume-screener": {
            "source": seeded, "fit": seeded, "made": {"ask_below": 0.55, "seed_from": "resume-screener", "probe": True},
        },
        "support-triage": {"urgency": {"ask_below": 0.75, "default": "normal"}},
        "weekly-report": {"ready": {"ask_below": 0.85, "min_precedents": 4, "default": "hold"}},
    }  # fmt: skip
    assert lib["weekly-report"].sidecar.decisions["ready"]["case"] == {
        "r": {"s": {"title": "$item.title", "highlights": "$item.highlights"}}
    }
    assert (packages.LIBRARY / "seeds" / "resume-screener.json").is_file()


def test_what_each_package_requires() -> None:
    lib = packages.library()
    assert {s: {r.app: r.tools for r in lib[s].sidecar.requires} for s in SLUGS} == {
        "inbox-triage": {"gmail": ["gmail-find-email", "gmail-send-email"]},
        "lead-scoring": {"google_sheets": ["google_sheets-add-multiple-rows"]},
        "meeting-prep": {"google_calendar": ["google_calendar-list-events"], "notion": ["notion-create-page"]},
        "news-brief": {},
        "pr-review-digest": {"github": ["github-search-issues-and-pull-requests"], "slack": ["slack-send-message"]},
        "resume-screener": {"gmail": []},
        "support-triage": {"gmail": ["gmail-find-email"], "slack": ["slack-send-message"]},
        "weekly-report": {"github": ["github-search-issues-and-pull-requests"], "notion": ["notion-create-page"]},
    }
    assert {s: lib[s].sidecar.hosts for s in SLUGS if lib[s].sidecar.hosts} == {"news-brief": ["hn.algolia.com"]}
    assert {s: lib[s].sidecar.schedule for s in SLUGS if lib[s].sidecar.schedule} == {
        "resume-screener": {"every": "hour"}
    }
    assert {s: lib[s].sidecar.limits for s in SLUGS} == {
        "inbox-triage": {}, "lead-scoring": {"seconds": 300}, "meeting-prep": {"seconds": 300, "runs_per_day": 2},
        "news-brief": {"seconds": 180, "runs_per_day": 3}, "pr-review-digest": {"seconds": 300, "runs_per_day": 4},
        "resume-screener": {"seconds": 600}, "support-triage": {"seconds": 300, "runs_per_day": 24},
        "weekly-report": {"seconds": 600, "runs_per_day": 1},
    }  # fmt: skip
    assert lib["news-brief"].sidecar.bot.model == "claude-haiku-5-5"
    assert lib["weekly-report"].sidecar.bot.model == "claude-opus-5-5"


def test_the_resume_screener_keeps_its_connector_tools_and_built_ins() -> None:
    lib = packages.library()
    s = lib["resume-screener"].sidecar
    was = json.loads((Path(__file__).with_name("old_library") / "resume-screener.json").read_text("utf-8"))
    assert digest(was["connector_tools"]) == "8fe7cc20816bcc07"  # the old template's tools, as they were
    kept = [{**t, "verdicts": "fit"} if "verdicts" in t else t for t in was["connector_tools"]]
    assert s.builtins == ["inbox_applications", "inbox_label"]
    assert s.connector_tools == kept  # each as it was, its verdicts now the `fit` decision's (the step is gone)
    assert [t["name"] for t in s.connector_tools] == [
        "screen_application", "screen_inbox", "applicants", "correct", "correct_generated", "correct_source",
        "screener_answer",
    ]  # fmt: skip
    assert all(
        not lib[slug].sidecar.builtins and not lib[slug].sidecar.connector_tools for slug in SLUGS[:5] + SLUGS[6:]
    )
    words = s.bot.instructions
    assert "inbox_applications" in words and "inbox_label" in words and "screening-report" in words
    assert "probe_generated" not in words and "screen_verdicts" not in words  # no longer tools
    assert "`spam` when its source is `spam`; otherwise its fit, `strong`, `borderline` or `poor`; `waiting`" in words
    assert "or `human` when no generated application close to it is known" in words
    assert "{subject:(application applying resume cv role position) has:attachment}" in words


def test_the_pr_review_digest_searches_for_review_requests_never_for_what_the_person_typed() -> None:
    words = packages.library()["pr-review-digest"].sidecar.bot.instructions
    assert "github_search_issues_and_pull_requests with the query `is:pr is:open review-requested:@me`" in words
    assert "Never search GitHub with the person's words" in words
    assert "slack_send_message" in words and "the digest skill" in words


# the validator


def test_a_package_that_fits_is_read_from_text_or_bytes() -> None:
    p = packages.check(files(**{"skills/digest/notes.md": b"More."}))
    assert (p.slug, p.version, p.description, p.skills) == ("digest-bot", "1.2.3", "A digest bot.", ["digest"])
    assert p.runs_on == ["cloud", "rrotor"] and p.sidecar.runs_on is None and p.sidecar.bot.effort == "medium"
    assert p.files["skills/digest/notes.md"] == "More." and json.loads(p.files[packages.SIDECAR])["task"]
    bare = packages.check(
        {packages.MANIFEST: '{"name": "a", "version": "0.0.1"}', packages.SIDECAR: json.dumps(sidecar())}
    )
    assert (bare.slug, bare.description, bare.skills) == ("a", "", [])


def test_a_path_outside_the_package_is_refused() -> None:
    assert refused(files(**{"/etc/passwd": "x", "skills/../../up.md": "x", "\\win": "x"})) == [
        "/etc/passwd is not a path inside the package: no leading / and no '..'.",
        "skills/../../up.md is not a path inside the package: no leading / and no '..'.",
        "\\win is not a path inside the package: no leading / and no '..'.",
    ]


def test_a_file_that_is_not_text_and_a_package_too_large_are_refused() -> None:
    assert refused(files(**{"skills/digest/logo.png": b"\x89PNG\xff\xfe"})) == [
        "skills/digest/logo.png is not UTF-8 text: a package holds text files only."
    ]
    assert refused(files(**{"skills/digest/big.md": "x" * packages.MAX_BYTES}))[0].endswith("the most is 1,000,000.")


def test_a_missing_or_broken_manifest_is_refused() -> None:
    given = files()
    del given[packages.MANIFEST]
    assert refused(given) == [".claude-plugin/plugin.json is missing."]
    assert refused(files(**{packages.MANIFEST: "{not json"})) == [".claude-plugin/plugin.json is not a JSON object."]
    assert refused(files(**{packages.MANIFEST: "[1]"})) == [".claude-plugin/plugin.json is not a JSON object."]


@pytest.mark.parametrize("name", [None, 7, "Digest", "9lives", "a" * 32, "with space"])
def test_a_manifest_without_a_good_name_is_refused(name: Any) -> None:
    assert refused(files(**{packages.MANIFEST: json.dumps({"name": name, "version": "1.0.0"})})) == [
        ".claude-plugin/plugin.json needs a name: a lowercase letter, then up to 30 lowercase letters, digits or -."
    ]


@pytest.mark.parametrize("version", [None, 1, "1.0", "v1.0.0", "1.0.0-beta"])
def test_a_manifest_without_a_good_version_is_refused(version: Any) -> None:
    assert refused(files(**{packages.MANIFEST: json.dumps({"name": "digest-bot", "version": version})})) == [
        ".claude-plugin/plugin.json needs a version of three numbers, like 1.0.0."
    ]


def test_a_skill_folder_without_its_skill_md_is_refused() -> None:
    assert refused(files(**{"skills/extra/scripts/x.py": "print(1)"})) == ["The skill extra has no SKILL.md."]


@pytest.mark.parametrize(
    "text",
    ["No frontmatter at all.", "---\nname: digest\n---\nBody.", "---\ndescription: How.\n---\nBody.",
     "---\nname:\ndescription: How.\n---\n"],
)  # fmt: skip
def test_a_skill_without_name_and_description_frontmatter_is_refused(text: str) -> None:
    assert refused(files(**{"skills/digest/SKILL.md": text})) == [
        "skills/digest/SKILL.md needs a name and a description in its frontmatter."
    ]


def test_a_skill_named_differently_from_its_folder_is_refused() -> None:
    assert refused(files(**{"skills/other/SKILL.md": SKILL})) == [
        "skills/other/SKILL.md names itself digest: a skill is named as its folder, other."
    ]


def test_a_missing_or_broken_sidecar_is_refused() -> None:
    given = files()
    del given[packages.SIDECAR]
    assert refused(given) == ["glyphh.json is missing."]
    assert refused(files(**{packages.SIDECAR: "nope"})) == ["glyphh.json is not a JSON object."]


def test_a_sidecar_with_unknown_keys_or_wrong_values_is_refused_naming_each() -> None:
    side = sidecar(loop=[], limits={"turns": 0, "steps": 3}, requires=[{"app": "slack", "scope": "all"}])
    side["bot"]["effort"] = "huge"
    del side["task"]
    found = refused(files(side))
    assert "glyphh.json has an unknown key: loop." in found
    assert "glyphh.json has an unknown key: requires.0.scope." in found
    assert "glyphh.json, task: Field required." in found
    assert "glyphh.json, limits.turns: Input should be greater than 0." in found
    assert "glyphh.json, limits.steps.[key]: Input should be 'turns', 'seconds', 'tokens' or 'runs_per_day'." in found
    assert any(p.startswith("glyphh.json, bot.effort: Input should be 'low'") for p in found) and len(found) == 6


def test_a_required_tool_that_is_not_its_apps_is_refused() -> None:
    side = sidecar(requires=[{"app": "slack", "tools": ["slack-send-message", "github-create-issue", "slackbot-x"]}])
    assert refused(files(side)) == [
        "The tool github-create-issue is not one of slack's: its key starts with slack-.",
        "The tool slackbot-x is not one of slack's: its key starts with slack-.",
    ]


def test_a_decision_without_outcomes_or_a_case_is_refused() -> None:
    case = {"m": {"s": {"subject": "$item.subject"}}}
    side = sidecar(decisions={
        "good": {"outcomes": ["read", "skip"], "case": case}, "one": {"outcomes": ["read"], "case": case},
        "none": {"case": case}, "blind": {"outcomes": ["a", "b"]}, "empty": {"outcomes": "ab", "case": {}},
    })  # fmt: skip
    assert refused(files(side)) == [
        "The decision one needs at least two outcomes.",
        "The decision none needs at least two outcomes.",
        "The decision blind needs a case: how an item becomes what Ada reads.",
        "The decision empty needs at least two outcomes.",
        "The decision empty needs a case: how an item becomes what Ada reads.",
    ]


def test_too_many_examples_and_one_too_long_are_refused() -> None:
    assert packages.check(files(sidecar(examples=["x" * 200] * 6))).sidecar.examples
    assert refused(files(sidecar(examples=["Hi"] * 7))) == [
        "glyphh.json, examples: List should have at most 6 items after validation, not 7."
    ]
    assert refused(files(sidecar(examples=["Hi", "x" * 201]))) == [
        "glyphh.json, examples.1: String should have at most 200 characters."
    ]


def test_code_naming_a_skill_or_a_script_that_is_not_there_is_refused() -> None:
    code = [{"skill": "digest", "scripts": ["skills/digest/scripts/a.py", "skills/digest/scripts/b.py"], "why": "x"},
            {"skill": "ghost", "scripts": [], "why": "x"}]  # fmt: skip
    assert refused(files(sidecar(code=code), **{"skills/digest/scripts/a.py": "print(1)"})) == [
        "The code names the script skills/digest/scripts/b.py, which is not in the package.",
        "The code names the skill ghost, which is not in the package.",
    ]


def test_where_a_package_runs_follows_from_its_code_and_folders() -> None:
    script = {"skills/digest/scripts/a.py": "print(1)"}
    code = [{"skill": "digest", "scripts": ["skills/digest/scripts/a.py"], "why": "It reads PDFs."}]
    assert packages.check(files(sidecar(code=code), **script)).runs_on == ["rrotor"]
    assert packages.check(files(sidecar(folders=True, runs_on=["rrotor"]))).runs_on == ["rrotor"]
    assert packages.check(files(sidecar(runs_on=["cloud", "rrotor"]))).runs_on == ["cloud", "rrotor"]
    why = "code and folders need a rrotor, anything else runs anywhere."
    assert refused(files(sidecar(code=code, runs_on=["cloud", "rrotor"]), **script)) == [
        f'runs_on must be ["rrotor"]: {why}'
    ]
    assert refused(files(sidecar(folders=True, runs_on=["cloud"]))) == [f'runs_on must be ["rrotor"]: {why}']
    assert refused(files(sidecar(runs_on=["rrotor"]))) == [f'runs_on must be ["cloud", "rrotor"]: {why}']


def test_every_problem_is_said_at_once() -> None:
    side = sidecar(requires=[{"app": "slack", "tools": ["gmail-find-email"]}], runs_on=["rrotor"])
    given = files(side, **{packages.MANIFEST: "{}", "skills/other/SKILL.md": SKILL, "/abs": "x"})
    found = refused(given)
    assert len(found) == 6 and found[0].startswith("/abs is not a path") and found[-1].startswith("runs_on must be")


def test_a_folder_is_read_whole_but_for_what_a_machine_leaves_in_it(tmp_path: Path) -> None:
    for path, body in files().items():
        (tmp_path / path).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / path).write_text(str(body))
    (tmp_path / ".DS_Store").write_bytes(b"\x00\xff")
    (tmp_path / "skills" / "__pycache__").mkdir()
    (tmp_path / "skills" / "__pycache__" / "x.pyc").write_bytes(b"\xff")
    found = packages.read(tmp_path)
    assert sorted(found) == [packages.MANIFEST, packages.SIDECAR, "skills/digest/SKILL.md"]
    assert packages.check(found).slug == "digest-bot"
