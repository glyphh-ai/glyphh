"""talk.py -- the group's messaging CLI on top of protocol.py (owner: courier).

    python3 shared/talk.py send  <me> <to> <act> "<content s-expr>" [--re ID] [--conf conf_hi]
    python3 shared/talk.py inbox <me> [--all] [--last N]    decode payloads addressed to me (or all)
    python3 shared/talk.py show  <ID>                       full decode of one message
    python3 shared/talk.py thread <ID>                      a conversation + what it established
    python3 shared/talk.py facts                            everything the channel established
    python3 shared/talk.py route "<content s-expr>"         who has talked about this?

Everything printed is decoded FROM THE PAYLOAD; the channel's text field is only
compared against it (column `txt`: = matches, ! differs).
In Python:  from protocol import send, inbox;  send("memory", "reasoner", "answer", "(fact :obj animal)", re=qid)
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import protocol as P  # noqa: E402
import language as L  # noqa: E402


def line(m) -> str:
    re = f" re^{m.re}" if m.re else ""
    tm = "=" if getattr(m, "text_matches", False) else "!"
    if not getattr(m, "from_matches", True):
        tm += f" SPOOF? channel says {m.raw_from}"
    if m.status in ("ok", "noisy"):
        body = f"{m.sender}->{m.to} {m.act}{re}: {L.show(m.content) if m.content is not None else ''}"
    elif m.status == "bare":
        body = f"(bare meaning from {m.raw_from}) {L.show(m.content)}"
    else:
        body = f"(from {m.raw_from}, unreadable)"
    return f"{m.id} {m.status:8s} flip={m.flip_est:.2f} txt{tm} {body}"


def main(argv=None):
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("send"); s.add_argument("me"); s.add_argument("to"); s.add_argument("act")
    s.add_argument("content"); s.add_argument("--re"); s.add_argument("--conf")
    s = sub.add_parser("inbox"); s.add_argument("me"); s.add_argument("--all", action="store_true")
    s.add_argument("--last", type=int, default=0)
    s = sub.add_parser("show"); s.add_argument("id")
    s = sub.add_parser("thread"); s.add_argument("id")
    sub.add_parser("facts")
    s = sub.add_parser("route"); s.add_argument("content")
    a = ap.parse_args(argv)

    if a.cmd == "send":
        if a.act not in P.SPEECH_ACTS:
            sys.exit(f"unknown act {a.act}; use one of {P.SPEECH_ACTS}")
        m = P.send(a.me, a.to, a.act, a.content, re=a.re, conf=a.conf)
        back = P.decode(P.wire(m), known_ids=[x for x in (m.re, m.thread) if x])
        print(f"sent {m.id}  {m.text()}")
        print(f"self-check: status={back.status} agree={back.agree:.3f} "
              f"content_roundtrip={L.show(back.content) == L.show(m.content)}")
        return
    msgs = P.inbox()
    by = {m.id: m for m in msgs}
    if a.cmd == "inbox":
        sel = [m for m in msgs if a.all or (m.to or m.raw_to) in (a.me, "all")]
        for m in sel[-a.last:] if a.last else sel:
            print(line(m))
    elif a.cmd == "show":
        m = by.get(a.id) or next((x for x in msgs if x.id.startswith(a.id)), None)
        if not m:
            sys.exit("no such id")
        print(line(m))
        print("text on channel:", m.raw_text)
        print("decoded        :", m.text() if m.status in ("ok", "noisy") else L.show(m.content))
        print(f"agree={m.agree:.3f} flip_est={m.flip_est:.3f} re_score={m.re_score:.3f}")
        for k, v in sorted(m.scores.items()):
            print(f"  {k:24s} {v:.3f}")
    elif a.cmd == "thread":
        root = by[a.id].root if a.id in by else a.id
        th = P.Thread([m for m in msgs if m.status in ("ok", "noisy") and m.root == root])
        for m in th.messages:
            print(line(m))
        tv = th.vector()
        rec = sum(th.turn(tv, i)[0] is m for i, m in enumerate(th.messages[:L.MAX_POS]))
        print(f"thread vector: {rec}/{min(len(th.messages), L.MAX_POS)} turns recovered from one vector")
        for f in th.distill():
            print("established:", L.show(f["fact"]), "src", f["src"], "endorsed", f["endorsed"],
                  "disputed", f["disputed"])
    elif a.cmd == "facts":
        for f in P.distill_all(msgs):
            print(L.show(f["fact"]), "| src", f["src"], "| endorsed", f["endorsed"],
                  "| disputed", f["disputed"], "| via", f["via"])
    elif a.cmd == "route":
        for ag, s in P.route(a.content, P.profiles(msgs)):
            print(f"{ag:10s} {s:.3f}")


if __name__ == "__main__":
    main()
