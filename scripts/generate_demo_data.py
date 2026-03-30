"""
Generate demo evaluation data for the EvalPulse static demo site.

Produces two realistic report JSONs and an index.json manifest in site/demo/data/.
Scores are seeded/deterministic so the output is reproducible.

Usage:
    python scripts/generate_demo_data.py
    python scripts/generate_demo_data.py --from-reports   # use real reports if available
"""

import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
OUT_DIR = ROOT / "site" / "demo" / "data"


def weighted_score(scores: dict, weights: dict) -> float:
    total = sum(scores[d] * weights.get(d, 0) for d in scores)
    return round(total, 2)


def generate_report(suite_path: Path, run_id: str, model_list: list, seed: int) -> dict:
    rng = random.Random(seed)
    suite = json.loads(suite_path.read_text())
    runs_per_test = suite.get("runs_per_test", 1)
    weights = suite.get("scoring_weights", {
        "completeness": 0.30, "accuracy": 0.30, "format": 0.15,
        "domain_relevance": 0.15, "clarity": 0.10
    })
    dims = list(weights.keys())

    # Per-model bias: higher-tier models score slightly better
    model_biases = {
        "openai/gpt-5.4-mini":                   0.7,
        "google/gemini-3.1-flash-lite-preview":   0.2,
        "qwen/qwen3.5-plus-02-15":                0.4,
        "mistralai/mistral-small-2603":           0.0,
        "openai/gpt-5.4-nano":                    0.5,
        "qwen/qwen3.5-flash-02-23":              -0.1,
    }

    results = []
    for model in model_list:
        bias = model_biases.get(model["id"], 0.0)
        test_results = []
        for tc in suite["test_cases"]:
            runs = []
            for run_idx in range(runs_per_test):
                scores = {}
                for d in dims:
                    base = rng.uniform(5.5, 8.5) + bias
                    scores[d] = round(min(10.0, max(1.0, base + rng.uniform(-0.5, 0.5))), 1)
                ws = weighted_score(scores, weights)
                latency = round(rng.uniform(0.6, 3.8), 2)
                inp_tokens = rng.randint(350, 700)
                out_tokens = rng.randint(180, 600)
                runs.append({
                    "run": run_idx,
                    "error": None,
                    "latency": latency,
                    "tokens": {"input": inp_tokens, "output": out_tokens},
                    "scores": scores,
                    "weighted_score": ws,
                    "validation": {"passed": True, "failures": []},
                })

            score_values = [r["weighted_score"] for r in runs]
            avg = round(sum(score_values) / len(score_values), 2)
            variance = sum((s - avg) ** 2 for s in score_values) / len(score_values) if len(score_values) > 1 else 0
            std_dev = round(variance ** 0.5, 2)

            test_results.append({
                "test_case_id": tc["id"],
                "test_case_name": tc["name"],
                "category": tc["category"],
                "runs": runs,
                "avg_score": avg,
                "std_dev": std_dev,
                "min_score": round(min(score_values), 2),
                "max_score": round(max(score_values), 2),
            })

        results.append({
            "model_id": model["id"],
            "model_name": model["name"],
            "test_results": test_results,
            "errors": 0,
        })

    return {
        "run_id": run_id,
        "suite_name": suite["suite_name"],
        "runs_per_test": runs_per_test,
        "judge_models": ["anthropic/claude-sonnet-4.6", "openai/gpt-5.4"],
        "results": results,
    }


def build_index(reports: list[tuple[str, dict]]) -> list:
    index = []
    for filename, data in reports:
        model_scores = []
        for r in data.get("results", []):
            scores = [tr["avg_score"] for tr in r.get("test_results", []) if tr["avg_score"] > 0]
            if scores:
                model_scores.append({
                    "name": r["model_name"],
                    "avg": round(sum(scores) / len(scores), 1)
                })
        model_scores.sort(key=lambda x: x["avg"], reverse=True)
        index.append({
            "filename": filename,
            "run_id": data.get("run_id", ""),
            "suite_name": data.get("suite_name", ""),
            "model_count": len(data.get("results", [])),
            "top_model": model_scores[0] if model_scores else None,
            "score_range": [model_scores[-1]["avg"], model_scores[0]["avg"]] if model_scores else [0, 0],
        })
    return index


def from_real_reports(reports_dir: Path) -> bool:
    files = sorted(reports_dir.glob("*.json"), reverse=True)
    if not files:
        return False

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    pairs = []
    for f in files[:4]:  # cap at 4 reports for the demo
        data = json.loads(f.read_text())
        dest = OUT_DIR / f.name
        dest.write_text(json.dumps(data, indent=2))
        pairs.append((f.name, data))
        print(f"  Copied {f.name}")

    index = build_index(pairs)
    (OUT_DIR / "index.json").write_text(json.dumps(index, indent=2))
    print(f"  Wrote index.json ({len(index)} entries)")
    return True


def main():
    use_real = "--from-reports" in sys.argv

    if use_real:
        real_dir = ROOT / "reports"
        print("Looking for real reports in reports/...")
        if from_real_reports(real_dir):
            print("Done. Used real reports.")
            return
        print("No real reports found, falling back to generated data.")

    models_data = json.loads((ROOT / "models.json").read_text())
    models = [m for m in models_data["models"] if m.get("enabled", True)]

    suites = [
        (ROOT / "evals" / "getting_started.json", "20260330_120000", 42),
        (ROOT / "evals" / "suite.json",            "20260315_090000", 99),
    ]

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    pairs = []
    for suite_path, run_id, seed in suites:
        report = generate_report(suite_path, run_id, models, seed)
        suite_name = report["suite_name"]
        filename = f"{suite_name}_{run_id}.json"
        dest = OUT_DIR / filename
        dest.write_text(json.dumps(report, indent=2))
        pairs.append((filename, report))
        print(f"  Wrote {filename}")

    # index.json sorted newest first (matches dashboard expectation)
    pairs_sorted = list(reversed(pairs))
    index = build_index(pairs_sorted)
    (OUT_DIR / "index.json").write_text(json.dumps(index, indent=2))
    print(f"  Wrote index.json ({len(index)} entries)")
    print(f"\nDemo data ready in {OUT_DIR.relative_to(ROOT)}/")


if __name__ == "__main__":
    main()
