"""
OpsWorld — a deterministic environment with ground truth.

Incidents arrive; each has attributes, an ordered event prelude, and
exactly one correct remediation. The world, not a human, grades every
action — that grounding is what replaces RLHF-style approval.

Two deliberate traps test the substrate:
- severity matters: high-severity db_latency needs failover, not a
  restart (same kind, different correct action by attribute)
- order matters: flap_up_down and flap_down_up share identical
  attributes and differ ONLY in event order — the strand must carry it
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Dict, List, Optional

ACTIONS = [
    "restart_db", "failover_db", "purge_cache", "rollback_deploy",
    "rate_limit", "renew_cert", "scale_up", "scale_down",
]


@dataclass
class Incident:
    kind: str
    situation: Dict[str, str]
    events: List[Dict[str, str]]
    correct_action: str


@dataclass
class OpsWorld:
    """Generates incidents and grades actions. Deterministic per seed."""

    seed: int = 7
    include_novel: bool = False
    _rng: random.Random = field(init=False)

    def __post_init__(self):
        self._rng = random.Random(self.seed)

    def _incident(self, kind: str) -> Incident:
        severity = self._rng.choice(["low", "high"])
        service = self._rng.choice(["checkout", "search", "billing"])
        base = {"kind": kind, "severity": severity, "service": service}

        if kind == "db_latency":
            correct = "failover_db" if severity == "high" else "restart_db"
            events = [{"signal": "slow_queries"}, {"signal": "conn_pool_full"}]
        elif kind == "stale_content":
            correct = "purge_cache"
            events = [{"signal": "cdn_miss_spike"}, {"signal": "old_asset_served"}]
        elif kind == "bad_deploy":
            correct = "rollback_deploy"
            events = [{"signal": "deploy_finished"}, {"signal": "error_rate_up"}]
        elif kind == "traffic_spike":
            correct = "rate_limit" if severity == "high" else "scale_up"
            events = [{"signal": "rps_up"}, {"signal": "latency_up"}]
        elif kind == "flap_up_down":
            # identical attributes to flap_down_up; only ORDER differs
            base = {"kind": "flapping", "severity": severity, "service": service}
            correct = "scale_down"
            events = [{"signal": "scale_event"}, {"signal": "drop_event"}]
        elif kind == "flap_down_up":
            base = {"kind": "flapping", "severity": severity, "service": service}
            correct = "scale_up"
            events = [{"signal": "drop_event"}, {"signal": "scale_event"}]
        elif kind == "cert_expiry":  # the novelty probe
            correct = "renew_cert"
            events = [{"signal": "tls_warning"}, {"signal": "handshake_fail"}]
        else:
            raise ValueError(kind)
        return Incident(kind=kind, situation=base, events=events,
                        correct_action=correct)

    def next_incident(self) -> Incident:
        kinds = ["db_latency", "stale_content", "bad_deploy",
                 "traffic_spike", "flap_up_down", "flap_down_up"]
        if self.include_novel:
            kinds = kinds + ["cert_expiry"]
        return self._incident(self._rng.choice(kinds))

    @staticmethod
    def grade(incident: Incident, action: str) -> bool:
        """The world's verdict. No human, no vibes — did it work?"""
        return action == incident.correct_action
