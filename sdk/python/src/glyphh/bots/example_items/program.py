"""HN reader's code steps: fetching the stories, each story's case for the `worth` gate, checking the digest and
delivering it. The gate does the judging (it learns which stories the person reads); this code never guesses for it.

Hard gates, here in code: only stories not judged before (kept in the bot's own data.sqlite), and a digest that names
every story kept (`digest_ok`). The rest are bot.json's limits: at most 30 stories, $0.50 a run, quiet hours."""

import time
import urllib.parse

API = "https://hn.algolia.com/api/v1"
FRONT = f"{API}/search?tags=front_page&hitsPerPage=50"
#: When the front page holds fewer new stories than this, it is topped up from the best recent ones not yet seen.
TOP_UP = 20
#: At most this many stories a run (bot.json's max_items holds the gate to it too).
MAX_STORIES = 30
KINDS = (("show hn", "show"), ("ask hn", "ask"), ("launch hn", "launch"), ("tell hn", "tell"))


def _seen(ctx):
    db = ctx.db()
    db.execute("CREATE TABLE IF NOT EXISTS seen (id TEXT PRIMARY KEY, run TEXT)")
    return db


def _story(hit, now):
    sid = str(hit.get("objectID") or "")
    title = (hit.get("title") or "").strip()
    if not sid or not title:
        return None
    hn = f"https://news.ycombinator.com/item?id={sid}"
    url = hit.get("url") or hn
    domain = (urllib.parse.urlparse(url).hostname or "news.ycombinator.com").removeprefix("www.")
    low = title.lower()
    kind = next((k for prefix, k in KINDS if low.startswith(prefix)), "link" if hit.get("url") else "text")
    created = hit.get("created_at_i") or now
    return {
        "id": sid,
        "title": title,
        "url": url,
        "hn": hn,
        "domain": domain,
        "kind": kind,
        "points": int(hit.get("points") or 0),
        "comments": int(hit.get("num_comments") or 0),
        "age_hours": max(0, round((now - created) / 3600)),
        "author": hit.get("author") or "",
    }


def front_page(ctx, inputs):
    """The front page's stories not judged before; topped up from the best recent stories when few are new."""
    now = time.time()
    db = _seen(ctx)
    seen = {r[0] for r in db.execute("SELECT id FROM seen")}
    found, ids = [], set()

    def take(hits):
        for hit in hits:
            s = _story(hit, now)
            if s and s["id"] not in seen and s["id"] not in ids:
                ids.add(s["id"])
                found.append(s)

    take(ctx.http_json(FRONT).get("hits", []))
    page = 0
    while len(found) < TOP_UP and page < 3:
        since = int(now - 7 * 86400)
        filters = urllib.parse.quote(f"points>=100,created_at_i>={since}")
        more = ctx.http_json(f"{API}/search?tags=story&numericFilters={filters}&hitsPerPage=50&page={page}")
        take(more.get("hits", []))
        page += 1
    if not found:
        return {"_end": "no story the bot has not judged before"}
    found = found[:MAX_STORIES]  # the rest stay unseen, for the next run
    db.executemany("INSERT OR IGNORE INTO seen VALUES (?, ?)", [(s["id"], ctx.run_id) for s in found])
    db.commit()
    ctx.log(f"{len(found)} stories not judged before")
    return {"items": found}


def story_case(ctx, story):
    """The worth gate's case for one story: what it is, how much pull it has, its id."""
    return {
        "story": {
            "what": {"title": story["title"], "domain": story["domain"], "kind": story["kind"]},
            "pull": {
                "points": min(1000, story["points"]),
                "comments": min(1000, story["comments"]),
                "age_hours": min(72, story["age_hours"]),
            },
            "id": {"story": story["id"]},
        }
    }


def digest_ok(ctx, answer, data):
    """The digest names every story kept, by its link: an answer that leaves one out is sent back once."""
    kept = data["worth"]["read"]
    missing = [s["title"] for s in kept if s["url"] not in answer and s["hn"] not in answer]
    if missing:
        return f"the digest leaves out {len(missing)} of the stories: {'; '.join(missing[:5])}"
    return True


def deliver(ctx, inputs):
    """The digest into out/digest.md (the newest) and out/<date>.md."""
    out = ctx.dir / "out"
    out.mkdir(exist_ok=True)
    text = inputs if isinstance(inputs, str) else str(inputs)
    (out / "digest.md").write_text(text)
    (out / f"{ctx.today.isoformat()}.md").write_text(text)
    return {"path": str(out / "digest.md"), "stories": len(ctx.data["worth"]["read"])}
