import json
import subprocess
import sys
import unittest
from decimal import Decimal
from pathlib import Path

from eval_budget import estimate


ROOT = Path(__file__).resolve().parent
EXAMPLE = ROOT / "examples" / "article.json"


class BudgetTests(unittest.TestCase):
    def test_article_totals_through_cli(self):
        output = subprocess.check_output(
            [sys.executable, str(ROOT / "eval_budget.py"), str(EXAMPLE), "--json"],
            text=True,
        )
        rows = json.loads(output)
        expected = {
            "weekly-standard-judge": ("344.25", "1491.75"),
            "weekly-higher-priced-judge": ("533.25", "2310.75"),
            "nightly-30-runs": ("533.25", "15997.50"),
            "nightly-with-retries": ("586.58", "17597.25"),
            "nightly-1200-tasks-with-retries": ("1407.78", "42233.40"),
        }
        self.assertEqual({
            name: (row["total_usd_per_run"], row["total_usd_per_month"])
            for name, row in rows.items()
        }, expected)

    def test_partial_judging_and_fixed_overhead(self):
        config = json.loads(EXAMPLE.read_text(), parse_float=Decimal)["nightly-30-runs"]
        row = estimate(dict(config, judge_fraction="0.5", other_usd_per_run=10))
        self.assertEqual(row["judge_usd_per_run"], Decimal("118.125"))
        self.assertEqual(row["total_usd_per_month"], Decimal("12753.75"))

    def test_judge_disabled_requires_no_judge_configuration(self):
        config = json.loads(EXAMPLE.read_text())["nightly-30-runs"]
        config = {key: value for key, value in config.items() if not key.startswith("judge")}
        self.assertEqual(estimate(config)["total_usd_per_run"], Decimal(297))

    def test_invalid_retry_fraction(self):
        config = json.loads(EXAMPLE.read_text())["nightly-30-runs"]
        with self.assertRaisesRegex(ValueError, "retry_fraction"):
            estimate(dict(config, retry_fraction="1.1"))


if __name__ == "__main__":
    unittest.main()
