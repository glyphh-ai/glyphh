"""Generate Security Incidents cases to TypeSafe's published format: an alert, the asset, and the records the
pipeline joined to it.

Each case is a technique (an Atomic Red Team test, as TypeSafe's case ids are) crossed with a context factor that
may or may not explain the activity, on an asset of some environment and tier. Claude Opus 5.5 writes the documents,
shown TypeSafe's published examples for the format only. No labels are generated here: the references label every
case (judge.py).

    uv run python generate.py --n 10        # writes data/cases/security_incidents.jsonl
"""

from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

import anthropic

import published

HERE = Path(__file__).parent
CASES = HERE / "data" / "cases"
MODEL = "claude-opus-5-5"

# (Atomic Red Team test, what it does, the detector's domain)
TECHNIQUES = [
    ("T1003.001-2", "LSASS memory dump via comsvcs.dll MiniDump", "endpoint"),
    ("T1021.006-1", "remote command execution over WinRM", "identity"),
    ("T1040-5", "network sniffing with a packet capture driver", "identity"),
    ("T1053.005-1", "scheduled task created for persistence", "endpoint"),
    (
        "T1059.001-17",
        "PowerShell download cradle executing a remote script",
        "endpoint",
    ),
    ("T1070.001-1", "Windows event logs cleared with wevtutil", "endpoint"),
    ("T1078.004-1", "cloud account sign-in from an unfamiliar country", "identity"),
    ("T1098.001-3", "new access key added to a cloud IAM user", "cloud"),
    ("T1110.003-1", "password spraying against many accounts", "identity"),
    ("T1114.003-1", "mailbox forwarding rule to an external address", "mail"),
    ("T1136.001-1", "local administrator account created", "endpoint"),
    ("T1218.011-1", "rundll32 proxy execution of an unsigned DLL", "endpoint"),
    ("T1486-1", "files encrypted in bulk with a ransom note dropped", "endpoint"),
    ("T1528-1", "OAuth consent granted to an unverified application", "cloud"),
    ("T1539-1", "browser session cookie stolen and replayed", "identity"),
    ("T1546.018-2", "Python startup hook placed for persistence", "endpoint"),
    ("T1547.001-1", "Run key added to the registry", "endpoint"),
    ("T1555.003-1", "credentials read from the browser store", "endpoint"),
    ("T1566.002-1", "phishing link delivered to several inboxes", "mail"),
    ("T1567.002-1", "data archive uploaded to a cloud storage service", "network"),
    ("T1572-1", "DNS tunnelling to an external resolver", "network"),
    ("T1574.001-2", "DLL search-order hijack of a signed binary", "endpoint"),
    ("T1621-1", "MFA push fatigue: many prompts until one is accepted", "identity"),
    ("T1648-1", "serverless function created to run attacker code", "cloud"),
]

# What the joined records say about the activity
FACTORS = {
    "change_covers": "an approved change request covers this exact activity, actor, asset and window",
    "maintenance_window": "scheduled maintenance booked in advance covers this asset at this time",
    "standing_authorization": "a standing authorization (e.g. a sanctioned red-team engagement) names this actor and activity",
    "badge_onsite": "badge records put the person onsite at the time, consistent with the activity",
    "factor_established": "the sign-in used a long-established MFA factor and registered device",
    "change_adjacent": "a change request exists but for a different asset or an earlier window: it does not cover this",
    "factor_recent": "a new MFA factor was enrolled minutes before the activity",
    "time_off": "the person is on approved time off at the time of the activity",
    "peer_contained": "a peer host showed the same activity last week and was contained as an incident",
    "none": "nothing in the records relates to the activity",
}
# How strong and how live the evidence of the activity is
EVIDENCE = {
    "weak": "a single indicator that could be benign; nothing corroborates it",
    "corroborated": "several independent indicators agree the activity happened; it may already have stopped",
    "live": "the activity is ongoing and clearly hostile: pick what fits the technique among a process still running, "
    "an outbound channel open to an attacker host, persistence still installed, a session in use by someone else, "
    "malicious mail still in inboxes, or a second host or account already involved",
}
ASSETS = [
    ("dev", 2, "Workstation"),
    ("prod", 2, "Workstation"),
    ("prod", 1, "Server"),
    ("prod", 0, "Server"),
    ("prod", 0, "Domain Controller"),
    ("dev", 1, "Server"),
]

SCHEMA = {
    "type": "object",
    "properties": {
        "alert": {"type": "string"},
        "context": {
            "type": "object",
            "properties": {
                "asset": {
                    "type": "object",
                    "properties": {
                        "environment": {"type": "string"},
                        "tier": {"type": "integer"},
                        "type": {"type": "string"},
                    },
                    "required": ["environment", "tier", "type"],
                    "additionalProperties": False,
                },
                "records": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["asset", "records"],
            "additionalProperties": False,
        },
    },
    "required": ["alert", "context"],
    "additionalProperties": False,
}


def brief(
    technique: tuple[str, str, str],
    factor: str,
    evidence: str,
    asset: tuple[str, int, str],
    examples: list[dict],
) -> str:
    test, what, domain = technique
    env, tier, kind = asset
    return f"""You write realistic test data for a security operations benchmark: one alert as a SOC pipeline delivers \
it, with the records the pipeline joined to it. Match the format of these examples exactly (a JSON object with \
"alert" and "context"; each record is a string whose first line is the source table, then indented key: value \
lines):

{json.dumps(examples, indent=1)}

Write a new, different case:
- Atomic Red Team test {test}: {what}. The detector's domain is {domain}.
- The asset: environment {env}, tier {tier}, type {kind} (a domain controller is a Server whose records say so).
- What the records say about the activity: {FACTORS[factor]}.
- The evidence in the alert and records: {EVIDENCE[evidence]}.
- 10 to 17 records, mixing the sources in the examples (activedirectory, crowdstrike, intune, tanium, okta, \
servicenow, lenel, workday), with irrelevant records as a real pipeline would join them. Invent a different \
company, people, hostnames, IDs and timestamps in 2026.
- Do not state a verdict anywhere: no record may say whether the activity is malicious or authorized beyond what \
its fields show. Let the evidence be as ambiguous or clear as the factor implies.

Return only the JSON object."""


def main() -> None:
    p = argparse.ArgumentParser(description="Generate Security Incidents cases")
    p.add_argument("--n", type=int, default=10)
    p.add_argument("--seed", type=int, default=7)
    p.add_argument("--out", default="security_incidents.jsonl")
    p.add_argument("--model", default=MODEL)
    a = p.parse_args()

    examples = published.load("security_incidents")["documents"][:2]
    rng = random.Random(a.seed)  # noqa: S311  (the case mix, not a secret)
    CASES.mkdir(parents=True, exist_ok=True)
    out = CASES / a.out
    done = {json.loads(line)["id"] for line in out.open()} if out.exists() else set()
    client = anthropic.Anthropic()
    tokens_in = tokens_out = 0
    for i in range(a.n):
        technique, factor, asset = (
            rng.choice(TECHNIQUES),
            rng.choice(list(FACTORS)),
            rng.choice(ASSETS),
        )
        evidence = rng.choice(list(EVIDENCE))
        cid = f"{technique[0]}__{factor}__{evidence}__{asset[0]}{asset[1]}_s{a.seed}_{i:03d}"  # unique per batch
        if cid in done:
            continue
        # Security test data can trip the cyber classifier; the server-side fallback answers what Opus 5.5 declines.
        # Haiku 5.5 has no server-side fallback, so its refusals are skipped and counted.
        fallback = {} if a.model.startswith("claude-haiku") else {
            "betas": ["server-side-fallback-2026-07-01"],
            "extra_body": {"fallbacks": "default"},
        }
        r = client.beta.messages.create(
            model=a.model,
            max_tokens=16000,
            messages=[{"role": "user", "content": brief(technique, factor, evidence, asset, examples)}],
            output_config={"effort": "medium", "format": {"type": "json_schema", "schema": SCHEMA}},
            **fallback,
        )
        tokens_in += r.usage.input_tokens
        tokens_out += r.usage.output_tokens
        if r.stop_reason != "end_turn":
            print(f"{cid}: stopped ({r.stop_reason}), skipped")
            continue
        state = json.loads(next(b.text for b in r.content if b.type == "text"))
        case = {
            "id": cid,
            "technique": technique[0],
            "factor": factor,
            "evidence": evidence,
            "domain": technique[2],
            "environment": asset[0],
            "tier": asset[1],
            "domain_controller": asset[2] == "Domain Controller",
            "state": state,
        }
        with out.open("a") as f:
            f.write(json.dumps(case) + "\n")
        print(f"{cid}: {len(state['context']['records'])} records")
    print(f"generation: {tokens_in:,} input and {tokens_out:,} output tokens")


if __name__ == "__main__":
    main()
