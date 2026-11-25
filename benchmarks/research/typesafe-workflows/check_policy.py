"""Replays TypeSafe's published example answers through security.py and compares with their published decisions."""

import published
import security


def normalised(answer: dict) -> float | dict[str, float]:
    return answer["noul"] if answer["type"] == "noul" else answer["probabilities"]


def consensus(reference_answers: dict) -> dict:
    out = {}
    for node in reference_answers.values():
        for q, v in node.items():
            sets = [s["probabilities"] for s in v["sets"]]
            if v["type"] == "noul":
                out[q] = sum(s["true"] for s in sets) / len(sets)
            else:
                out[q] = {k: sum(s[k] for s in sets) / len(sets) for k in sets[0]}
    return out


def main() -> None:
    e = published.load("security_incidents")
    same = total = 0
    for (cid, c), doc in zip(e["cases"].items(), e["documents"], strict=True):
        state = c["models"]["typesafe"]["decisions"]["playbook"]["outputs"]["state"]
        case = {
            **state,
            "domain_controller": doc["context"]["asset"]["type"] == "Domain Controller",
        }
        runs = {}
        for name, m in c["models"].items():
            a = {q: normalised(v) for n in m["nodes"] for q, v in n["answers"].items()}
            runs[name] = (a, m["decisions"]["playbook"]["actions"][0][0])
        runs["consensus"] = (
            consensus(c["reference_answers"]),
            c["references"][-1]["decisions"]["playbook"][0][0],
        )
        for name, (a, theirs) in runs.items():
            ours, _ = security.decide(lambda qs, a=a: {q: a[q] for q in qs}, case)
            same += ours == theirs
            total += 1
            print(f"{cid[:38]:38s} {name:9s} ours {ours:20s} theirs {theirs}")
    print(f"{same} of {total} decisions match TypeSafe's")


if __name__ == "__main__":
    main()
