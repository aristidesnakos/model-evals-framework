"""
Runs evaluation suite against enabled models.
Scores with dual LLM judges via OpenRouter.
"""

import re
from datetime import datetime, timezone

from openai import OpenAI

from color_scoring import (
    extract_hex_codes,
    format_color_match_for_judge,
    score_palette,
)
from eval_common import (
    EVALS_DIR,
    OPENROUTER_BASE_URL,
    call_model,
    compute_weighted_score,
    load_suite,
    parse_judge_response,
)

__all__ = [
    "EVALS_DIR",
    "OPENROUTER_BASE_URL",
    "call_model",
    "compute_weighted_score",
    "judge_output",
    "load_suite",
    "parse_judge_response",
    "run_evaluation",
    "validate_output",
]


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


def build_judge_prompt(
    test_case: dict,
    model_output: str,
    suite_description: str = "",
    color_match: dict | None = None,
) -> str:
    """Build the scoring prompt for the LLM judge."""
    criteria = test_case["scoring_criteria"]
    reference = test_case.get("reference_answer", "No reference provided.")

    preamble = "You are an expert evaluator."
    if suite_description:
        preamble += f" Context: {suite_description}"

    color_block = ""
    if color_match is not None:
        color_block = "\n\n" + format_color_match_for_judge(color_match)

    return f"""{preamble}

Score the following model output against the criteria below. Be strict and specific.

## Test Case
**Name:** {test_case["name"]}
**Category:** {test_case["category"]}
**Prompt given to model:** {test_case["prompt"]}

## Reference Answer (what a good response should cover)
{reference}

## Model Output
{model_output}{color_block}

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


def judge_output(
    client: OpenAI,
    judge_model: str,
    test_case: dict,
    model_output: str,
    suite_description: str = "",
    color_match: dict | None = None,
) -> dict:
    """Score a model output using an LLM judge."""
    prompt = build_judge_prompt(
        test_case, model_output, suite_description, color_match=color_match
    )
    result = call_model(
        client, judge_model, [{"role": "user", "content": prompt}]
    )

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
        pricing = model.get("pricing", {})
        input_cost_per_million = pricing.get("input_per_million", 0)
        output_cost_per_million = pricing.get("output_per_million", 0)
        print(f"\nEvaluating: {model_id}")
        model_results = {
            "model_id": model_id,
            "model_name": model.get("name", model_id),
            "pricing": pricing,
            "test_results": [],
            "errors": 0,
        }

        for tc in test_cases:
            tc_runs = []
            tc_image_path_raw = tc.get("image_path")
            tc_needs_vision = bool(tc_image_path_raw)
            tc_image_path = (
                (EVALS_DIR / tc_image_path_raw) if tc_image_path_raw else None
            )
            expected_colors = tc.get("expected_colors")

            # Skip whole test case for non-vision models when vision is required.
            if tc_needs_vision and not model.get("vision"):
                print(
                    f"  Skipping {tc['id']} ({tc['name']}) — "
                    f"model has no vision capability"
                )
                tc_runs.append({
                    "run": 0,
                    "skipped": True,
                    "reason": "model has no vision capability",
                    "error": None,
                    "latency": 0.0,
                    "scores": None,
                    "weighted_score": None,
                    "validation": None,
                })
                model_results["test_results"].append({
                    "test_case_id": tc["id"],
                    "test_case_name": tc["name"],
                    "category": tc["category"],
                    "prompt": tc["prompt"],
                    "reference_answer": tc.get("reference_answer", ""),
                    "runs": tc_runs,
                    "avg_score": None,
                    "std_dev": 0.0,
                    "min_score": None,
                    "max_score": None,
                    "skipped": True,
                    "skipped_reason": "model has no vision capability",
                })
                continue

            for run_idx in range(runs_per_test):
                # Call the model (with image if configured)
                result = call_model(
                    client,
                    model_id,
                    [{"role": "user", "content": tc["prompt"]}],
                    image_path=tc_image_path,
                )

                # Compute cost for this call
                run_tokens = result["tokens"]
                run_cost = round(
                    (run_tokens["input"] * input_cost_per_million
                     + run_tokens["output"] * output_cost_per_million) / 1_000_000,
                    6,
                )

                if result["error"]:
                    model_results["errors"] += 1
                    tc_runs.append({
                        "run": run_idx,
                        "error": result["error"],
                        "latency": result["latency"],
                        "tokens": run_tokens,
                        "cost": run_cost,
                        "output": result["output"],
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
                        "tokens": run_tokens,
                        "cost": run_cost,
                        "output": result["output"],
                        "scores": None,
                        "weighted_score": 0,
                        "validation": validation,
                    })
                    continue

                # Deterministic color-palette scoring (if this test case has ground truth)
                color_match = None
                if expected_colors:
                    extracted = extract_hex_codes(result["output"])
                    color_match = score_palette(
                        expected_colors,
                        extracted,
                        tolerance=tc.get("color_tolerance", 10.0),
                    )

                # Judge with dual judges and average
                all_judge_scores = []
                for jm in judge_models:
                    judge_result = judge_output(
                        client, jm["id"], tc, result["output"],
                        suite_description=suite_description,
                        color_match=color_match,
                    )
                    if judge_result["scores"]:
                        all_judge_scores.append(judge_result["scores"])

                if not all_judge_scores:
                    tc_runs.append({
                        "run": run_idx,
                        "error": "All judges failed",
                        "latency": result["latency"],
                        "tokens": run_tokens,
                        "cost": run_cost,
                        "output": result["output"],
                        "scores": None,
                        "weighted_score": 0,
                        "validation": validation,
                        "color_match": color_match,
                    })
                    continue

                # Average scores across judges
                avg_scores = {}
                for dim in weights:
                    vals = [s.get(dim, 0) for s in all_judge_scores]
                    avg_scores[dim] = round(sum(vals) / len(vals), 1)

                weighted = compute_weighted_score(avg_scores, weights)

                run_record = {
                    "run": run_idx,
                    "error": None,
                    "latency": result["latency"],
                    "tokens": run_tokens,
                    "cost": run_cost,
                    "output": result["output"],
                    "scores": avg_scores,
                    "weighted_score": weighted,
                    "validation": validation,
                    "judge_reasoning": [
                        s.get("reasoning", "") for s in all_judge_scores
                    ],
                }
                if color_match is not None:
                    run_record["color_match"] = color_match
                tc_runs.append(run_record)

            # Aggregate runs for this test case (exclude skipped and zero/None).
            valid_runs = [
                r for r in tc_runs
                if not r.get("skipped")
                and r.get("weighted_score") not in (None, 0)
            ]
            score_values = [r["weighted_score"] for r in valid_runs]
            avg_score = (
                round(sum(score_values) / len(score_values), 2)
                if score_values
                else 0
            )
            std_dev = 0.0
            if len(score_values) > 1:
                mean = sum(score_values) / len(score_values)
                variance = sum((x - mean) ** 2 for x in score_values) / (len(score_values) - 1)
                std_dev = round(variance ** 0.5, 2)

            model_results["test_results"].append({
                "test_case_id": tc["id"],
                "test_case_name": tc["name"],
                "category": tc["category"],
                "prompt": tc["prompt"],
                "reference_answer": tc.get("reference_answer", ""),
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
