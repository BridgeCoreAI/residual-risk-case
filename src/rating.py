"""Risk rating helpers. Bands match the infographic: Low 1-5, Medium 6-11, High 12-19, Critical 20-25."""
from datetime import datetime, timezone

BANDS = [(1, 5, "Low"), (6, 11, "Medium"), (12, 19, "High"), (20, 25, "Critical")]
MAX_EVIDENCE_AGE_DAYS = 90
REDUCTION_RULE = "Likelihood drops 2 levels (floor 1) only if design, implementation and operation tests all pass and the evidence is under 90 days old. Otherwise residual equals inherent."


def band(score: int) -> str:
    for lo, hi, name in BANDS:
        if lo <= score <= hi:
            return name
    raise ValueError(f"score out of range: {score}")


def rate(likelihood: int, impact: int) -> dict:
    for v in (likelihood, impact):
        if not 1 <= v <= 5:
            raise ValueError("likelihood and impact must be 1-5")
    score = likelihood * impact
    return {"likelihood": likelihood, "impact": impact, "score": score, "band": band(score)}


def residual(inherent: dict, evidence: dict | None, now: datetime | None = None) -> dict:
    """Residual risk from inherent rating and a test evidence record (or None if untested)."""
    now = now or datetime.now(timezone.utc)
    reason = "No evidence: control untested, residual equals inherent."
    reduce = False
    if evidence:
        results = evidence["results"]
        dims_pass = all(results.get(d) == "pass" for d in ("design", "implementation", "operation"))
        age = (now - datetime.fromisoformat(evidence["tested_at"])).days
        if not dims_pass:
            reason = "At least one test dimension failed: residual equals inherent."
        elif age > MAX_EVIDENCE_AGE_DAYS:
            reason = f"Evidence is {age} days old (limit {MAX_EVIDENCE_AGE_DAYS}): residual equals inherent."
        else:
            reduce = True
            reason = "All three dimensions passed with current evidence: likelihood reduced by 2 levels."
    likelihood = max(1, inherent["likelihood"] - 2) if reduce else inherent["likelihood"]
    out = rate(likelihood, inherent["impact"])
    out["rationale"] = reason
    return out
