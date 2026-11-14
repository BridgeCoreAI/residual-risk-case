"""Run the recovery sequence end to end and write a hash-chained ledger plus a SHA256 manifest.

Usage: python scripts/run_recovery.py [--reviewer chief-privacy-officer] [--out evidence]
The reviewer is a simulated role name, not an authenticated identity.
"""
import argparse, hashlib, json, subprocess, sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from src.defective_gate import DefectiveGate  # noqa: E402
from src.purpose_gate import Gate  # noqa: E402
from src.recovery import Recovery, CLAIM  # noqa: E402
from src.simulate import verify_chain  # noqa: E402


def regression():
    p = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider",
                        "tests/test_control.py", "tests/test_rating.py", "tests/test_simulation.py"],
                       cwd=ROOT, capture_output=True, text=True)
    return p.returncode == 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--reviewer", default="chief-privacy-officer")
    ap.add_argument("--out", default="evidence")
    args = ap.parse_args()

    r = Recovery()
    r.invalidate(ROOT / "src/defective_gate.py", DefectiveGate())
    r.record_correction(ROOT / "src/purpose_gate.py")
    passed = r.retest(ROOT / "src/purpose_gate.py", Gate(), regression_passed=regression())
    if passed:
        r.restore(args.reviewer)
    led = r.ledger()
    now = datetime.now(timezone.utc)
    record = {"claim": CLAIM, "final_state": r.state, "ledger_verified": verify_chain(led), "ledger": led,
              "note": "Synthetic, single process. The reviewer is a simulated role, not an authenticated identity. The defective fixture is an educational example, not a real incident."}
    out = ROOT / args.out
    out.mkdir(exist_ok=True)
    path = out / f"recovery-{now.strftime('%Y%m%dT%H%M%SZ')}.json"
    path.write_text(json.dumps(record, indent=2))
    path.with_suffix(".manifest.json").write_text(json.dumps(
        {"file": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "created_at": now.isoformat()}, indent=2))
    print(json.dumps({"final_state": r.state, "ledger_verified": record["ledger_verified"],
                      "events": [e["event"] for e in led], "file": str(path.relative_to(ROOT))}, indent=2))
    sys.exit(0 if r.state == "RESTORED_BOUNDED" else 1)


if __name__ == "__main__":
    main()
