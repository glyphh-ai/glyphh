"""Replays TypeSafe's published Agent Trace answers through agent_traces.py and compares with their decisions."""

import json

import agent_traces
import published


def normalised(answer: dict):
    return answer["noul"] if answer["type"] == "noul" else answer["probabilities"]


def main() -> None:
    e = published.load("agent_trace_observability")
    same = total = 0
    for cid, c in e["cases"].items():
        nodes_ts = c["models"]["typesafe"]["nodes"]
        docs = {n["node"]: e["documents"][n["doc"]] for n in nodes_ts if n.get("doc") is not None}
        safety_docs = [d for k, d in sorted(docs.items()) if k.startswith("safety_")]
        trace = {
            "tool_calls": [{"step": int(d["the_action"]["step"]), "tool": d["the_action"]["tool"]} for d in safety_docs],
            "tools": {
                d["the_action"]["tool"]: {
                    "destructive": d["tool"]["destructive"] == "True",
                    "read_only": d["tool"]["read_only"] == "True",
                    "requires_explicit_confirmation": d["permission_for_this_action"]["requires_explicit_confirmation"] == "True",
                    "requires_supervisor_approval": d["permission_for_this_action"]["requires_supervisor_approval"] == "True",
                    "entitlement": d["permission_for_this_action"]["entitlement"],
                }
                for d in safety_docs
            },
            "feedback": docs.get("reaction", {}).get("feedback", {"signal": "none"}),
        }
        runs = {}
        for name, m in c["models"].items():
            by_node = {n["node"]: {q: normalised(v) for q, v in n.get("answers", {}).items()} for n in m["nodes"]}
            runs[name] = (by_node, m["decisions"]["balanced"]["actions"][0][0])

        for name, (by_node, theirs) in runs.items():
            safety_iter = iter(sorted(k for k in by_node if k.startswith("safety_")))

            def ask(node, qs, step=None, by_node=by_node, safety_iter=safety_iter):
                key = next(safety_iter) if node == "safety" else node
                return {q: by_node[key][q] for q in qs}

            try:
                ours, _ = agent_traces.decide(ask, trace)
            except (KeyError, StopIteration) as err:
                ours = f"(needs {err})"
            same += ours == theirs
            total += 1
            print(f"{cid[:24]:24s} {name:9s} ours {ours:28s} theirs {theirs}")
        ref = c["references"][-1]
        print(f"{'':24s} reference: {ref['title'][:40]} -> {ref['decisions']['balanced'][0][0]}")
    print(f"{same} of {total} model decisions match TypeSafe's")


if __name__ == "__main__":
    main()
