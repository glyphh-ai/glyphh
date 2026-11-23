"""Ada, as a bot's tools (docs/specs/bot-agent-loop.md, 4): a bot uses Ada however its instructions say. `decide`
answers how the person decided items like these before; `ask_person` about a decision's items asks the person and
teaches that decision's Ada model their answers. Each function here is one go of the SDK's runner on the bot's state
(ops/bots/goes.py: a worker thread), using the SDK's own policy and store, so what Ada answered and what the person
said is kept in the runner's decisions (copied to bot_decisions, ops/bots/decided.py), which is what the Decisions
panel, a correction and training read. The runner's store names a decision a `gate`: a storage name, nothing more.

An entry is one item of one call: `n`, `key`, `label`, `item`, `case`, then how it stands: `by` (ada: sure by the
decision's own bar; unsure; person; probe: no precedent as close as the decision's reference, so it is none of its
outcomes) and `outcome` (for an unsure item, Ada's best guess, or None with nothing to go on)."""

import json
from datetime import date
from typing import Any

from glyphh.bots import Policy
from glyphh.bots.runner import _item_key, fill, held, new_run_id

from glyphh_server.ops.bots import probe, readable

ITEMS_MAX: int = 200
NOT_ONE: str = "human"  # what a probed decision says of an item unlike every precedent it holds
BY: dict[str, str] = {"person": "you", "ada": "ada", "unsure": "ada", "probe": "ada"}
KEPT: frozenset[str] = frozenset(("ada", "person"))  # neither an unsure answer nor a probed one is kept


def key(item: dict[str, Any]) -> str:
    return _item_key({}, item)


def label(item: dict[str, Any]) -> str:
    """An item as the person reads it: its own `label` when it carries one, else a title drawn from its fields,
    never JSON (ops/bots/readable.py)."""
    own = item.get("label")
    return readable.label(own if isinstance(own, str) else None, readable.fields(item))


def _floor(runner: Any, name: str, decision: dict[str, Any]) -> float | None:
    kept = runner.store.state(probe.KEY + name) if decision.get("probe") else None
    reference = json.loads(kept) if kept else {}
    return reference.get(probe.FLOOR)


def judged(runner: Any, run: str, name: str, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Each item's entry: Ada's answer, sure or not by the decision's own bar (`ask_below`, `min_precedents`)."""
    decision = runner.bot.gates[name]
    policy, model_name = Policy.of(name, decision), runner.bot.gate_model(name)
    n, model, floor = held(runner.ada, model_name), runner.ada.model(model_name), _floor(runner, name, decision)
    entries = []
    for i, item in enumerate(items, 1):
        k, case = key(item), fill(decision["case"], {"item": item})
        e = {"n": i, "key": k, "label": label(item), "item": item, "case": case, "outcome": None,
             "by": "unsure", "p": None, "guess": None, "mode": "", "why": "", "agreed": None}  # fmt: skip
        near = probe.nearest(model, case) if floor is not None and n else None
        if floor is not None and (near is None or near < floor):
            entries.append(e | {"outcome": NOT_ONE, "by": "probe", "mode": "probe"})
            continue
        call = policy.judge(model.decide(case) if n else None, n, f"{run}:{name}:{k}")
        e |= {"p": call.p, "guess": call.outcome, "mode": call.mode, "why": call.why, "outcome": call.outcome}
        entries.append(e | ({} if call.ask else {"by": "ada"}))
    return entries


def question(name: str, decision: dict[str, Any], entries: list[dict[str, Any]], said: str) -> dict[str, Any]:
    """What the run asks the person about a decision's items, as a batch (`N=outcome`, `rest=outcome`)."""
    outcomes = list(decision["outcomes"])
    said = said.strip() or str(decision.get("question") or f"What is the {name.replace('_', ' ')}?")
    batch = [{"n": e["n"], "label": e["label"], "guess": e["guess"], "p": e["p"], "why": e["why"]} for e in entries]
    example = " ".join(f"{e['n']}={outcomes[i % len(outcomes)]}" for i, e in enumerate(entries[:2]))
    answer_with = f"{example} rest={outcomes[-1]}" if len(entries) > 2 else example
    return {"question": said, "options": outcomes, "batch": batch, "answer_with": answer_with, "step": name,
            "approval": False, "decision": name}  # fmt: skip


def answered(runner: Any, name: str, entries: list[dict[str, Any]], answers: dict[int, str]) -> list[dict[str, Any]]:
    """The person's answers taken: each recorded as a precedent of the decision (unless the world answers it)."""
    policy, model = Policy.of(name, runner.bot.gates[name]), runner.ada.model(runner.bot.gate_model(name))
    for e in entries:
        got = answers[e["n"]]
        e |= {"outcome": got, "by": "person", "agreed": None if e["guess"] is None else e["guess"] == got}
        if not policy.world:
            model.record(e["case"], got)
    return entries


def kept(runner: Any, run: str, name: str, entries: list[dict[str, Any]]) -> str:
    """The call's decisions kept in the runner's store, and the run's row there with them (each decision under its
    name, and the items by outcome under the call's step): what the decisions' sync and a correction read. Answers
    the run's id there (made when the run had none)."""
    run = run or new_run_id()
    world = Policy.of(name, runner.bot.gates[name]).world
    had = runner.store.get(run) or {"data": {}, "log": []}
    data = had["data"]
    step = f"{name}-{sum(1 for k in data if k.startswith(name + '-')) + 1}"
    made = [e for e in entries if e["by"] in KEPT]
    for e in made:
        runner.store.keep_decision(
            run=run, gate=name, step=step, n=e["n"], key=e["key"], label=e["label"], kind="each", case=e["case"],
            outcome=e["outcome"], by=e["by"], p=e["p"], guess=e["guess"], mode=e["mode"], agreed=e["agreed"],
            recorded=e["by"] == "person" and not world, day=date.today().isoformat(),
        )  # fmt: skip
    outcomes = {str(e["outcome"]) for e in made}
    data[step] = {o: [e["item"] for e in made if e["outcome"] == o] for o in sorted(outcomes)}
    asked = sum(1 for e in made if e["by"] == "person")
    data.setdefault("_gates", {})[name] = {"each": True, "by": "person" if asked else "ada", "asked": asked}
    runner.store.save(run, "done", 0, data, {}, "", had["log"], date.today().isoformat())
    return run


def results(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """What `decide` answers the agent: per item its outcome, who said it, how sure, and whether Ada is sure."""
    return [
        {"id": e["key"], "item": e["label"], "outcome": e["outcome"], "by": BY[e["by"]],
         "confidence": 1.0 if e["by"] == "person" else e["p"], "sure": e["by"] != "unsure"}
        for e in entries
    ]  # fmt: skip
