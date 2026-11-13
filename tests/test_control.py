"""Control tests, grouped by the three effectiveness dimensions: design, implementation, operation.
Each test name starts with its dimension so the evidence runner can aggregate results."""
import inspect
from datetime import datetime, timedelta, timezone

import pytest

from src import purpose_gate
from src.purpose_gate import Gate, LocationStore, PurposeViolation, POLICY

NOW = datetime(2026, 11, 13, 12, 0, tzinfo=timezone.utc)
GOOD = {"purposes": ["navigation", "fraud_prevention", "marketing"], "expires_at": (NOW + timedelta(days=30)).isoformat()}
EXPIRED = {"purposes": ["navigation"], "expires_at": (NOW - timedelta(days=1)).isoformat()}
DATA = {"u1": {"lat": 38.9, "lon": -77.0}}


def store():
    return LocationStore(Gate(), DATA)


# ---- Design: does the control, as specified, address the scenario? ----
def test_design_policy_names_data_class_and_purposes():
    assert POLICY["data_class"] == "precise_geolocation"
    assert POLICY["permitted_purposes"]


def test_design_marketing_is_not_a_permitted_purpose():
    assert "marketing" not in POLICY["permitted_purposes"]


def test_design_default_is_deny():
    g = Gate()
    assert g.decide("anything_unlisted", GOOD, NOW) is False


# ---- Implementation: is it actually wired in, with no bypass in the access path? ----
def test_implementation_read_calls_gate():
    assert "_gate.decide" in inspect.getsource(LocationStore.read)


def test_implementation_no_public_path_to_raw_records():
    public = [n for n in dir(LocationStore) if not n.startswith("_")]
    assert public == ["read"]


def test_implementation_gate_uses_exact_match():
    src = inspect.getsource(Gate.decide)
    assert ".lower()" not in src and ".strip()" not in src


# ---- Operation: does it block misuse under realistic and adversarial conditions? ----
def test_operation_permitted_purpose_allowed():
    assert store().read("u1", "navigation", GOOD, NOW) == DATA["u1"]


@pytest.mark.parametrize("purpose", ["marketing", "analytics", "ad_targeting"])
def test_operation_use_beyond_permitted_purpose_blocked(purpose):
    with pytest.raises(PurposeViolation):
        store().read("u1", purpose, GOOD, NOW)


@pytest.mark.parametrize("purpose", [None, "", "Navigation", " navigation", "navigation ", "navigation;marketing"])
def test_operation_missing_or_spoofed_purpose_blocked(purpose):
    with pytest.raises(PurposeViolation):
        store().read("u1", purpose, GOOD, NOW)


def test_operation_expired_consent_blocked():
    with pytest.raises(PurposeViolation):
        store().read("u1", "navigation", EXPIRED, NOW)


def test_operation_no_consent_for_purpose_blocked():
    with pytest.raises(PurposeViolation):
        store().read("u1", "fraud_prevention", {"purposes": ["navigation"], "expires_at": GOOD["expires_at"]}, NOW)


def test_operation_every_decision_is_logged():
    s = store()
    s.read("u1", "navigation", GOOD, NOW)
    with pytest.raises(PurposeViolation):
        s.read("u1", "marketing", GOOD, NOW)
    assert [e["allowed"] for e in s._gate.log] == [True, False]
