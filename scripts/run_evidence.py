"""Run the control tests, write a dated evidence record, and compute residual risk from it.

Usage: python scripts/run_evidence.py [--tester NAME] [--out evidence]
The evidence record answers: what was tested, when, by whom, under what conditions.
"""
import argparse, json, os, platform, subprocess, sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from src.rating import rate, residual, REDUCTION_RULE  # noqa: E402
from src.simulate import run_all, summary as sim_summary  # noqa: E402
import hashlib  # noqa: E402


def git(*a):
    try:
        return subprocess.check_output(["git", *a], cwd=ROOT, text=True, stderr=subprocess.DEVNULL).strip()
    except Exception:
        return "unavailable"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tester", default=os.environ.get("GITHUB_ACTOR", "local-run"))
    ap.add_argument("--out", default="evidence")
    args = ap.parse_args()

    scenario = json.loads((ROOT / "risk_register" / "geo-001.json").read_text())
    report = ROOT / ".pytest_report.json"
    proc = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "--junitxml", str(ROOT / ".junit.xml")],
                          cwd=ROOT, text=True, capture_output=True)
    import xml.etree.ElementTree as ET
    cases = ET.parse(ROOT / ".junit.xml").getroot().iter("testcase")
    results, detail = {"design": [], "implementation": [], "operation": [], "recovery": []}, []
    for c in cases:
        name = c.get("name")
        dim = name.split("_")[1]
        if dim not in results:
            continue
        ok = not any(ch.tag in ("failure", "error") for ch in c)
        results[dim].append(ok)
        detail.append({"test": name, "result": "pass" if ok else "fail"})
    summary = {d: ("pass" if v and all(v) else "fail") for d, v in results.items()}

    now = datetime.now(timezone.utc)
    evidence = {
        "scenario_id": scenario["id"],
        "control": scenario["control"]["name"],
        "tested_at": now.isoformat(),
        "tested_by": args.tester,
        "conditions": {
            "commit": git("rev-parse", "HEAD"),
            "python": platform.python_version(),
            "platform": platform.platform(),
            "environment": "CI" if os.environ.get("GITHUB_ACTIONS") else "local",
            "data": "synthetic records only; fixed clock 2026-11-13T12:00Z for time-based tests",
        },
        "results": summary,
        "test_count": len(detail),
        "tests": detail,
    }
    inherent = rate(scenario["inherent"]["likelihood"], scenario["inherent"]["impact"])
    outcome = {
        "inherent": inherent,
        "residual_if_tested": residual(inherent, evidence, now),
        "residual_if_untested": residual(inherent, None, now),
        "rule": REDUCTION_RULE,
        "note": "Illustrative ratings. The reduction rule is a recorded judgment, not a derived value. The risk owner decides treat, monitor or accept.",
    }
    evidence["outcome"] = outcome
    evidence["simulation"] = {
        "description": "Fixed stream of 32 synthetic read requests (8 purposes x 4 consent states), run with the gate, a deliberately defective fixture, and no control. Leak = allowed although it should have been refused.",
        "results": sim_summary(run_all()),
    }
    evidence["conditions"]["ci_run"] = os.environ.get("GITHUB_RUN_ID", "not a CI run")
    evidence["conditions"]["ci_attempt"] = os.environ.get("GITHUB_RUN_ATTEMPT", "n/a")

    out = ROOT / args.out
    out.mkdir(exist_ok=True)
    path = out / f"evidence-{now.strftime('%Y%m%dT%H%M%SZ')}.json"
    path.write_text(json.dumps(evidence, indent=2))
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    manifest = path.with_suffix(".manifest.json")
    manifest.write_text(json.dumps({"file": path.name, "sha256": digest, "created_at": now.isoformat()}, indent=2))
    for f in (".junit.xml", ".pytest_report.json"):
        (ROOT / f).unlink(missing_ok=True)
    print(json.dumps({"evidence_file": str(path.relative_to(ROOT)), "results": summary,
                      "inherent": f"{inherent['score']} {inherent['band']}",
                      "residual": f"{outcome['residual_if_tested']['score']} {outcome['residual_if_tested']['band']}",
                      "rationale": outcome["residual_if_tested"]["rationale"]}, indent=2))
    sys.exit(0 if all(v == "pass" for v in summary.values()) else 1)


if __name__ == "__main__":
    main()
