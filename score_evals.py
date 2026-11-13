"""Score recorded agent runs against deterministic expectations."""
import argparse
import json
from pathlib import Path


def reject_constant(value):
    raise ValueError(f"invalid JSON number {value}")


def load_json(path):
    return json.loads(path.read_text(encoding="utf-8"), parse_constant=reject_constant)


def index(document, label, *, allow_empty=False):
    if not isinstance(document, dict) or type(document.get("version")) is not int or document["version"] != 1:
        raise ValueError(f"{label}: expected a version 1 document")
    items = document.get(label)
    if not isinstance(items, list):
        raise ValueError(f"{label}: expected an array")
    if not items and not allow_empty:
        raise ValueError(f"{label}: expected a non-empty array")
    result = {}
    for item in items:
        case_id = item.get("id") if isinstance(item, dict) else None
        if not isinstance(case_id, str) or not case_id.strip() or case_id in result:
            raise ValueError(f"{label}: each id must be unique and non-empty")
        result[case_id] = item
    return result


def lookup(evidence, path):
    for key in path:
        if not isinstance(evidence, dict) or key not in evidence:
            raise KeyError(key)
        evidence = evidence[key]
    return evidence


def score(cases_document, runs_document):
    cases = index(cases_document, "cases")
    runs = index(runs_document, "runs", allow_empty=True)
    unexpected = runs.keys() - cases.keys()
    if unexpected:
        raise ValueError(f"unknown run IDs: {', '.join(sorted(unexpected))}")

    results = []
    counts = dict.fromkeys(("pass", "fail", "error"), 0)
    for case_id, case in cases.items():
        checks = case.get("checks")
        if not isinstance(checks, list) or not checks:
            raise ValueError(f"{case_id}: expected at least one check")

        run = runs.get(case_id)
        observed = run.get("observed") if run else None
        run_status = run.get("status") if run else None
        if run and run_status not in ("completed", "execution_error"):
            raise ValueError(f"{case_id}: status must be completed or execution_error")

        details = []
        for check in checks:
            path = check.get("path") if isinstance(check, dict) else None
            if (not isinstance(path, list) or not path
                    or any(not isinstance(key, str) or not key for key in path)
                    or "equals" not in check):
                raise ValueError(f"{case_id}: expected a path array and an equals value")

            expected = check["equals"]
            detail = {"path": path, "expected": expected}
            if run_status == "completed":
                try:
                    actual = lookup(observed, path)
                except KeyError:
                    detail.update(status="error", reason="missing evidence")
                else:
                    # JSON comparison keeps booleans distinct from numbers even in nested data.
                    equal = json.dumps(actual, sort_keys=True) == json.dumps(expected, sort_keys=True)
                    detail.update(status="pass" if equal else "fail", actual=actual)
            else:
                reason = "missing run" if run is None else "execution error"
                detail.update(status="error", reason=reason)
            details.append(detail)

        statuses = {detail["status"] for detail in details}
        status = "error" if "error" in statuses else "fail" if "fail" in statuses else "pass"
        counts[status] += 1
        results.append({"id": case_id, "status": status, "checks": details})

    return {"version": 1, "summary": counts, "cases": results}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("cases", type=Path)
    parser.add_argument("runs", type=Path)
    args = parser.parse_args()
    try:
        report = score(load_json(args.cases), load_json(args.runs))
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    print(json.dumps(report, indent=2))
    return 2 if report["summary"]["error"] else 1 if report["summary"]["fail"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
