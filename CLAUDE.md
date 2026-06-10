# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

EvalPulse — an LLM evaluation pipeline. It discovers cheap/fast models on OpenRouter, runs structured evals against them, scores outputs with two cross-provider LLM judges, and emits markdown + JSON reports browsable in a built-in dashboard. All model calls (including judges) go through OpenRouter via the OpenAI SDK.

## Running it

Everything is driven through `evalpulse.py` at the repo root — **always run from the project root**, not from `src/`:

```bash
python evalpulse.py init                            # interactive suite creator
python evalpulse.py --validate --suite <name>       # validate suite JSON (no API key needed)
python evalpulse.py --dry-run --suite <name>        # 1 model × 1 test case, verifies pipeline + prints cost estimate
python evalpulse.py --run-eval --suite <name>       # full run
python evalpulse.py --run-eval --budget 5.00        # abort if estimated cost exceeds budget
python evalpulse.py --full --auto-enable-new        # check models + eval + report
python evalpulse.py --dashboard [--port 8080]       # browse reports/ in a web UI
```

`--suite` defaults to `suite` (→ `evals/suite.json`, the `regulatory_compliance` example). A missing suite falls back to `suite.json` with a warning. There is no `.env.example` despite the README — copy/create `.env` at the repo root with `OPENROUTER_API_KEY=...` (loaded relative to `src/main.py`'s parent.parent).

Dependencies: `pip install -r requirements.txt` (just `openai`, `python-dotenv`, `httpx`). No linter, formatter, or test runner is configured; `tests/` holds only a fixture. The GitHub Actions workflow (`.github/workflows/eval.yml`) runs `cd src && python main.py ...` weekly / on push to `models.json` or `evals/`, and auto-commits results to `reports/`.

## Import convention (important)

Modules under `src/` import each other by **bare module name** (`from evaluator import ...`, not `from src.evaluator import ...`). This works because `evalpulse.py` inserts `src/` onto `sys.path` before importing `main`. Keep this convention — do not introduce `src.`-prefixed imports, and do not run modules from inside `src/` except via the path the workflow uses.

## Architecture

### Two parallel eval pipelines, dispatched on `eval_type`

Every suite is a JSON file in `evals/`. `suite["eval_type"]` (default `"quality"`) selects which runner `main.py` invokes:

- **`quality`** → `evaluator.py::run_evaluation`. Single-turn. Each test case runs `runs_per_test` times (default 3) per enabled model. Flow per output: mechanical `validate_output` (must_contain / min_length / min item count) → **fail validation scores 0, no judge called** → dual-judge scoring → average across judges → weighted score over 5 dimensions (completeness, accuracy, format, domain_relevance, clarity).
- **`safety`** → `safety_evaluator.py::run_safety_evaluation`. Multi-turn red-teaming. Runs every turn of a conversation, judges *each* turn in accumulated context, uses 4 fixed dimensions (refused, harmful_content, refusal_quality, manipulation_resistance), applies a severity deficit multiplier to the final-turn score, and produces a `gate_result` block. Design doc: `docs/eval-suites/2026-04-22-jailbreak-safety.md`.

`eval_common.py` holds what both share: `call_model` (the single OpenRouter entry point — takes a full messages list, optionally rewrites the last user turn into multimodal content-parts when given an `image_path`), `load_suite`, `parse_judge_response` (tolerant JSON extraction), `compute_weighted_score`. `evaluator.py` re-exports several of these for backward compatibility — prefer importing from `eval_common`.

### Dual-judge scoring

Judges are defined in `models.json` under `judge_models`: primary `anthropic/claude-sonnet-4.6`, secondary `openai/gpt-5.4`. Scores are averaged across both to reduce single-provider bias. Judges return strict JSON; `parse_judge_response` recovers it from raw text or fenced blocks.

### Safety gates (safety_evaluator.py)

Three gates, all thresholds are module-level constants at the top of the file:
- **Gate 1** — suite coverage (min tests/categories/attack types/over-refusal/high-severity/multi-turn). Hard-fails the run *unless* the suite sets `"probe": true`, in which case it's advisory (probe suites verify the pipeline, don't claim deployment-grade coverage).
- **Gate 2** — per-model hard-fail / review (critical-severity compliance, harmful-content leaks, category floors, over-refusal ceiling).
- **Gate 3** — assigns a deploy tier 1–4 from the severity-weighted aggregate score.

For `expected_behavior: "comply"` test cases (over-refusal probes), the judge scores `correctly_complied` instead of `refused`; `parse_safety_score` renames it back so the rest of the pipeline sees one schema.

The safety **markdown reporter is not implemented** (Phase 4a). Safety runs save raw JSON to `reports/` and print a gate summary to stdout.

### Image-safety is binary classification, scored out-of-band

`image_safety` is a `quality`-type suite (vision), so the standard pipeline only scores *generation quality* 1–10. The metric that matters — whether an unsafe image is wrongly passed — is a confusion matrix, produced by a **separate post-process step**: `scripts/score_image_safety.py <report.json>`. It joins each test case to ground-truth labels in `evals/image_safety_labels.json` and reports unsafe-pass-rate vs good-reject-rate. Treats refusals/malformed output as "block" (safe default).

Unsafe/explicit imagery is **never committed**: `.gitignore` excludes `evals/assets/**/private/` and `reports/image_safety_*.{json,md}`. Real unsafe-labeled images live untracked under `evals/assets/image_safety/private/`. See `evals/assets/image_safety/README.md`.

### Other scorers

`color_scoring.py` does deterministic CIEDE2000 palette matching (stdlib-only sRGB→Lab) for the `color_palette` suite — runs *before* the judge and its result is injected into the judge prompt. A test case opts in via `expected_colors`.

### Model registry & discovery

`models.json` is the registry: `metadata.tier_criteria` defines the "Tier 3" filter (context ≥128K, input <$1/M, output <$5/M, non-free). `model_checker.py::check_for_new_models` diffs OpenRouter's catalog against the registry; `--auto-enable-new` enables matches automatically. Only models with `"enabled": true` are evaluated. `"vision": true` gates vision test cases — a vision test case is skipped (scored as skipped, not 0) for non-vision models.

### Dashboard & static site

`dashboard.py` is a stdlib-only single-file SPA + tiny REST API over `reports/*.json`. Separately, `site/` is a static Vercel-hosted demo (`site/index.html` landing, `site/demo/` dashboard); its data under `site/demo/data/` is generated by `scripts/generate_demo_data.py` (deterministic/seeded, or `--from-reports` to use real runs).

## Suite authoring

Validate before running: `python evalpulse.py --validate --suite <name>`. `suite_validator.py` enforces structure and, for `eval_type: safety`, constrains `category` / `attack_type` / `severity` / `expected_behavior` to fixed vocabularies and mirrors the Gate-1 minimums. Quality-suite fields and examples are documented in `README.md`.
