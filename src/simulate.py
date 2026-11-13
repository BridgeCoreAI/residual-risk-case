"""Deterministic simulation: a fixed stream of synthetic location-read requests run through
three configurations: the real gate, a defective gate, and no control.

No randomness, no network, synthetic data only. A leak is a read that was allowed although the
request should have been refused (purpose not permitted, or consent missing, wrong or expired).
Each run produces a hash-chained decision log that can be verified and shows tampering.
"""
import hashlib
import json
from datetime import datetime, timedelta, timezone

from .defective_gate import DefectiveGate, NoControl
from .purpose_gate import Gate, LocationStore, PurposeViolation, POLICY

NOW = datetime(2026, 11, 13, 12, 0, tzinfo=timezone.utc)
FUTURE = (NOW + timedelta(days=30)).isoformat()
PAST = (NOW - timedelta(days=1)).isoformat()

CONSENTS = {
    "consent_all": {"purposes": ["navigation", "fraud_prevention", "marketing", "analytics", "ad_targeting"], "expires_at": FUTURE},
    "consent_nav_only": {"purposes": ["navigation"], "expires_at": FUTURE},
    "consent_expired": {"purposes": ["navigation", "fraud_prevention"], "expires_at": PAST},
    "consent_none": {"purposes": [], "expires_at": FUTURE},
}
PURPOSES = ["navigation", "fraud_prevention", "marketing", "analytics", "ad_targeting", None, "Navigation", " navigation"]
DATA = {"u1": {"lat": 38.9, "lon": -77.0}}


def stream():
    return [(p, ck) for ck in CONSENTS for p in PURPOSES]


def should_allow(purpose, consent):
    return (isinstance(purpose, str) and purpose in POLICY["permitted_purposes"]
            and purpose in consent["purposes"] and datetime.fromisoformat(consent["expires_at"]) > NOW)


def chain(entries):
    prev, out = "0" * 64, []
    for e in entries:
        h = hashlib.sha256((prev + json.dumps(e, sort_keys=True)).encode()).hexdigest()
        out.append({**e, "prev": prev, "hash": h})
        prev = h
    return out


def verify_chain(chained):
    prev = "0" * 64
    for e in chained:
        body = {k: v for k, v in e.items() if k not in ("prev", "hash")}
        if e["prev"] != prev or e["hash"] != hashlib.sha256((prev + json.dumps(body, sort_keys=True)).encode()).hexdigest():
            return False
        prev = e["hash"]
    return True


def run(gate):
    store = LocationStore(gate, DATA)
    entries, leaks, over_blocks, allowed = [], 0, 0, 0
    for i, (purpose, ck) in enumerate(stream()):
        consent, expected = CONSENTS[ck], should_allow(purpose, CONSENTS[ck])
        try:
            store.read("u1", purpose, consent, NOW)
            got = True
        except PurposeViolation:
            got = False
        allowed += got
        leaks += got and not expected
        over_blocks += (not got) and expected
        entries.append({"n": i, "purpose": purpose, "consent": ck, "expected_allow": expected,
                        "allowed": got, "why": gate.log[-1]["why"]})
    ch = chain(entries)
    return {"requests": len(entries), "allowed": allowed, "blocked": len(entries) - allowed,
            "leaks": leaks, "over_blocks": over_blocks, "chain_verified": verify_chain(ch),
            "chain_head": ch[-1]["hash"], "log": ch}


def run_all():
    return {"gate_on": run(Gate()), "defective_fixture": run(DefectiveGate()), "no_control": run(NoControl())}


def summary(results):
    return {k: {f: v[f] for f in ("requests", "allowed", "blocked", "leaks", "over_blocks", "chain_verified", "chain_head")}
            for k, v in results.items()}


if __name__ == "__main__":
    r = run_all()
    print(json.dumps(summary(r), indent=2))
    tampered = [dict(e) for e in r["gate_on"]["log"]]
    tampered[3]["allowed"] = not tampered[3]["allowed"]
    print("tamper detected:", not verify_chain(tampered))
