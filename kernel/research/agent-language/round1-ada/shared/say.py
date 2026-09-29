#!/usr/bin/env python3
"""say.py — the CLI for glyph messages on the channel (owner: courier).

  python3 shared/say.py send FROM TO ACT 'CONTENT' [--reply TS] [--text T] [--extra '{"claim_id":"c-1"}']
      CONTENT is JSON (a frame/list/word) or a bare word.
  python3 shared/say.py inbox ME [--since TS]   # decoded from the glyph only
  python3 shared/say.py read [--since TS]        # decode every glyph on the channel
  python3 shared/say.py threads                  # conversations rebuilt from glyph reply links
  python3 shared/say.py audit                    # decoded fields vs the sender's receipt

Acts: tell ask answer propose agree disagree ack correct done.
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import protocol as P  # noqa: E402
from language import render  # noqa: E402


def _content(s: str):
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        return s


def _line(l, d):
    ts = f"{l['ts']:.4f}"
    if not d.valid:
        return f"{ts} {l['from']:>9} [bare glyph, not an envelope: {d.reason}]"
    rep = f" re:{float(d.get('reply_to')):.4f}" if d.get("reply_to") else ""
    return (f"{ts} {d.get('from') or '?':>9} -> {d.get('to') or '?':<8} "
            f"{d.get('act') or '?':<8}{rep} fid={d.fidelity:.2f}  "
            f"{render(d.content)}")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawTextHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("send")
    s.add_argument("sender"); s.add_argument("to"); s.add_argument("act")
    s.add_argument("content"); s.add_argument("--reply", type=float)
    s.add_argument("--text", default=""); s.add_argument("--extra", default="{}")
    i = sub.add_parser("inbox"); i.add_argument("me")
    i.add_argument("--since", type=float, default=0.0)
    r = sub.add_parser("read"); r.add_argument("--since", type=float, default=0.0)
    sub.add_parser("threads")
    sub.add_parser("audit")
    a = ap.parse_args(argv)

    if a.cmd == "send":
        msg = P.send(a.sender, a.to, a.act, _content(a.content),
                     reply_ts=a.reply, text=a.text, **json.loads(a.extra))
        print(f"posted ts={msg['ts']!r}")
    elif a.cmd == "inbox":
        for l, d in P.inbox(a.me, a.since):
            print(_line(l, d))
    elif a.cmd == "read":
        for l, d in P.resolve():
            if l["ts"] > a.since:
                print(_line(l, d))
    elif a.cmd == "threads":
        for root, branches in P.threads().items():
            print(f"conversation {root}: {len(branches)} branch(es)")
            for chain in branches:
                print(f"   {len(chain)} turns: {' -> '.join(chain)}")
    elif a.cmd == "audit":
        print(json.dumps(P.audit(), indent=1))


if __name__ == "__main__":
    main()
