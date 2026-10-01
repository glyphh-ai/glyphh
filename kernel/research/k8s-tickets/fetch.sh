#!/usr/bin/env bash
# Fetch a year of kubernetes/kubernetes issues (search API, half-month
# slices to stay under its 1000-result cap) and their linked fix PRs.
# Needs an authenticated `gh`. Usage: ./fetch.sh <data dir>
set -euo pipefail
dir=${1:?data dir}; here=$(cd "$(dirname "$0")" && pwd)
mkdir -p "$dir" && cd "$dir" && : > issues.jsonl
for m in 2025-10 2025-11 2025-12 2026-01 2026-02 2026-03 2026-04 2026-05 2026-06 2026-07 2026-08 2026-09; do
  y=${m%-*}; mo=${m#*-}
  end=$(python3 -c "import calendar; print(calendar.monthrange($y, int('$mo'))[1])")
  for half in "01..15" "16..$end"; do a=${half%..*}; b=${half#*..}
    gh api -X GET search/issues -f q="repo:kubernetes/kubernetes is:issue created:$m-$a..$m-$b" \
      -f per_page=100 --paginate \
      --jq '.items[] | {number, title, body, state, state_reason, created_at, closed_at, labels: [.labels[].name], comments, author: .user.login}' \
      >> issues.jsonl
  done
done
python3 "$here/fetch_fixes.py"
