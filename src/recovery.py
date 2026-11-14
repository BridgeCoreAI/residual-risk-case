"""Bounded recovery of a control claim after a defective control is found.

Claim: the purpose limitation gate reduces GEO-001 residual risk to 10 (Medium).
States: VALID -> INVALIDATED -> CORRECTED_PENDING_RETEST -> PENDING_REVIEW -> RESTORED_BOUNDED

Rules enforced here:
- The claim is invalidated only if a leak is actually observed.
- The corrected source is bound to its SHA256 and must differ from the defective one.
- Retest must use the same recorded condition and the same corrected version, and the regression
  suite must pass. A new failure sends the claim back to INVALIDATED.
- Restoration needs a designated reviewer and a claim in PENDING_REVIEW. It restores only the
  recorded claim. It does not authorize any future read: each read still needs its own gate decision.

Simulated: the reviewer is a role name passed in, not an authenticated identity.
"""
import hashlib
from datetime import datetime, timezone
from pathlib import Path

from .simulate import chain, run

CLAIM = {
    "id": "GEO-001-CLAIM-1",
    "statement": "The purpose limitation gate reduces GEO-001 residual risk to 10 (Medium).",
    "condition": "Fixed synthetic stream of 32 requests, zero leaks and zero over-blocks.",
    "stream_size": 32,
}
DESIGNATED_REVIEWERS = {"chief-privacy-officer"}
BOUNDS = "Restores only the recorded claim. It does not authorize any future read; each read needs its own gate decision."


class RecoveryError(Exception):
    pass


def sha256_file(path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class Recovery:
    def __init__(self):
        self.state = "VALID"
        self.events = []
        self.defective_sha = None
        self.corrected_sha = None

    def _log(self, event, **detail):
        self.events.append({"event": event, "state": self.state, "claim": CLAIM["id"],
                            "at": datetime.now(timezone.utc).isoformat(), **detail})

    def invalidate(self, defective_source, gate):
        if self.state != "VALID":
            raise RecoveryError(f"cannot invalidate from {self.state}")
        result = run(gate)
        if result["leaks"] == 0:
            raise RecoveryError("no leak observed: claim is not invalidated")
        self.defective_sha = sha256_file(defective_source)
        self.state = "INVALIDATED"
        self._log("claim_invalidated", leaks=result["leaks"], requests=result["requests"],
                  defective_sha256=self.defective_sha, chain_head=result["chain_head"])

    def record_correction(self, corrected_source):
        if self.state != "INVALIDATED":
            raise RecoveryError(f"cannot record a correction from {self.state}")
        digest = sha256_file(corrected_source)
        if digest == self.defective_sha:
            raise RecoveryError("corrected source is identical to the defective source")
        self.corrected_sha = digest
        self.state = "CORRECTED_PENDING_RETEST"
        self._log("correction_recorded", corrected_sha256=digest)

    def retest(self, corrected_source, gate, regression_passed, stream_size=CLAIM["stream_size"]):
        if self.state != "CORRECTED_PENDING_RETEST":
            raise RecoveryError(f"cannot retest from {self.state}")
        if sha256_file(corrected_source) != self.corrected_sha:
            raise RecoveryError("wrong version: source differs from the recorded corrected version")
        if stream_size != CLAIM["stream_size"]:
            raise RecoveryError("wrong condition: retest must use the recorded stream")
        if not regression_passed:
            self._log("retest_blocked_regression_failed")
            return False
        result = run(gate)
        if result["leaks"] or result["over_blocks"]:
            self.state = "INVALIDATED"
            self._log("retest_failed_new_failure", leaks=result["leaks"], over_blocks=result["over_blocks"])
            return False
        self.state = "PENDING_REVIEW"
        self._log("retest_passed", leaks=0, over_blocks=0, requests=result["requests"],
                  chain_head=result["chain_head"], corrected_sha256=self.corrected_sha)
        return True

    def restore(self, reviewer):
        if self.state != "PENDING_REVIEW":
            raise RecoveryError(f"premature restoration: state is {self.state}")
        if reviewer not in DESIGNATED_REVIEWERS:
            raise RecoveryError("restoration needs a designated reviewer")
        self.state = "RESTORED_BOUNDED"
        self._log("claim_restored_bounded", reviewer=reviewer, bounds=BOUNDS)

    def ledger(self):
        return chain(self.events)
