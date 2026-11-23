"""PR Review Digest's program: every weekday, the pull requests waiting on my review found and the ones that need me
today picked (the bot, its decision in Ada), the digest shown to me, and posted to me in Slack once I say so."""

FLOW = [
    {
        "id": "digest",
        "kind": "bot",
        "title": "Pick today's pull requests and write the digest",
        "task": "Find the pull requests waiting on my review, decide which need me today, and write the digest of "
        "those. Do not post it: answer with the digest alone.",
        "next": "approve",
        "at": [0, 0],
    },
    {
        "id": "approve",
        "kind": "ask",
        "title": "Post it?",
        "question": "Post this digest to you in Slack?\n\n{digest}",
        "options": ["Post", "Skip"],
        "next": {"Post": "post", "else": None},
        "at": [0, 140],
    },
    {
        "id": "post",
        "kind": "bot",
        "title": "Post the digest to me in Slack",
        "task": "Post this digest to me in Slack (@me), exactly as it is, and say where you posted it:\n\n{digest}",
        "next": None,
        "at": [0, 280],
    },
]
