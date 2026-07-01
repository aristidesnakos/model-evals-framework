"""
Runs agentic evaluation suites: multi-step, tool-calling tasks against real
APIs (agentic_tools.py), scored deterministically rather than by an LLM
judge — success is "did the model reach a grounded correct answer", and the
metrics that actually matter here are tokens / cost / tool-calls / latency
to get there. This is what evaluator.py (single-turn quality) and
safety_evaluator.py (adversarial conversation) cannot measure: neither one
exercises a tool-use loop, so neither can show whether one model converges
on a correct multi-step outcome with less waste than another.

Design: see the "efficiency" discussion in conversation history — single-
turn quality scoring mostly captures verbosity, not agentic efficiency.
"""

import re
from datetime import datetime, timezone

from openai import OpenAI

from eval_common import OPENROUTER_BASE_URL, call_model_with_tools, load_suite
from tool_packs import DEFAULT_TOOL_PACK, get_tool_pack

DEFAULT_MAX_TOOL_CALLS = 8
DEFAULT_SYSTEM_PROMPT = (
    "You are a research assistant with access to real government data tools. "
    "Use the tools to gather grounded facts before answering — do not guess "
    "or rely on prior knowledge for anything the tools can look up. When you "
    "have enough information, give a final answer with no further tool calls."
)


def _final_claim_text(final_answer: str) -> str:
    """Isolate the model's actual final claim from any preceding scratch work
    (e.g. a numbered list of candidates it considered before concluding).
    Suites instruct models to end with one specific final-answer sentence, so
    the last paragraph (or last line, if the model didn't blank-line
    separate) is what should be graded — checking the whole response risks
    picking up distractor values mentioned while reasoning, not the answer.
    """
    paragraphs = [p.strip() for p in final_answer.strip().split("\n\n") if p.strip()]
    if paragraphs:
        return paragraphs[-1]
    lines = [l.strip() for l in final_answer.strip().split("\n") if l.strip()]
    return lines[-1] if lines else final_answer


def _check_required_tools(test_case: dict, tool_log: list[dict]) -> str | None:
    required_tools = set(test_case.get("required_tools", []))
    called_tools = {entry["name"] for entry in tool_log}
    missing = required_tools - called_tools
    if missing:
        return f"never called required tool(s): {sorted(missing)}"
    return None


def _check_grounded_citation(test_case: dict, final_answer: str, tool_log: list[dict]) -> dict:
    """Default check: final_answer must match answer_pattern, AND the matched
    value must be "grounded" — it must appear among the results of the run's
    own grounding_tool calls (self-consistent grounding: rejects answers the
    model could have produced by guessing/prior knowledge instead of using
    the tools). grounding_tool defaults to ecfr_get_section_text for
    backward compatibility with the construction suite.
    """
    answer_pattern = test_case.get("answer_pattern")
    grounding_tool = test_case.get("grounding_tool", "ecfr_get_section_text")
    claim = _final_claim_text(final_answer)

    match = re.search(answer_pattern, claim) if answer_pattern else None
    if answer_pattern and not match:
        return {"success": False, "reason": "final answer did not contain expected pattern"}

    if match:
        matched_value = match.group(0)
        grounded = any(
            matched_value in str(entry.get("result", ""))
            for entry in tool_log
            if entry["name"] == grounding_tool
        )
        if not grounded:
            return {
                "success": False,
                "reason": f"answer cited {matched_value!r} but that was never fetched via {grounding_tool}",
            }

    tools_error = _check_required_tools(test_case, tool_log)
    if tools_error:
        return {"success": False, "reason": tools_error}
    return {"success": True, "reason": None}


def _check_repeat_entity(test_case: dict, final_answer: str, tool_log: list[dict]) -> dict:
    """For "flag the entity with 2+ occurrences" tasks (e.g. openFDA recalls):
    the final answer must cite at least 2 distinct values matching
    answer_pattern (e.g. NDC codes) that, per this run's OWN
    entity_lookup_tool calls, all resolve to the same entity_field value.
    This is self-consistent grounding for a cross-referencing claim rather
    than a single-fact citation — it can't be satisfied by guessing, only by
    actually looking up 2+ NDCs and noticing they share a manufacturer.
    """
    answer_pattern = test_case.get("answer_pattern")
    entity_lookup_tool = test_case.get("entity_lookup_tool", "openfda_get_ndc_manufacturer")
    entity_field = test_case.get("entity_field", "labeler_name")
    min_repeats = test_case.get("min_repeats", 2)
    claim = _final_claim_text(final_answer)

    matches = set(re.findall(answer_pattern, claim)) if answer_pattern else set()
    if not matches:
        return {"success": False, "reason": "final answer did not contain expected pattern"}

    key_by_value = {}
    for entry in tool_log:
        if entry["name"] != entity_lookup_tool:
            continue
        result = entry.get("result") or {}
        if not isinstance(result, dict):
            continue
        arg_value = next(iter(entry.get("arguments", {}).values()), None)
        key = result.get(entity_field)
        if arg_value is not None and key:
            key_by_value[str(arg_value)] = key

    cited_lookups = {v: key_by_value[v] for v in matches if v in key_by_value}
    if len(cited_lookups) < min_repeats:
        return {
            "success": False,
            "reason": (
                f"answer cited {sorted(matches)} but only {len(cited_lookups)} were "
                f"actually looked up via {entity_lookup_tool} in this run (need {min_repeats})"
            ),
        }

    distinct_entities = set(cited_lookups.values())
    if len(distinct_entities) != 1:
        return {
            "success": False,
            "reason": f"cited values resolved to {len(distinct_entities)} different {entity_field} values, not one shared entity",
        }

    tools_error = _check_required_tools(test_case, tool_log)
    if tools_error:
        return {"success": False, "reason": tools_error}
    return {"success": True, "reason": None}


_CHECKERS = {
    "grounded_citation": _check_grounded_citation,
    "repeat_entity": _check_repeat_entity,
}


def _check_success(test_case: dict, final_answer: str | None, tool_log: list[dict]) -> dict:
    """Deterministic, judge-free scoring — dispatches on check_type (default
    'grounded_citation'). See _check_grounded_citation / _check_repeat_entity."""
    if not final_answer:
        return {"success": False, "reason": "no final answer produced"}

    check_type = test_case.get("check_type", "grounded_citation")
    checker = _CHECKERS.get(check_type)
    if checker is None:
        return {"success": False, "reason": f"unknown check_type: {check_type!r}"}
    return checker(test_case, final_answer, tool_log)


def run_agentic_task(
    client: OpenAI,
    model_id: str,
    test_case: dict,
    tool_schemas: list[dict],
    execute_tool_call: callable,
) -> dict:
    """Run one model through one tool-use task to completion or budget exhaustion."""
    max_tool_calls = test_case.get("max_tool_calls", DEFAULT_MAX_TOOL_CALLS)
    messages = [
        {"role": "system", "content": test_case.get("system_prompt", DEFAULT_SYSTEM_PROMPT)},
        {"role": "user", "content": test_case["goal"]},
    ]

    tool_log: list[dict] = []
    total_tokens = {"input": 0, "output": 0}
    total_latency = 0.0
    model_calls = 0
    final_answer = None
    error = None

    while True:
        if len(tool_log) >= max_tool_calls:
            error = f"exceeded max_tool_calls ({max_tool_calls})"
            break

        result = call_model_with_tools(client, model_id, messages, tool_schemas)
        model_calls += 1
        total_latency += result["latency"]
        total_tokens["input"] += result["tokens"]["input"]
        total_tokens["output"] += result["tokens"]["output"]

        if result["error"]:
            error = result["error"]
            break

        messages.append(result["assistant_message"])

        if not result["tool_calls"]:
            final_answer = result["content"]
            break

        for call in result["tool_calls"]:
            if len(tool_log) >= max_tool_calls:
                break
            tool_result = execute_tool_call(call["name"], call["arguments"])
            tool_log.append({"name": call["name"], "arguments": call["arguments"], "result": tool_result})
            messages.append({
                "role": "tool",
                "tool_call_id": call["id"],
                "content": str(tool_result),
            })

    scoring = _check_success(test_case, final_answer, tool_log) if not error else {
        "success": False, "reason": error,
    }

    return {
        "model_calls": model_calls,
        "tool_calls": len(tool_log),
        "tool_log": tool_log,
        "tokens": total_tokens,
        "latency": round(total_latency, 2),
        "final_answer": final_answer,
        "success": scoring["success"],
        "failure_reason": scoring["reason"],
        "error": error,
    }


def run_agentic_evaluation(
    api_key: str,
    models: list[dict],
    suite_name: str,
    budget: float | None = None,
) -> dict:
    """Run the full agentic evaluation pipeline. No judge models — scoring is
    deterministic (see _check_success), so cost is purely model-call cost.
    """
    suite = load_suite(suite_name)
    test_cases = suite["test_cases"]
    runs_per_test = suite.get("runs_per_test", 1)
    tool_schemas, execute_tool_call = get_tool_pack(suite.get("tool_pack", DEFAULT_TOOL_PACK))

    client = OpenAI(base_url=OPENROUTER_BASE_URL, api_key=api_key)
    enabled_models = [m for m in models if m.get("enabled")]
    if not enabled_models:
        return {"error": "No enabled models to evaluate", "results": []}

    max_calls_per_task = max((tc.get("max_tool_calls", DEFAULT_MAX_TOOL_CALLS) + 1) for tc in test_cases)
    total_model_calls = max_calls_per_task * len(test_cases) * runs_per_test * len(enabled_models)
    print(f"Agentic plan: up to {total_model_calls} model calls (no judge calls — scoring is deterministic)")

    if budget is not None:
        max_output_cost = max(m["pricing"]["output_per_million"] for m in enabled_models)
        est_cost = (total_model_calls * 2000 * max_output_cost) / 1_000_000
        if est_cost > budget:
            return {"error": f"Estimated cost ${est_cost:.2f} exceeds budget ${budget:.2f}", "results": []}
        print(f"Estimated cost: ~${est_cost:.2f} (budget: ${budget:.2f})")

    run_id = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    results = []

    for model in enabled_models:
        model_id = model["id"]
        input_cost = model["pricing"].get("input_per_million", 0)
        output_cost = model["pricing"].get("output_per_million", 0)
        print(f"\nEvaluating {model.get('name', model_id)} ({model_id})...")

        for tc in test_cases:
            for run_idx in range(runs_per_test):
                outcome = run_agentic_task(client, model_id, tc, tool_schemas, execute_tool_call)
                cost = round(
                    (outcome["tokens"]["input"] * input_cost + outcome["tokens"]["output"] * output_cost)
                    / 1_000_000,
                    4,
                )
                status = "PASS" if outcome["success"] else f"FAIL ({outcome['failure_reason']})"
                print(
                    f"  [{tc['id']}] run {run_idx + 1}/{runs_per_test}: {status} | "
                    f"{outcome['model_calls']} model calls, {outcome['tool_calls']} tool calls, "
                    f"{sum(outcome['tokens'].values())} tokens, ${cost:.4f}, {outcome['latency']}s"
                )
                results.append({
                    "model_id": model_id,
                    "model_name": model.get("name", model_id),
                    "test_case_id": tc["id"],
                    "test_case_name": tc.get("name", tc["id"]),
                    "run": run_idx + 1,
                    "success": outcome["success"],
                    "failure_reason": outcome["failure_reason"],
                    "model_calls": outcome["model_calls"],
                    "tool_calls": outcome["tool_calls"],
                    "tool_log": outcome["tool_log"],
                    "tokens": outcome["tokens"],
                    "cost": cost,
                    "latency": outcome["latency"],
                    "final_answer": outcome["final_answer"],
                    "error": outcome["error"],
                })

    return {
        "run_id": run_id,
        "suite_name": suite_name,
        "eval_type": "agentic",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "results": results,
    }
