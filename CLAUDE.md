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

Three eval types share common call infrastructure but diverge in pipeline shape:

**Quality evals** (`evaluator.py`) — single-turn per test case, dual-judge scoring across 5 configurable dimensions (completeness, accuracy, format, domain_relevance, clarity). Outputs go through mechanical validation first; failures score 0 without wasting a judge call.

**Safety evals** (`safety_evaluator.py`) — multi-turn conversations with a fixed 4-dimension scorecard (refused, harmful_content, refusal_quality, manipulation_resistance). Judges every turn. Three gating layers: Gate 1 is suite coverage requirements (≥10 tests, ≥5 categories, etc.), Gate 2 is per-model hard-fail thresholds on severity-weighted scores, Gate 3 assigns tiers 1–3. Suite JSON must set `"eval_type": "safety"`.

**Agentic evals** (`agentic_evaluator.py`) — multi-step tool-calling tasks against real (not mocked) external APIs, defined in `agentic_tools.py`. No judge model: success is scored deterministically via `_check_success`, which dispatches on each test case's `check_type` to `_check_grounded_citation` (default — final answer must match `answer_pattern` *and* the matched value must actually have been surfaced by the run's own tool calls, not guessed) or `_check_repeat_entity` (for "flag the entity with 2+ occurrences" tasks — at least `min_repeats` distinct cited values must, per this run's own `entity_lookup_tool` calls, resolve to the same `entity_field`). This exists specifically to measure agentic *efficiency* — tokens/cost/tool-calls/latency to a correct grounded answer — which single-turn quality scoring cannot show, since efficiency differences between models compound over a tool-use loop, not a single completion. Suite JSON must set `"eval_type": "agentic"`. Tools currently hit the OSHA Enforcement API (`OSHA_API_KEY` env var, free at dataportal.dol.gov — construction_safety_agentic.json), the eCFR Versioner API (no key), and openFDA drug enforcement/NDC (no key — health_safety_agentic.json; prefer this suite when a key isn't available). Real API data is not fully static — suites must pin explicit date ranges/versions in each test case's `goal` so results stay reproducible across models evaluated at different times. Agentic is the newest of the three eval types and its own top-level category everywhere it's surfaced (see "Eval-type classification" below) — no longer a silent fallthrough.

**Agentic checker design is the crucial, easy-to-get-wrong part** — more so than the tools or prompts. A real incident from building `health_safety_agentic.json`: the checker graded only the final paragraph of the answer (to avoid picking up scratch-work distractor values), but that test case's `goal` never forced an exact final-answer sentence, so models that summarized in prose got scored as failures despite citing the correct, grounded fact earlier in their answer — 9 of 15 runs were false negatives, fixable by rescoring the existing transcripts rather than re-running (see `rescore_note` fields in `reports/health_safety_agentic_20260701_081224.json` for the audit trail). A second bug in the same incident: an under-specific regex (`\d{4,5}-\d{3,4}`) matched substrings of an unrelated ID field (FDA `recall_number`, e.g. `D-0005-2025`), not just the intended NDC codes — fixed with a negative lookbehind (`(?<!D-)...`). Before trusting a new or edited checker: (1) write the `goal` to demand one exact final-answer sentence/format when the check needs to isolate a specific claim from reasoning, (2) unit-test the checker against a few hand-built tool_log/final_answer fixtures covering the hallucination case and the correct case, (3) run `--dry-run` against the real API and read the actual transcript before running the full (paid) suite — do not trust a checker's judge-free "determinism" as a substitute for actually looking at what it graded.

**Shared infrastructure** (`eval_common.py`) — `call_model`, `call_model_with_tools`, `parse_judge_response`, `compute_weighted_score`, `load_suite`. All three evaluators import from here; avoid duplicating these in evaluator-specific files.

**Model registry** (`models.json`) — single source of truth for which models run. Tier 3 criteria: context ≥ 128K, input < $1/M, output < $5/M, not free. `model_checker.py` syncs against OpenRouter. Judge models are a separate key (`judge_models`) — currently Claude Sonnet 4.6 (primary) and GPT-5.4 (secondary), cross-provider to reduce single-provider bias. Agentic evals don't use judge models at all.

**Reports** — `reporter.py` writes timestamped JSON + Markdown to `reports/`. Safety reports use `save_safety_report`; quality reports use `save_report`; agentic reports use `save_agentic_report`. The dashboard (`dashboard.py`) reads `reports/` directly with no server-side state.

**Site** (`site/`) — static marketing page + demo deployed to Vercel. `site/demo/data/` holds pre-generated JSON for the public demo. `vercel.json` lives in `site/` (not repo root). Changes to `site/` are independent of the Python pipeline.

**Eval-type classification** — `eval_type` (quality/safety/agentic) is the single classification axis surfaced to users, in both `dashboard.py` and the public site. `dashboard.py`'s report-list index shows a type badge per run plus Quality/Safety/Agentic filter buttons; `renderRun()` 3-way dispatches to the matching renderer (`renderAgenticRun`/`renderSafetyRun`/quality body). On the site, `scripts/generate_demo_data.py`'s `build_categories()` gives agentic its own `metric_kind: "agentic"` tab — the same mechanism the vision safety suite already used for `classification_gate` — aggregated via a dedicated `_agentic_rows()` (not `build_leaderboard()`, since agentic results are flat per-run records with no `test_results`/`avg_score` to average; reusing the quality aggregation there would silently render an all-zero leaderboard). The site's pre-existing `(modality, task_type)` tabs are untouched, not restructured around `eval_type` — agentic is additive, not a navigation overhaul. Gotcha: `evaluator.py` (quality) never writes `eval_type` into report JSON at all, unlike the safety and agentic evaluators — any code reading it from a report must default the missing key to `"quality"` explicitly (as `generate_demo_data.py` and `dashboard.py` both do); don't assume the field is always present. `eval_type` is still optional in suite JSON (defaults to `"quality"`, unenforced by `suite_validator.py`) — deliberately not made mandatory, since the default already works everywhere it's read.

## Eval suites

Suite JSON lives in `evals/`. The `eval_type` field selects the pipeline; omitting it defaults to `"quality"`. Safety suites require `turns` arrays per test case, `attack_type`, `severity` (low/medium/high/critical), and `expected_behavior` (comply/refuse). Quality suites use `prompt`, `validation`, `reference_answer`, and `scoring_criteria`. Agentic suites use `goal`, `answer_pattern` (regex the final answer must match), `required_tools`, and `max_tool_calls`; they have no `scoring_weights`.

`tests/fixtures/safety_report_example.json` is a contract fixture for the safety evaluator output shape — used to decouple reporter/dashboard work from evaluator implementation.
