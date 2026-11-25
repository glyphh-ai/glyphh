"""A model's versions as a page of versions reads them: what changed against the version before, the precedents when
each was made, what each had learned, its newest backtest scores, its store and from when it may be dropped; one
version whole, a comparison of two, and a version's note written again."""

from datetime import datetime, timedelta

import httpx
import psycopg
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_ada import history, pg
from glyphh_ada.process import Worker
from tests.ada.conftest import SHAPES, a_model, an_org, finished
from tests.conftest import DATABASE_URL

URL = "/v1/models/shapes/versions"


def _sql(org: str, text: str) -> list[tuple]:
    with psycopg.connect(pg.libpq_url(DATABASE_URL), autocommit=True) as conn:
        pg.enter(conn, org)
        found = conn.execute(text.replace("{s}", f'"{pg.schema_for(org)}"'))
        return found.fetchall() if found.description else []


async def test_each_version_says_what_changed_what_it_learned_and_its_store(
    engine: AsyncEngine, ada: httpx.AsyncClient, worker: Worker, jobs_worker: Worker
) -> None:
    who, key = await an_org(engine, ada)
    org = str(who.org_id)
    await a_model(ada, key, n=60)
    await finished(ada, key, (await ada.post("/v1/models/shapes/learn", headers=key)).json())
    more = await ada.patch("/v1/models/shapes/settings", json={"changes": {"k": 20}, "note": "more"}, headers=key)
    assert more.json()["active"], more.text
    body = {"candidates": [{"spec_version": 1}, {"settings": {"k": 5}}], "holdout": {"newest": 20}}
    tested = await finished(ada, key, (await ada.post("/v1/models/shapes/backtest", json=body, headers=key)).json())
    assert tested["state"] == "done", tested
    seeded = {**SHAPES, "seed": 11, "settings": {"k": 20}}
    moved = await ada.put("/v1/models/shapes/spec", json={"spec": seeded}, headers=key)
    assert (await finished(ada, key, moved.json()["job"]))["state"] == "done"

    one, two, three = (await ada.get(URL, headers=key)).json()["versions"]
    assert (one["changes"], one["precedents_at"], one["new_store"]) == (None, 0, False)
    assert two["changes"] == [{"path": "settings.k", "from": 15, "to": 20, "restates": False}]
    assert (two["precedents_at"], two["note"], two["new_store"]) == (60, "more", False)
    assert three["changes"] == [{"path": "seed", "from": 5, "to": 11, "restates": True}]
    assert three["new_store"] and three["reencoded"] and three["active"]
    assert set(one["learned"]["default"]) >= {"roles", "words", "pairs", "tau"}
    assert three["learned"]["default"]["roles"]
    assert two["scores"]["job"] == tested["id"] and 0 <= two["scores"]["accuracy"] <= 1
    assert one["scores"]["job"] == tested["id"] and "mistakes" not in one["scores"]
    assert three["scores"] is None
    assert three["store"] == {"status": "active", "drop_after": None}
    assert one["store"]["status"] == two["store"]["status"] == "kept"
    retired = datetime.fromisoformat(str(two["retired_at"]))
    assert datetime.fromisoformat(str(one["store"]["drop_after"])) == retired + timedelta(days=7)

    whole = (await ada.get(f"{URL}/1", headers=key)).json()
    assert whole["spec"] == SHAPES and whole["settings"]["k"] == 15 and whole["version"] == 1
    live = (await ada.get(f"{URL}/1/diff", headers=key)).json()
    assert live["against"] == 3
    assert [(c["path"], c["from"], c["to"], c["restates"]) for c in live["changes"]] == [
        ("seed", 11, 5, True),
        ("settings.k", 20, 15, False),
    ]
    against = (await ada.get(f"{URL}/3/diff?against=2", headers=key)).json()
    assert [c["path"] for c in against["changes"]] == ["seed"]
    assert (await ada.get(f"{URL}/9", headers=key)).status_code == 404
    assert (await ada.get(f"{URL}/9/diff", headers=key)).status_code == 404

    noted = await ada.patch(f"{URL}/2", json={"note": "k up for recall"}, headers=key)
    assert noted.json() == {"version": 2, "note": "k up for recall"}, noted.text
    assert (await ada.get(URL, headers=key)).json()["versions"][1]["note"] == "k up for recall"
    assert (await ada.patch(f"{URL}/9", json={"note": "x"}, headers=key)).status_code == 404
    assert (await ada.patch(f"{URL}/2", json={"note": "x" * 501}, headers=key)).status_code == 422

    _sql(org, "UPDATE {s}.spec_versions SET gone = true WHERE version = 1")
    assert (await ada.get(URL, headers=key)).json()["versions"][0]["store"]["status"] == "dropped"


ROLE = {"name": "color"}


def _spec(**changes: object) -> dict:
    roles = [ROLE, {"name": "shape"}]
    return {"name": "m", "layers": [{"name": "a", "segments": [{"name": "s", "roles": roles}]}], **changes}


def test_a_diff_matches_named_things_by_name_and_says_which_changes_rewrite_the_cases() -> None:
    added = _spec()
    added["layers"][0]["segments"][0]["roles"] = [ROLE, {"name": "shape"}, {"name": "size"}]
    assert [(c["path"], c["restates"]) for c in history.diff(_spec(), added)] == [
        ("layers[a].segments[s].roles[size]", True)
    ]
    weighed = _spec()
    weighed["layers"][0]["segments"][0]["roles"] = [{"name": "color", "similarity_weight": 0.5}, {"name": "shape"}]
    assert [(c["path"], c["from"], c["to"], c["restates"]) for c in history.diff(_spec(), weighed)] == [
        ("layers[a].segments[s].roles[color].similarity_weight", 1.0, 0.5, False)
    ]
    named = {"lexicons": ["colour"], "value_weights": {"r": 0.5}}
    words = _spec()
    words["layers"][0]["segments"][0]["roles"] = [{"name": "color", **named}, {"name": "shape"}]
    assert {c["path"]: c["restates"] for c in history.diff(_spec(), words)} == {
        "layers[a].segments[s].roles[color].lexicons": False,
        "layers[a].segments[s].roles[color].value_weights": True,
    }
    pairs = _spec(interactions=[{"name": "cs", "roles": ["a.s.color", "a.s.shape"]}])
    costs = _spec(outputs={"risk": {"values": ["hi", "lo"]}}, settings={"lexicon": False})
    assert {c["path"]: c["restates"] for c in history.diff(_spec(), pairs)} == {"interactions[cs]": True}
    assert {c["path"]: c["restates"] for c in history.diff(_spec(), costs)} == {
        "outputs": False,
        "settings.lexicon": True,
    }
    assert history.diff(_spec(), _spec()) == []


def test_what_was_learned_the_scores_and_the_store_in_short() -> None:
    assert history.learned(None) is None and history.learned({}) is None
    table = {"a.s.color": {"similarity_weight": 0.7}, "~interactions": [{"roles": ["x", "y"]}]}
    kept = {"learned": table, "learned:risk": None, "tau": 0.81234, "tau:risk": "1.5"}
    assert history.learned(kept) == {
        "default": {"roles": {"a.s.color": 0.7}, "words": {}, "pairs": [["x", "y"]], "tau": 0.8123},
        "risk": {"tau": 1.5},
    }
    failed = {"version": 4, "output": "default", "active": {"error": {"code": "E_SPEC"}}, "candidates": []}
    candidate = {"candidate": {"spec_version": 4}, "accuracy": 0.9, "mistakes": {}}
    found = {"version": 5, "output": "risk", "active": {"accuracy": 0.8}, "candidates": [candidate]}
    tests = [("j1", "t1", failed), ("j2", "t2", found)]
    assert history.scores(tests, 4) == {"job": "j2", "at": "t2", "output": "risk", "accuracy": 0.9}
    assert history.scores(tests, 6) is None
    row = {"store": "b", "gone": False, "ready": False}
    assert history.store(row, "a", {}) == {"status": "making", "drop_after": None}
    assert history.store({**row, "ready": True}, "a", {}) == {"status": "kept", "drop_after": None}
