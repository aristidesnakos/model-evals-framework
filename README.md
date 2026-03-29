# EvalPulse

Automated LLM evaluation pipeline. Discovers new models on OpenRouter, runs structured evaluations with dual-judge scoring, and generates comparison reports with a built-in dashboard.

Built for practitioners who need to answer: **which model works best for my actual production task?** Real prompts, real scoring, real tradeoffs.

## How it works

```
Cron / push / manual trigger
  -> Check OpenRouter for new models matching tier criteria
  -> Compare against models.json registry
  -> Run evaluation suite against enabled models (3 runs per test)
  -> Validate outputs mechanically before judging
  -> Score with dual LLM judges (cross-provider to reduce bias)
  -> Generate markdown + JSON comparison report
  -> View results in the built-in dashboard
```

## Quick start

### 1. Install

```bash
pip install -r requirements.txt
```

### 2. Configure

```bash
cp .env.example .env
# Add your OpenRouter API key: https://openrouter.ai
```

### 3. Run

```bash
cd src

# Full pipeline: check models + evaluate + report
python main.py --full

# Just check for new models
python main.py --check-models

# Just run evaluation
python main.py --run-eval

# Auto-enable newly detected models
python main.py --full --auto-enable-new

# Use a specific evaluation suite
python main.py --run-eval --suite your_domain

# Set a budget limit (USD)
python main.py --run-eval --budget 5.00
```

### 4. View results

```bash
# Start the dashboard
python main.py --dashboard

# Custom port
python main.py --dashboard --port 3000

# Run eval then immediately open dashboard
python main.py --run-eval --dashboard
```

The dashboard runs locally at `http://127.0.0.1:8080` and auto-opens your browser.

## Dashboard

The built-in dashboard provides three views:

**Run Index** — All evaluation runs listed with date, suite, model count, and top scores. Select multiple runs with checkboxes to compare.

**Run Detail** — Drill into a single run: model leaderboard with bar chart, dimension radar chart (completeness, accuracy, format, domain relevance, clarity), per-test-case breakdowns, and reliability analysis.

**Run Comparison** — Side-by-side comparison of selected runs with grouped bar charts and a delta table showing score regressions and improvements.

No external services required. Zero dependencies beyond Python stdlib.

## Project structure

```
├── models.json              # Model registry (auto-updated)
├── evals/
│   └── suite.json           # Evaluation test cases and scoring criteria
├── src/
│   ├── main.py              # CLI orchestrator
│   ├── model_checker.py     # OpenRouter model discovery + tier filtering
│   ├── evaluator.py         # Eval runner with dual-judge scoring
│   ├── reporter.py          # Markdown + JSON report generation
│   └── dashboard.py         # Built-in web dashboard (stdlib only)
├── reports/                 # Generated reports (auto-committed)
├── .github/workflows/
│   └── eval.yml             # GitHub Actions automation
├── requirements.txt
└── .env.example
```

## Model selection

Models are filtered by tier criteria defined in `models.json`:

- Context window >= 128K tokens
- Input cost < $1.00 / million tokens
- Output cost < $5.00 / million tokens
- Not free-tier

New models are automatically discovered via `--check-models` and added to the registry when they match the criteria.

## Evaluation suite

The default suite (`evals/suite.json`) evaluates models on regulatory compliance document generation. Each output goes through two stages:

**1. Mechanical validation** (before judging)
- Required terms present
- Minimum length met
- Minimum structured items (hazards, gaps, steps)
- Outputs that fail validation score 0 — no judge call wasted

**2. Dual-judge scoring** (cross-provider)
- Primary judge: Claude Sonnet 4.6
- Secondary judge: GPT-5.4
- Scores averaged across judges to reduce single-provider bias
- Each test repeated 3 times for statistical reliability

Scoring dimensions (configurable per suite):
- **Completeness** (30%) — coverage of required content
- **Accuracy** (30%) — factual and reasoning correctness
- **Format** (15%) — structural match to expected output
- **Domain relevance** (15%) — specificity vs generic content
- **Clarity** (10%) — actionable for a non-expert

### Custom suites

Create a new JSON file in `evals/`:

```json
{
  "suite_name": "your_domain",
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
      "prompt": "Your production prompt here",
      "expected_format": "json",
      "validation": {
        "must_contain": ["required_term"],
        "min_length": 500
      },
      "reference_answer": "What a good answer should cover",
      "scoring_criteria": {
        "accuracy": "What 'accurate' means for your domain",
        "completeness": "What 'complete' means for your use case"
      }
    }
  ]
}
```

Run with: `python main.py --run-eval --suite your_domain`

## Automation (GitHub Actions)

The included workflow runs:

- **Weekly** (Monday 6am UTC)
- **On push** to `models.json` or `evals/`
- **Manual** from the Actions UI with mode, suite, budget, and auto-enable options

Add this secret to your GitHub repository:
- `OPENROUTER_API_KEY`

Reports are auto-committed to `reports/`.

## Reports

Generated reports include:
- **Summary table** — all models ranked by weighted score
- **Per-test-case breakdown** — dimension scores per model per test
- **Reliability analysis** — standard deviation across runs
- **Raw JSON** — structured results for programmatic analysis

## License

MIT
