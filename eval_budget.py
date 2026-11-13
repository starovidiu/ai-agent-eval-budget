"""Estimate recurring agent evaluation costs from a JSON scenario file."""
import argparse
import json
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path

MILLION = Decimal(1_000_000)
CENT = Decimal("0.01")


def number(values, key, default=None, *, integer=False, fraction=False):
    raw = values.get(key, default)
    if isinstance(raw, bool) or not isinstance(raw, (int, str, Decimal)):
        raise ValueError(f"{key} must be a number")
    try:
        value = Decimal(raw)
    except InvalidOperation as exc:
        raise ValueError(f"{key} must be a number") from exc
    if not value.is_finite() or value < 0:
        raise ValueError(f"{key} must be finite and nonnegative")
    if integer and value != value.to_integral_value():
        raise ValueError(f"{key} must be a whole number")
    if fraction and value > 1:
        raise ValueError(f"{key} must be between 0 and 1")
    return value


def model_cost(config, prefix):
    input_tokens = number(config, f"{prefix}_input_tokens")
    output_tokens = number(config, f"{prefix}_output_tokens")
    input_rate = number(config, f"{prefix}_input_usd_per_million")
    output_rate = number(config, f"{prefix}_output_usd_per_million")
    return (input_tokens * input_rate + output_tokens * output_rate) / MILLION


def estimate(config):
    tasks = number(config, "tasks", integer=True)
    trials_per_task = number(config, "trials_per_task", integer=True)
    calls = number(config, "agent_calls_per_trial")
    if not tasks or not trials_per_task:
        raise ValueError("tasks and trials_per_task must be positive")
    if "runs_per_year" in config:
        if "runs_per_month" in config:
            raise ValueError("specify runs_per_month or runs_per_year, not both")
        runs_per_year = number(config, "runs_per_year")
        return calculate(config, tasks * trials_per_task, calls, runs_per_year, Decimal(12))
    return calculate(config, tasks * trials_per_task, calls, number(config, "runs_per_month"), Decimal(1))


def calculate(config, trials, calls_per_trial, runs, months):
    judge_fraction = number(config, "judge_fraction", 0, fraction=True)
    retry_fraction = number(config, "retry_fraction", 0, fraction=True)
    agent = trials * calls_per_trial * model_cost(config, "agent")
    judge = trials * judge_fraction * model_cost(config, "judge") if judge_fraction else Decimal(0)
    retry = (agent + judge) * retry_fraction
    overhead = number(config, "other_usd_per_run", 0)
    total = agent + judge + retry + overhead
    return {
        "trials_per_run": int(trials),
        "agent_usd_per_run": agent,
        "judge_usd_per_run": judge,
        "retry_usd_per_run": retry,
        "other_usd_per_run": overhead,
        "total_usd_per_run": total,
        "total_usd_per_month": total * runs / months,
    }


def money(value):
    return str(value.quantize(CENT, rounding=ROUND_HALF_UP))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("config", type=Path)
    parser.add_argument("--json", action="store_true", help="emit machine-readable results")
    args = parser.parse_args()
    try:
        scenarios = json.loads(args.config.read_text(encoding="utf-8"), parse_float=Decimal)
        if not isinstance(scenarios, dict) or not scenarios:
            raise ValueError("expected a non-empty object of named scenarios")
        results = {}
        for name, config in scenarios.items():
            if not isinstance(config, dict):
                raise ValueError(f"{name}: expected an object")
            try:
                result = estimate(config)
            except (ValueError, InvalidOperation) as exc:
                raise ValueError(f"{name}: {exc}") from exc
            results[name] = {
                key: money(value) if isinstance(value, Decimal) else value
                for key, value in result.items()
            }
    except (OSError, ValueError, InvalidOperation) as exc:
        parser.error(str(exc))
    if args.json:
        print(json.dumps(results, indent=2))
    else:
        for name, row in results.items():
            print(f"{name}: ${row['total_usd_per_run']} per run | ${row['total_usd_per_month']} per month")
            print(f"  {row['trials_per_run']:,} base trials | agent ${row['agent_usd_per_run']} | "
                  f"judge ${row['judge_usd_per_run']} | retries ${row['retry_usd_per_run']} | "
                  f"other ${row['other_usd_per_run']}")


if __name__ == "__main__":
    main()
