"""Security Incidents: TypeSafe's playbook, rebuilt from their published workflow diagram and threshold tests.

The model answers the questions; this code decides. Every contestant and both references go through the same code,
so where a threshold differs from TypeSafe's unpublished one, it differs for everyone alike.

Answers are normalised: a noul is its P(yes); a choice or a score is its probability per option.
"""

from __future__ import annotations

Answers = dict[str, float | dict[str, float]]

TRIAGE = ("is_true_positive", "context_explains_activity", "evidence_strength")


def disposition(a: Answers, case: dict) -> str:
    """close, queue or act, from the three triage answers and the asset."""
    tp, explained = a["is_true_positive"], a["context_explains_activity"]
    if tp < 0.15 and explained > 0.50 and not case["domain_controller"]:
        return "close"
    if tp > 0.75:
        return "act"
    return "queue"


def queue_action(a: Answers, case: dict) -> str:
    return (
        "NOTIFY USER"
        if case["domain"] == "identity" and 0.15 < a["is_true_positive"] <= 0.60
        else "ESCALATE TIER2"
    )


def containment_action(a: Answers, case: dict) -> str:
    """The first group whose conditions hold, then its strongest action that still applies."""
    scope = a["affected_scope"]
    widest = max(scope, key=scope.get)
    creds, session = a["credentials_exposed"], a["session_in_attacker_hands"]
    spread = a["spread_beyond_initial_entity"]

    if a["outbound_channel_active"] > 0.45:  # 1: data is leaving now
        return (
            "BLOCK DESTINATION"
            if widest == "organization_wide"
            else "BLOCK EGRESS ASSET"
        )
    if creds > 0.40 or session > 0.50:  # 2: the attacker has access
        if session > 0.65 and spread > 0.50:
            return "DISABLE ACCOUNT"
        if creds > 0.60 and case["domain"] == "cloud":
            return "REVOKE ACCESS KEY"
        if session > 0.50 or creds > 0.60:
            return "REVOKE SESSIONS"
        return "REQUIRE REAUTH"
    if a["malicious_content_in_mailboxes"] > 0.50:  # 3: malicious mail is delivered
        if spread > 0.50 or widest != "single_entity":
            return "BLOCK SENDER"
        if a["is_true_positive"] > 0.90:
            return "PURGE MAILBOXES"
        return "QUARANTINE MESSAGE"
    persistence, process = (
        a["attacker_persistence_present"],
        a["malicious_process_running"],
    )
    if persistence > 0.60 or process > 0.60:  # 4: the host is compromised
        lone_production = case["environment"] == "prod" and spread <= 0.50
        if persistence > 0.60 and a["activity_ongoing"] > 0.50 and not lone_production:
            return "ISOLATE HOST"
        if process > 0.60:
            return "KILL PROCESS"
        return "QUARANTINE FILE"
    if a["attacker_modified_configuration"] > 0.50:  # 5: configuration was changed
        return "REMOVE FORWARDING RULES"
    return "ESCALATE URGENT"


def decide(ask, case: dict) -> tuple[str, Answers]:
    """Run the workflow: `ask(question_ids)` returns normalised answers for those questions about the case's state.

    Returns the action and every answer the workflow used."""
    a: Answers = dict(ask(TRIAGE))
    d = disposition(a, case)
    if d == "close":
        return "AUTO CLOSE", a
    if d == "queue":
        return queue_action(a, case), a
    a.update(ask(CONTAINMENT))
    return containment_action(a, case), a


CONTAINMENT = (
    "credentials_exposed",
    "session_in_attacker_hands",
    "malicious_content_in_mailboxes",
    "attacker_persistence_present",
    "malicious_process_running",
    "outbound_channel_active",
    "attacker_modified_configuration",
    "activity_ongoing",
    "spread_beyond_initial_entity",
    "affected_scope",
    "attack_type",
)
