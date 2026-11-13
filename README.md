# Residual Risk Case: Precise Geolocation (GEO-001)

A worked, executable example of moving from inherent risk to residual risk by testing the control, not by assuming it works.

| Step | Where |
|---|---|
| 1 Risk scenario | `risk_register/geo-001.json` |
| 2 Inherent risk: Likelihood 4 x Impact 5 = 20 (Critical) | `risk_register/geo-001.json`, `src/rating.py` |
| 3 Relevant control: purpose limitation gate (preventive) | `src/purpose_gate.py` |
| 4 Test effectiveness: design, implementation, operation | `tests/test_control.py` |
| 5 Residual risk, computed from the evidence | `scripts/run_evidence.py`, `src/rating.py` |
| 6 Owner decision | Recorded by the risk owner against `tolerance` in the register |
| 7 Reassess on triggers | `reassess_on` in the register; CI reruns on every push and monthly |

## Run it
```
pip install pytest
python scripts/run_evidence.py --tester "Your Name"
```
Writes `evidence/evidence-<timestamp>.json`: what was tested, when, by whom, under what conditions (commit, platform, data, clock), per-test results, and the rating outcome.

## Reduction rule (a recorded judgment, not a derived value)
Likelihood drops 2 levels (floor 1) only if design, implementation and operation tests all pass and the evidence is under 90 days old. Otherwise residual equals inherent.

- Tests pass: 4 x 5 = 20 becomes 2 x 5 = 10 (Medium)
- Untested, failed or stale evidence: stays 20 (Critical)

## Simulation
`python -m src.simulate` runs a fixed stream of 32 synthetic requests (8 purposes x 4 consent states) three ways. Leak = allowed although it should have been refused.

| Configuration | Allowed | Blocked | Leaks |
|---|---|---|---|
| Purpose gate | 3 | 29 | 0 |
| Defective fixture (checks consent exists, not purpose) | 16 | 16 | 13 |
| No control | 32 | 0 | 29 |

Each run writes a hash-chained decision log; altering one entry breaks verification. `sim/index.html` is a separate browser illustration of the same idea. It does not call the Python code and keeps everything in page memory. The defective fixture is an educational example, not a real incident.

## Evidence record
`scripts/run_evidence.py` writes `evidence/evidence-<timestamp>.json` plus a `.manifest.json` holding its SHA256, and records commit, CI run id and attempt, Python version, test results by dimension, the simulation results, and the rating outcome. CI runs on Python 3.10 and 3.12.

## Negative check
Weakening the gate (removing the permitted-purpose check) makes the operation tests fail and the residual stays 20. The rating cannot improve without passing evidence.

## Limits
The simulation covers scenarios written for this gate; it does not measure how often real misuse occurs, so it supports the effectiveness rating but cannot set likelihood. Single process, synthetic data, trusted inputs (purpose, consent, clock), in-memory logs, and no independent assurance.
Ratings are illustrative. Synthetic data only. Tests show this gate behaves as specified; they do not prove no other code path reads the data. The risk owner decides treat, monitor or accept.
