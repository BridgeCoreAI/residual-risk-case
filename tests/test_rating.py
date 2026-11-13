"""Rating logic: includes the untested and failed-control cases. Names avoid the three dimension prefixes on purpose."""
from datetime import datetime, timedelta, timezone

from src.rating import rate, residual

NOW = datetime(2026, 11, 13, tzinfo=timezone.utc)
INH = rate(4, 5)


def ev(days_old=0, **over):
    r = {"design": "pass", "implementation": "pass", "operation": "pass"}
    r.update(over)
    return {"tested_at": (NOW - timedelta(days=days_old)).isoformat(), "results": r}


def test_rating_inherent_is_20_critical():
    assert (INH["score"], INH["band"]) == (20, "Critical")


def test_rating_passing_evidence_gives_10_medium():
    r = residual(INH, ev(), NOW)
    assert (r["score"], r["band"]) == (10, "Medium")


def test_rating_untested_stays_20_critical():
    r = residual(INH, None, NOW)
    assert (r["score"], r["band"]) == (20, "Critical")


def test_rating_failed_dimension_stays_20():
    assert residual(INH, ev(operation="fail"), NOW)["score"] == 20


def test_rating_stale_evidence_stays_20():
    assert residual(INH, ev(days_old=91), NOW)["score"] == 20
