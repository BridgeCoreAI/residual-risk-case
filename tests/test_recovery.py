"""Recovery state machine tests, including the negative paths. Prefixed test_recovery_ so the
evidence runner reports them as a separate group."""
import pytest

from src.defective_gate import DefectiveGate
from src.purpose_gate import Gate
from src.recovery import Recovery, RecoveryError
from src.simulate import verify_chain

DEFECTIVE = "src/defective_gate.py"
CORRECTED = "src/purpose_gate.py"


def at_invalidated():
    r = Recovery()
    r.invalidate(DEFECTIVE, DefectiveGate())
    return r


def at_corrected():
    r = at_invalidated()
    r.record_correction(CORRECTED)
    return r


def at_pending_review():
    r = at_corrected()
    assert r.retest(CORRECTED, Gate(), regression_passed=True)
    return r


def test_recovery_full_sequence_reaches_bounded_restore():
    r = at_pending_review()
    r.restore("risk-owner")
    assert r.state == "RESTORED_BOUNDED"
    assert [e["event"] for e in r.events] == ["claim_invalidated", "correction_recorded", "retest_passed", "claim_restored_bounded"]
    assert "does not authorize any future read" in r.events[-1]["bounds"]


def test_recovery_ledger_chain_verifies_and_detects_tampering():
    r = at_pending_review()
    r.restore("risk-owner")
    led = r.ledger()
    assert verify_chain(led)
    t = [dict(e) for e in led]
    t[0]["leaks"] = 0
    assert not verify_chain(t)


def test_recovery_no_leak_means_no_invalidation():
    with pytest.raises(RecoveryError):
        Recovery().invalidate(CORRECTED, Gate())


def test_recovery_identical_source_is_not_a_correction():
    with pytest.raises(RecoveryError):
        at_invalidated().record_correction(DEFECTIVE)


def test_recovery_wrong_version_blocks_retest(tmp_path):
    other = tmp_path / "other.py"
    other.write_text("# different source\n")
    with pytest.raises(RecoveryError, match="wrong version"):
        at_corrected().retest(other, Gate(), regression_passed=True)


def test_recovery_wrong_condition_blocks_retest():
    with pytest.raises(RecoveryError, match="wrong condition"):
        at_corrected().retest(CORRECTED, Gate(), regression_passed=True, stream_size=8)


def test_recovery_failed_regression_blocks_progress():
    r = at_corrected()
    assert r.retest(CORRECTED, Gate(), regression_passed=False) is False
    assert r.state == "CORRECTED_PENDING_RETEST"
    with pytest.raises(RecoveryError, match="premature"):
        r.restore("risk-owner")


def test_recovery_new_failure_returns_to_invalidated():
    r = at_corrected()
    assert r.retest(CORRECTED, DefectiveGate(), regression_passed=True) is False
    assert r.state == "INVALIDATED"


@pytest.mark.parametrize("build", [lambda: Recovery(), at_invalidated, at_corrected])
def test_recovery_premature_restoration_refused(build):
    with pytest.raises(RecoveryError, match="premature"):
        build().restore("risk-owner")


def test_recovery_wrong_reviewer_refused():
    with pytest.raises(RecoveryError, match="designated reviewer"):
        at_pending_review().restore("someone-else")
