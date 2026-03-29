"""
Runs evaluation suite against enabled models.
Scores with dual LLM judges via OpenRouter.
"""

import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path

from openai import OpenAI

EVALS_DIR = Path(__file__).parent.parent / "evals"
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"


def load_suite(suite_name: str) -> dict:
    suite_file = EVALS_DIR / f"{suite_name}.json"
    if not suite_file.exists():
        fallback = EVALS_DIR / "suite.json"
        if fallback.exists():
            print(f"Warning: Suite '{suite_name}' not found, falling back to suite.json")
            suite_file = fallback
        else:
            raise FileNotFoundError(f"No evaluation suite found: tried {suite_file} and {fallback}")
    with open(suite_file) as f:
        return json.load(f)


def validate_output(output: str, validation: dict) -> dict:
    """Run mechanical validation checks before sending to judge."""
    failures = []

    if "must_contain" in validation:
        for term in validation["must_contain"]:
            if term.lower() not in output.lower():
                failures.append(f"Missing required term: '{term}'")

    if "min_length" in validation:
        if len(output) < validation["min_length"]:
            failures.append(
                f"Output too short: {len(output)} chars < {validation['min_length']} required"
            )

    if "min_hazards" in validation or "min_gaps" in validation:
        # Count numbered items or bullet points as a rough proxy
        items = re.findall(r"(?:^|\n)\s*(?:\d+[.)]|\-|\*)\s+", output)
        min_items = validation.get("min_hazards") or validation.get("min_gaps", 0)
        if len(items) < min_items:
            failures.append(
                f"Found {len(items)} structured items, expected at least {min_items}"
            )

    return {
        "passed": len(failures) == 0,
        "failures": failures,
    }


def build_judge_prompt(test_case: dict, model_output: str, suite_description: str = "") -> str:
    """Build the scoring prompt for the LLM judge."""
    criteria = test_case["scoring_criteria"]
    reference = test_case.get("reference_answer", "No reference provided.")

    preamble = "You are an expert evaluator."
    if suite_description:
        preamble += f" Context: {suite_description}"

    return f"""{preamble}

Score the following model output against the criteria below. Be strict and specific.

## Test Case
**Name:** {test_case["name"]}
**Category:** {test_case["category"]}
**Prompt given to model:** {test_case["prompt"]}

## Reference Answer (what a good response should cover)
{reference}

## Model Output
{model_output}

## Scoring Criteria
Score each dimension from 1-10:

- **Completeness** (weight: 30%): {criteria.get("completeness", "N/A")}
- **Accuracy** (weight: 30%): {criteria.get("accuracy", "N/A")}
- **Format** (weight: 15%): {criteria.get("format", "N/A")}
- **Domain Relevance** (weight: 15%): {criteria.get("domain_relevance", "N/A")}
- **Clarity** (weight: 10%): {criteria.get("clarity", "N/A")}

Respond in exactly this JSON format (no other text):
{{
  "completeness": <1-10>,
  "accuracy": <1-10>,
  "format": <1-10>,
  "domain_relevance": <1-10>,
  "clarity": <1-10>,
  "reasoning": "<brief explanation of scores>"
}}"""


def parse_judge_response(response_text: str) -> dict | None:
    """Extract JSON scores from judge response."""
    # Try direct JSON parse
    try:
        return json.loads(response_text)
    except json.JSONDecodeError:
        pass

    # Try extracting JSON block from markdown
    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", response_text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass

    # Try finding first { to last }
    start = response_text.find("{")
    end = response_text.rfind("}")
    if start != -1 and end != -1:
        try:
            return json.loads(response_text[start : end + 1])
        except json.JSONDecodeError:
            pass

    return None


def compute_weighted_score(scores: dict, weights: dict) -> float:
    """Compute weighted average from dimension scores."""
    total = 0.0
    for dim, weight in weights.items():
        total += scores.get(dim, 0) * weight
    return round(total, 2)


def call_model(client: OpenAI, model_id: str, prompt: str) -> dict:
    """Call a model via OpenRouter."""
    start = time.time()
    try:
        response = client.chat.completions.create(
            model=model_id,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=4096,
        )
        latency = time.time() - start
        output = response.choices[0].message.content or ""
        usage = response.usage

        return {
            "output": output,
            "latency": round(latency, 2),
            "tokens": {
                "input": usage.prompt_tokens if usage else 0,
                "output": usage.completion_tokens if usage else 0,
            },
            "error": None,
        }
    except Exception as e:
        latency = time.time() - start
        return {
            "output": "",
            "latency": round(latency, 2),
            "tokens": {"input": 0, "output": 0},
            "error": str(e),
        }


def judge_output(
    client: OpenAI,
    judge_model: str,
    test_case: dict,
    model_output: str,
    suite_description: str = "",
) -> dict:
    """Score a model output using an LLM judge."""
    prompt = build_judge_prompt(test_case, model_output, suite_description)
    result = call_model(client, judge_model, prompt)

    if result["error"]:
        return {"scores": None, "error": result["error"], "raw": ""}

    parsed = parse_judge_response(result["output"])
    if not parsed:
        return {"scores": None, "error": "Failed to parse judge response", "raw": result["output"]}

    return {"scores": parsed, "error": None, "raw": result["output"]}


def run_evaluation(
    api_key: str,
    models: list[dict],
    judge_models: list[dict],
    suite_name: str = "suite",
    budget: float | None = None,
) -> dict:
    """
    Run the full evaluation pipeline.

    Returns structured results for the reporter.
    """
    suite = load_suite(suite_name)
    weights = suite["scoring_weights"]
    runs_per_test = suite.get("runs_per_test", 3)
    test_cases = suite["test_cases"]
    suite_description = suite.get("description", "")

    client = OpenAI(base_url=OPENROUTER_BASE_URL, api_key=api_key)

    enabled_models = [m for m in models if m.get("enabled")]
    if not enabled_models:
        return {"error": "No enabled models to evaluate", "results": []}

    # Cost estimation
    estimated_calls = len(enabled_models) * len(test_cases) * runs_per_test
    judge_calls = estimated_calls * len(judge_models)
    total_calls = estimated_calls + judge_calls
    print(f"Evaluation plan: {estimated_calls} model calls + {judge_calls} judge calls = {total_calls} total API calls")

    if budget is not None:
        # Rough estimate: assume avg 2K tokens per call, use max model pricing
        max_output_cost = max(m["pricing"]["output_per_million"] for m in enabled_models)
        est_cost = (total_calls * 2000 * max_output_cost) / 1_000_000
        if est_cost > budget:
            return {
                "error": f"Estimated cost ${est_cost:.2f} exceeds budget ${budget:.2f}",
                "results": [],
            }
        print(f"Estimated cost: ~${est_cost:.2f} (budget: ${budget:.2f})")

    run_id = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    results = []

    for model in enabled_models:
        model_id = model["id"]
        print(f"\nEvaluating: {model_id}")
        model_results = {
            "model_id": model_id,
            "model_name": model.get("name", model_id),
            "test_results": [],
            "errors": 0,
        }

        for tc in test_cases:
            tc_runs = []

            for run_idx in range(runs_per_test):
                # Call the model
                result = call_model(client, model_id, tc["prompt"])

                if result["error"]:
                    model_results["errors"] += 1
                    tc_runs.append({
                        "run": run_idx,
                        "error": result["error"],
                        "latency": result["latency"],
                        "scores": None,
                        "weighted_score": 0,
                        "validation": {"passed": False, "failures": ["Model call failed"]},
                    })
                    continue

                # Validate output
                validation = validate_output(
                    result["output"], tc.get("validation", {})
                )

                if not validation["passed"]:
                    tc_runs.append({
                        "run": run_idx,
                        "error": None,
                        "latency": result["latency"],
                        "tokens": result["tokens"],
                        "scores": None,
                        "weighted_score": 0,
                        "validation": validation,
                    })
                    continue

                # Judge with dual judges and average
                all_judge_scores = []
                for jm in judge_models:
                    judge_result = judge_output(
                        client, jm["id"], tc, result["output"],
                        suite_description=suite_description,
                    )
                    if judge_result["scores"]:
                        all_judge_scores.append(judge_result["scores"])

                if not all_judge_scores:
                    tc_runs.append({
                        "run": run_idx,
                        "error": "All judges failed",
                        "latency": result["latency"],
                        "tokens": result["tokens"],
                        "scores": None,
                        "weighted_score": 0,
                        "validation": validation,
                    })
                    continue

                # Average scores across judges
                avg_scores = {}
                for dim in weights:
                    vals = [s.get(dim, 0) for s in all_judge_scores]
                    avg_scores[dim] = round(sum(vals) / len(vals), 1)

                weighted = compute_weighted_score(avg_scores, weights)

                tc_runs.append({
                    "run": run_idx,
                    "error": None,
                    "latency": result["latency"],
                    "tokens": result["tokens"],
                    "scores": avg_scores,
                    "weighted_score": weighted,
                    "validation": validation,
                    "judge_reasoning": [
                        s.get("reasoning", "") for s in all_judge_scores
                    ],
                })

            # Aggregate runs for this test case
            valid_runs = [r for r in tc_runs if r["weighted_score"] > 0]
            avg_score = (
                round(sum(r["weighted_score"] for r in valid_runs) / len(valid_runs), 2)
                if valid_runs
                else 0
            )
            score_values = [r["weighted_score"] for r in valid_runs]
            std_dev = 0.0
            if len(score_values) > 1:
                mean = sum(score_values) / len(score_values)
                variance = sum((x - mean) ** 2 for x in score_values) / (len(score_values) - 1)
                std_dev = round(variance ** 0.5, 2)

            model_results["test_results"].append({
                "test_case_id": tc["id"],
                "test_case_name": tc["name"],
                "category": tc["category"],
                "runs": tc_runs,
                "avg_score": avg_score,
                "std_dev": std_dev,
                "min_score": min(score_values) if score_values else 0,
                "max_score": max(score_values) if score_values else 0,
            })

        results.append(model_results)

    return {
        "run_id": run_id,
        "suite_name": suite["suite_name"],
        "runs_per_test": runs_per_test,
        "judge_models": [jm["id"] for jm in judge_models],
        "results": results,
    }
