"""Deliberately defective fixture. Educational only, not a real incident.

It checks that consent exists and has not expired, but never checks the purpose
against the permitted list. This is the "approval exists" mistake: the gate looks
like a control but lets marketing reads through.
"""
from datetime import datetime, timezone

from .purpose_gate import Gate


class DefectiveGate(Gate):
    def decide(self, purpose, consent, now=None):
        now = now or datetime.now(timezone.utc)
        allowed = bool(consent.get("purposes")) and datetime.fromisoformat(consent["expires_at"]) > now
        self.log.append({"purpose": purpose, "allowed": allowed,
                         "why": "consent exists (purpose not checked)" if allowed else "no valid consent",
                         "at": now.isoformat()})
        return allowed


class NoControl(Gate):
    """Baseline: no gate at all. Every read is allowed."""

    def decide(self, purpose, consent, now=None):
        now = now or datetime.now(timezone.utc)
        self.log.append({"purpose": purpose, "allowed": True, "why": "no control", "at": now.isoformat()})
        return True
