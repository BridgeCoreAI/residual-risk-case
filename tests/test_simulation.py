"""Simulation tests. Prefixed test_operation_ so the evidence runner counts them under operation."""
from src.simulate import run_all, verify_chain, stream, should_allow, CONSENTS


def test_operation_sim_stream_is_fixed_and_mixed():
    s = stream()
    assert len(s) == 32
    allowed = [x for x in s if should_allow(x[0], CONSENTS[x[1]])]
    assert 0 < len(allowed) < len(s)


def test_operation_sim_gate_on_has_zero_leaks_and_no_over_blocks():
    g = run_all()["gate_on"]
    assert g["leaks"] == 0 and g["over_blocks"] == 0


def test_operation_sim_defective_fixture_leaks():
    d = run_all()["defective_fixture"]
    assert d["leaks"] > 0


def test_operation_sim_no_control_leaks_everything_it_should_refuse():
    n = run_all()["no_control"]
    assert n["blocked"] == 0 and n["leaks"] > 0


def test_operation_sim_chain_verifies_and_detects_tampering():
    g = run_all()["gate_on"]["log"]
    assert verify_chain(g)
    t = [dict(e) for e in g]
    t[3]["allowed"] = not t[3]["allowed"]
    assert not verify_chain(t)


def test_operation_sim_is_deterministic():
    a, b = run_all(), run_all()
    assert a["gate_on"]["chain_head"] == b["gate_on"]["chain_head"]
