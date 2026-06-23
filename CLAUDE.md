# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Setup
pip install -r requirements.txt
cp .env.example .env   # add OPENROUTER_API_KEY

# Suite lifecycle
python evalpulse.py init                          # interactive suite creator
python evalpulse.py --validate --suite <name>     # pre-flight JSON validation
python evalpulse.py --dry-run --suite <name>      # 1 model × 1 test case (cheap)
python evalpulse.py --run-eval --suite <name>     # full run
python evalpulse.py --run-eval --budget 5.00      # with cost cap

# Model registry
python evalpulse.py --check-models                # sync OpenRouter → models.json
python evalpulse.py --full --auto-enable-new      # discover + eval in one shot

# Dashboard (stdlib HTTP server, no external deps)
python evalpulse.py --dashboard
python evalpulse.py --run-eval --dashboard        # eval then open dashboard
```

All commands run from the repo root via `evalpulse.py`, which imports from `src/`.

## Architecture

Two eval types share a common call/judge harness but diverge in pipeline shape:

**Quality evals** (`evaluator.py`) — single-turn per test case, dual-judge scoring across 5 configurable dimensions (completeness, accuracy, format, domain_relevance, clarity). Outputs go through mechanical validation first; failures score 0 without wasting a judge call.

**Safety evals** (`safety_evaluator.py`) — multi-turn conversations with a fixed 4-dimension scorecard (refused, harmful_content, refusal_quality, manipulation_resistance). Judges every turn. Three gating layers: Gate 1 is suite coverage requirements (≥10 tests, ≥5 categories, etc.), Gate 2 is per-model hard-fail thresholds on severity-weighted scores, Gate 3 assigns tiers 1–3. Suite JSON must set `"eval_type": "safety"`.

**Shared infrastructure** (`eval_common.py`) — `call_model`, `parse_judge_response`, `compute_weighted_score`, `load_suite`. Both evaluators import from here; avoid duplicating these in evaluator-specific files.

**Model registry** (`models.json`) — single source of truth for which models run. Tier 3 criteria: context ≥ 128K, input < $1/M, output < $5/M, not free. `model_checker.py` syncs against OpenRouter. Judge models are a separate key (`judge_models`) — currently Claude Sonnet 4.6 (primary) and GPT-5.4 (secondary), cross-provider to reduce single-provider bias.

**Reports** — `reporter.py` writes timestamped JSON + Markdown to `reports/`. Safety reports use `save_safety_report`; quality reports use `save_report`. The dashboard (`dashboard.py`) reads `reports/` directly with no server-side state.

**Site** (`site/`) — static marketing page + demo deployed to Vercel. `site/demo/data/` holds pre-generated JSON for the public demo. `vercel.json` lives in `site/` (not repo root). Changes to `site/` are independent of the Python pipeline.

## Eval suites

Suite JSON lives in `evals/`. The `eval_type` field selects the pipeline; omitting it defaults to `"quality"`. Safety suites require `turns` arrays per test case, `attack_type`, `severity` (low/medium/high/critical), and `expected_behavior` (comply/refuse). Quality suites use `prompt`, `validation`, `reference_answer`, and `scoring_criteria`.

`tests/fixtures/safety_report_example.json` is a contract fixture for the safety evaluator output shape — used to decouple reporter/dashboard work from evaluator implementation.
