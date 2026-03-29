# EvalPulse

Automated LLM evaluation pipeline. Discovers new models on OpenRouter, runs structured evaluations with dual-judge scoring, and generates comparison reports with a built-in dashboard.

Built for practitioners who need to answer: **which model works best for my actual production task?** Real prompts, real scoring, real tradeoffs.

## Quick start

```bash
# 1. Install
pip install -r requirements.txt

# 2. Configure
cp .env.example .env
# Add your OpenRouter API key: https://openrouter.ai

# 3. Create your evaluation suite
python evalpulse.py init

# 4. Validate it
python evalpulse.py --validate --suite your_domain

# 5. Test the pipeline (1 model, 1 test case, low cost)
python evalpulse.py --dry-run --suite your_domain

# 6. Run the full evaluation
python evalpulse.py --run-eval --suite your_domain

# 7. View results
python evalpulse.py --dashboard
```

Or try the included getting-started suite to verify everything works:

```bash
python evalpulse.py --dry-run --suite getting_started
```

## How it works

```
Create suite (init wizard or JSON)
  -> Validate suite structure
  -> Dry-run to verify pipeline
  -> Run evaluation against all enabled models (3 runs per test)
  -> Validate outputs mechanically before judging
  -> Score with dual LLM judges (cross-provider to reduce bias)
  -> Generate markdown + JSON comparison report
  -> View results in the built-in dashboard
```

## CLI reference

```bash
# Suite management
python evalpulse.py init                           # Interactive suite creator
python evalpulse.py --validate --suite my_suite    # Validate before running

# Evaluation
python evalpulse.py --dry-run --suite my_suite     # Quick pipeline test
python evalpulse.py --run-eval --suite my_suite    # Full evaluation
python evalpulse.py --run-eval --budget 5.00       # With cost limit
python evalpulse.py --full                         # Check models + evaluate + report
python evalpulse.py --full --auto-enable-new       # Auto-enable newly found models

# Model discovery
python evalpulse.py --check-models                 # Check OpenRouter for new models

# Dashboard
python evalpulse.py --dashboard                    # Start web UI
python evalpulse.py --dashboard --port 3000        # Custom port
python evalpulse.py --run-eval --dashboard         # Run then view
```

## Dashboard

The built-in dashboard provides three views:

**Run Index** — All evaluation runs listed with date, suite, model count, and top scores. Select multiple runs with checkboxes to compare.

**Run Detail** — Drill into a single run: model leaderboard with bar chart, dimension radar chart (completeness, accuracy, format, domain relevance, clarity), per-test-case breakdowns, and reliability analysis.

**Run Comparison** — Side-by-side comparison of selected runs with grouped bar charts and a delta table showing score regressions and improvements.

No external services required. Zero dependencies beyond Python stdlib.

## Project structure

```
├── evalpulse.py             # Run from project root
├── models.json              # Model registry (auto-updated)
├── evals/
│   ├── getting_started.json # Domain-neutral starter suite
│   └── suite.json           # Example: regulatory compliance suite
├── src/
│   ├── main.py              # CLI orchestrator
│   ├── init_wizard.py       # Interactive suite creator
│   ├── suite_validator.py   # Pre-flight suite validation
│   ├── evaluator.py         # Eval runner with dual-judge scoring
│   ├── model_checker.py     # OpenRouter model discovery + tier filtering
│   ├── reporter.py          # Markdown + JSON report generation
│   └── dashboard.py         # Built-in web dashboard (stdlib only)
├── reports/                 # Generated reports
├── .github/workflows/
│   └── eval.yml             # GitHub Actions automation
├── requirements.txt
└── .env.example
```

## Creating evaluation suites

### Interactive wizard

The fastest way to create a suite:

```bash
python evalpulse.py init
```

The wizard asks you for:
- Domain name and description
- Test cases: name, category, prompt, validation rules, reference answer
- Number of runs per test

It generates a valid JSON file in `evals/` and validates it automatically.

### Manual JSON

Create a JSON file in `evals/`:

```json
{
  "suite_name": "customer_support",
  "description": "Evaluates models on customer support response quality",
  "runs_per_test": 3,
  "scoring_weights": {
    "completeness": 0.30,
    "accuracy": 0.30,
    "format": 0.15,
    "domain_relevance": 0.15,
    "clarity": 0.10
  },
  "test_cases": [
    {
      "id": "tc_001",
      "name": "your_test",
      "category": "reasoning",
      "prompt": "Your actual production prompt here",
      "expected_format": "text",
      "validation": {
        "must_contain": ["required_term"],
        "min_length": 200
      },
      "reference_answer": "Description of what a good answer covers",
      "scoring_criteria": {
        "completeness": "What 'complete' means for your use case",
        "accuracy": "What 'accurate' means for your domain",
        "format": "Expected output structure",
        "domain_relevance": "What domain-specific knowledge is needed",
        "clarity": "What 'clear' means for your audience"
      }
    }
  ]
}
```

### Tips for writing good test cases

- Use your actual production prompts, not synthetic ones
- Include edge cases that have caused issues in production
- Set `must_contain` to terms that a correct answer absolutely requires
- Set `min_length` based on what a useful response looks like for your use case
- Write `scoring_criteria` descriptions specific to your domain — the judges use these to calibrate scores
- Adjust `scoring_weights` to emphasize what matters most (e.g., raise accuracy for medical/legal)
- Add a `description` field to your suite — it's used in the judge prompt for domain context
- Multiple suites can coexist in `evals/` for different use cases

## Evaluation pipeline

Each output goes through two stages:

**1. Mechanical validation** (before judging)
- Required terms present
- Minimum length met
- Minimum structured items
- Outputs that fail validation score 0 — no judge call wasted

**2. Dual-judge scoring** (cross-provider)
- Primary judge: Claude Sonnet 4.6
- Secondary judge: GPT-5.4
- Scores averaged across judges to reduce single-provider bias
- Each test repeated across configurable number of runs

Scoring dimensions (configurable per suite):
- **Completeness** (30%) — coverage of required content
- **Accuracy** (30%) — factual and reasoning correctness
- **Format** (15%) — structural match to expected output
- **Domain relevance** (15%) — specificity vs generic content
- **Clarity** (10%) — actionable for a non-expert

## Model selection

Models are filtered by tier criteria defined in `models.json`:

- Context window >= 128K tokens
- Input cost < $1.00 / million tokens
- Output cost < $5.00 / million tokens
- Not free-tier

New models are automatically discovered via `--check-models` and added to the registry when they match the criteria. Edit `models.json` to change tier thresholds.

## Automation (GitHub Actions)

The included workflow runs:

- **Weekly** (Monday 6am UTC)
- **On push** to `models.json` or `evals/`
- **Manual** from the Actions UI with mode, suite, budget, and auto-enable options

Add this secret to your GitHub repository:
- `OPENROUTER_API_KEY`

Reports are auto-committed to `reports/`.

## License

MIT
