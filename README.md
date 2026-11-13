# AI Agent Eval Budget

A dependency-free Python CLI for estimating what an agent evaluation suite costs to run. Companion to [AI Agent Evals Can Cost $16,000 a Month. Budget for Them.](https://medium.com/@tmucb.all/ai-agent-evals-can-cost-16-000-a-month-budget-for-them-57280cb6c3e3)

## Run the article example

Use Python 3.10 or newer. On Windows, use `py -3` in place of `python` if needed.

```bash
python eval_budget.py examples/article.json
python eval_budget.py examples/tiered.json --json
python -m unittest -v
```

The article's higher-priced judge scenario costs **$533.25 per run** and **$15,997.50 for 30 runs**. The 10% retry scenario comes to **$17,597.25**. The supplied token rates are illustrative inputs. Use your provider rates and measured token usage when budgeting.

## Model your suite

Copy an example JSON file and edit the named scenarios. Configure task count, trials per task, average calls per trial, average billable input/output tokens per call, and USD per million tokens. Set either `runs_per_month` or `runs_per_year`. The second option reports an average month over the year.

- `judge_fraction` is the share of trials that receive one model judgment. Set it to zero or omit it for deterministic checks. Judge token counts are per judgment.
- `retry_fraction` is the share of trials receiving one additional attempt at the average agent and judge cost. It models a single extra attempt, with the same judge coverage as the original trial.
- `other_usd_per_run` is an optional fixed estimate for costs such as sandboxes and human review. Include any expected retry-related overhead in that estimate.
- The CLI rounds displayed results to cents after calculating each total. A monthly total uses the unrounded per-run cost.

`examples/tiered.json` models pre-merge smoke tests, a smaller nightly suite with selective judging, and full pre-release runs. If these tiers all run in a month, add their monthly totals. The calculator runs offline and estimates costs from supplied assumptions. For mixed models or different cache rates, use separate scenarios for distinct work or fold measured rates into a token-weighted effective rate.

## What to evaluate

For a refund agent, check the ledger mechanically for exactly one refund with the right order and amount. Add a separate trace check for whether the agent promised a refund before verifying eligibility. The article explains when a model judge or human reviewer can add evidence that the ledger alone cannot provide.

## Score runs from an existing system

Keep the current application entry point. In staging or a test environment, invoke it from the integration test or script you already use. Export an observed result under each stable case ID and let the scorer compare it against versioned expectations. The scorer accepts JSON from any stack and runs locally without credentials.

```bash
python score_evals.py examples/refund-cases.json examples/refund-runs.json
```

This example intentionally returns one pass and one failure. The second case passes the ledger check but fails the trace check. The report includes the case ID, field path, expected value, actual value, and status. In CI, exit code 0 means all cases passed, 1 means a mismatch, and 2 means missing evidence, an execution error, or invalid input. Case results retain check-level details even when a case has both an error and a mismatch.

1. **Define expected behavior** in a version 1 cases file. Each case has a unique `id` and a `checks` array. Each check declares a nested object `path` and an exact JSON `equals` value. Types matter. Use integers for counts and currency minor units.
2. **Export observed evidence** in a version 1 runs file with the same case IDs. Use `status: "completed"` and put evidence under `observed`, or set `status: "execution_error"` when the application could not run. A required field that is unavailable should be omitted so the scorer reports missing evidence.
3. **Collect facts from the systems that own them.** For a travel planner, record how many stops violate the allowed-country constraint. For a marketplace, exercise hiring with an unverified operator and read the resulting hire count from the test database. For a refund flow, get the refund count and amount from the ledger. Use a trace field for a promise only if your system emits a structured event or a reviewer labels the trace. A missing signal is different from a false value.
4. **Start with a few release-blocking cases.** Use synthetic fixtures and sandbox side effects. Export only fields the checks need. Add the score command to CI once the evidence export is stable. Use the existing budget command to price the runs you schedule.

The runner scores one recorded result per case. If you repeat a case, use a separate runs file per trial or distinct case IDs per trial. Subjective outputs can be labeled upstream by a reviewer or calibrated judge. This CLI checks the supplied evidence and does not infer those labels.
