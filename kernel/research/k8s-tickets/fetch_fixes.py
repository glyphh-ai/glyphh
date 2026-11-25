"""Linked fix PRs (and the files they touched) for every closed issue in
issues.jsonl, via GitHub GraphQL. Writes fixes.json. Run in the data dir."""

import json, subprocess, sys
rows = [json.loads(l) for l in open("issues.jsonl")]
nums = [r["number"] for r in rows if r["state"] == "closed"]
out = {}
for i in range(0, len(nums), 20):
    chunk = nums[i:i+20]
    fields = "\n".join(
        f'i{n}: issue(number: {n}) {{ closedByPullRequestsReferences(first: 3, includeClosedPrs: false) '
        f'{{ nodes {{ number merged mergedAt files(first: 60) {{ nodes {{ path }} }} }} }} }}' for n in chunk)
    q = f'query {{ repository(owner: "kubernetes", name: "kubernetes") {{ {fields} }} }}'
    res = subprocess.run(["gh", "api", "graphql", "-f", f"query={q}"], capture_output=True, text=True)
    if res.returncode:
        print("err", res.stderr[:300], file=sys.stderr); continue
    data = json.loads(res.stdout)["data"]["repository"]
    for k, v in data.items():
        prs = [{"number": p["number"], "merged": p["merged"], "mergedAt": p["mergedAt"],
                "files": [f["path"] for f in p["files"]["nodes"]]}
               for p in (v or {}).get("closedByPullRequestsReferences", {}).get("nodes", []) if p]
        if prs: out[k[1:]] = prs
json.dump(out, open("fixes.json", "w"))
print("closed issues:", len(nums), "with linked fix PRs:", len(out))
