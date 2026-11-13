"""Preventive control: purpose limitation gate for precise geolocation data.

Default deny. Access is allowed only when the stated purpose is on the permitted list,
the user's consent covers that purpose, and the consent has not expired.
Every decision is logged so operation can be evidenced.
"""
from dataclasses import dataclass, field
from datetime import datetime, timezone

POLICY = {
    "data_class": "precise_geolocation",
    "permitted_purposes": ["navigation", "fraud_prevention"],
}


class PurposeViolation(Exception):
    pass


@dataclass
class Gate:
    policy: dict = field(default_factory=lambda: dict(POLICY))
    log: list = field(default_factory=list)

    def decide(self, purpose, consent: dict, now: datetime | None = None) -> bool:
        now = now or datetime.now(timezone.utc)
        allowed, why = False, "default deny"
        if not isinstance(purpose, str) or not purpose:
            why = "missing purpose"
        elif purpose not in self.policy["permitted_purposes"]:  # exact match, no normalisation
            why = "purpose not permitted"
        elif purpose not in consent.get("purposes", []):
            why = "no consent for purpose"
        elif datetime.fromisoformat(consent["expires_at"]) <= now:
            why = "consent expired"
        else:
            allowed, why = True, "permitted purpose with valid consent"
        self.log.append({"purpose": purpose, "allowed": allowed, "why": why, "at": now.isoformat()})
        return allowed


class LocationStore:
    """The only path to the data. Reads go through the gate."""

    def __init__(self, gate: Gate, records: dict):
        self._gate, self._records = gate, records

    def read(self, user_id: str, purpose, consent: dict, now: datetime | None = None):
        if not self._gate.decide(purpose, consent, now):
            raise PurposeViolation(self._gate.log[-1]["why"])
        return self._records[user_id]
