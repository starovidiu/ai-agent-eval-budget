import copy
import json
import subprocess
import sys
import unittest
from pathlib import Path

from score_evals import load_json, score


ROOT = Path(__file__).resolve().parent
CASES = ROOT / "examples" / "refund-cases.json"
RUNS = ROOT / "examples" / "refund-runs.json"


class ScoreTests(unittest.TestCase):
    def setUp(self):
        self.cases = load_json(CASES)
        self.runs = load_json(RUNS)

    def test_demo_failure_explains_which_check_failed(self):
        result = subprocess.run(
            [sys.executable, str(ROOT / "score_evals.py"), str(CASES), str(RUNS)],
            capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 1)
        report = json.loads(result.stdout)
        self.assertEqual(report["summary"], {"pass": 1, "fail": 1, "error": 0})
        self.assertEqual(report["cases"][1]["checks"][1], {
            "path": ["trace", "promised_refund_before_eligibility"],
            "expected": False,
            "actual": True,
            "status": "fail",
        })

    def test_fixing_evidence_passes_both_cases(self):
        self.runs["runs"][1]["observed"]["trace"]["promised_refund_before_eligibility"] = False
        self.assertEqual(score(self.cases, self.runs)["summary"], {"pass": 2, "fail": 0, "error": 0})

    def test_missing_run_or_field_is_error(self):
        self.runs["runs"].pop()
        del self.runs["runs"][0]["observed"]["ledger"]["refund_count"]
        result = score(self.cases, self.runs)
        self.assertEqual(result["summary"]["error"], 2)
        self.assertEqual(result["cases"][0]["checks"][0]["reason"], "missing evidence")
        self.assertEqual(result["cases"][1]["checks"][0]["reason"], "missing run")

    def test_empty_run_export_reports_every_case_missing(self):
        self.runs["runs"] = []
        self.assertEqual(score(self.cases, self.runs)["summary"]["error"], 2)

    def test_execution_failure_is_error(self):
        self.runs["runs"][0]["status"] = "execution_error"
        result = score(self.cases, self.runs)
        self.assertEqual(result["cases"][0]["checks"][0]["reason"], "execution error")

    def test_rejects_duplicate_and_unknown_runs(self):
        runs = copy.deepcopy(self.runs)
        runs["runs"].append(runs["runs"][0])
        with self.assertRaisesRegex(ValueError, "unique"):
            score(self.cases, runs)
        runs["runs"].pop()
        runs["runs"][0]["id"] = "typo"
        with self.assertRaisesRegex(ValueError, "unknown run IDs"):
            score(self.cases, runs)
