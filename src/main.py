"""
EvalPulse — CLI orchestrator.

Usage:
    python evalpulse.py init                       Create a new evaluation suite interactively
    python evalpulse.py --validate --suite my_suite Validate a suite before running
    python evalpulse.py --dry-run --suite my_suite  Test pipeline with 1 model, 1 test case
    python evalpulse.py --run-eval --suite my_suite Run full evaluation
    python evalpulse.py --full                      Check models + evaluate + report
    python evalpulse.py --dashboard                 Start the dashboard web UI
"""

import argparse
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

from model_checker import check_for_new_models, load_registry
from evaluator import (
    run_evaluation, load_suite, call_model, validate_output,
    judge_output, compute_weighted_score, OPENROUTER_BASE_URL,
)
from safety_evaluator import run_safety_evaluation
from reporter import save_report, save_safety_report

GITHUB_ISSUES = "https://github.com/aristidesnakos/model-evals-framework/issues"


def run_dry_run(api_key: str, models: list, judge_models: list, suite_name: str) -> None:
    """Run one test case against one model for pipeline verification."""
    from openai import OpenAI
    from evaluator import EVALS_DIR
    from color_scoring import extract_hex_codes, score_palette

    suite = load_suite(suite_name)
    if suite.get("eval_type") == "safety":
        _run_safety_dry_run(api_key, models, judge_models, suite_name, suite)
        return

    weights = suite["scoring_weights"]
    test_cases = suite["test_cases"]
    suite_description = suite.get("description", "")

    enabled = [m for m in models if m.get("enabled")]
    if not enabled:
        print("Error: No enabled models in models.json")
        sys.exit(1)

    # Vision-aware selection: if any test case needs an image, require a
    # vision-capable enabled model and pick the first vision test case.
    suite_needs_vision = any(tc.get("image_path") for tc in test_cases)
    if suite_needs_vision:
        vision_enabled = [m for m in enabled if m.get("vision")]
        if not vision_enabled:
            print(
                f"Error: Suite '{suite_name}' requires a vision-capable model, "
                f"but none are enabled.\n"
                f"Hint: Set \"vision\": true on a multimodal model in models.json "
                f"and enable it."
            )
            sys.exit(1)
        model = vision_enabled[0]
        tc = next(t for t in test_cases if t.get("image_path"))
    else:
        model = enabled[0]
        tc = test_cases[0]

    image_path = (EVALS_DIR / tc["image_path"]) if tc.get("image_path") else None
    expected_colors = tc.get("expected_colors")

    print()
    print("DRY RUN -- verifying pipeline with 1 test case, 1 model, 1 iteration")
    print("=" * 60)
    print(f"Model: {model.get('name', model['id'])} ({model['id']})")
    print(f"Test:  {tc['name']} ({tc['id']})")
    print(f"Suite: {suite['suite_name']}")
    if image_path is not None:
        print(f"Image: {image_path} ({'exists' if image_path.exists() else 'MISSING'})")

    client = OpenAI(base_url=OPENROUTER_BASE_URL, api_key=api_key)

    # Call model
    print("\nCalling model...", end=" ", flush=True)
    result = call_model(
        client,
        model["id"],
        [{"role": "user", "content": tc["prompt"]}],
        image_path=image_path,
    )

    if result["error"]:
        print(f"FAILED")
        print(f"\nError: {result['error']}")
        print("\nHint: Check your OPENROUTER_API_KEY and internet connection.")
        sys.exit(1)

    total_tokens = result["tokens"]["input"] + result["tokens"]["output"]
    print(f"done ({result['latency']}s, {total_tokens} tokens)")

    # Output preview
    output = result["output"]
    preview = output[:500] + ("..." if len(output) > 500 else "")
    print(f"\nOutput preview (first 500 chars):")
    print("-" * 60)
    print(preview)
    print("-" * 60)

    # Validation
    validation = validate_output(output, tc.get("validation", {}))
    if validation["passed"]:
        print(f"\nValidation: PASSED")
    else:
        print(f"\nValidation: FAILED")
        for f in validation["failures"]:
            print(f"  - {f}")
        print("\nNote: Failed validation would score 0 in a full run (judges not called).")
        print("Consider adjusting your validation rules if this was unexpected.")
        sys.exit(1)

    # Deterministic color scoring (if applicable)
    color_match = None
    if expected_colors:
        extracted = extract_hex_codes(output)
        color_match = score_palette(
            expected_colors, extracted,
            tolerance=tc.get("color_tolerance", 10.0),
        )
        print(
            f"\nColor match: {color_match['matched_count']}/"
            f"{color_match['expected_count']} within ΔE ≤ {color_match['tolerance']} "
            f"| mean ΔE: {color_match.get('mean_delta_e', 'n/a')} "
            f"| extracted: {color_match['extracted_count']}"
        )

    # Judge
    for i, jm in enumerate(judge_models, 1):
        print(f"\nJudge {i} ({jm['id']})...", end=" ", flush=True)
        judge_result = judge_output(
            client, jm["id"], tc, output,
            suite_description=suite_description,
            color_match=color_match,
        )
        if judge_result["error"]:
            print(f"FAILED: {judge_result['error']}")
            continue

        scores = judge_result["scores"]
        weighted = compute_weighted_score(scores, weights)
        dims = " | ".join(
            f"{d.replace('_', ' ').title()}: {scores.get(d, 0)}/10"
            for d in weights
        )
        print(f"done")
        print(f"  {dims}")
        print(f"  Weighted: {weighted}/10")

    # Cost estimate for full run
    all_enabled = len(enabled)
    all_tests = len(test_cases)
    runs_per_test = suite.get("runs_per_test", 3)
    model_calls = all_enabled * all_tests * runs_per_test
    jcalls = model_calls * len(judge_models)
    total = model_calls + jcalls
    max_cost = max(m["pricing"]["output_per_million"] for m in enabled)
    est = (total * 2000 * max_cost) / 1_000_000

    print(f"\nFull run estimate:")
    print(f"  Models: {all_enabled} enabled | Test cases: {all_tests} | Runs/test: {runs_per_test}")
    print(f"  Model calls: {model_calls} | Judge calls: {jcalls} | Total: {total} API calls")
    print(f"  Estimated cost: ~${est:.2f}")

    print(f"\nPipeline verified. Run the full evaluation with:")
    print(f"  python evalpulse.py --run-eval --suite {suite_name}")


def _print_safety_gate_summary(eval_results: dict) -> None:
    gate = eval_results.get("gate_result", {})
    print(f"\nSuite coverage: {gate.get('suite_coverage', 'unknown').upper()}")
    models = gate.get("models", {})
    if not models:
        return
    print("\nPer-model gate results:")
    for model_id, info in models.items():
        print(
            f"  {info['result'].upper():7s} | tier {info['tier']} | "
            f"score {info['safety_score']:.2f}/10 | {model_id}"
        )
        for cf in info.get("critical_failures", []):
            print(f"     - FAIL: {cf['reason']} on {cf['test_case_id']}")
        for rf in info.get("review_flags", []):
            print(f"     - REVIEW: {rf}")


def _run_safety_dry_run(
    api_key: str,
    models: list,
    judge_models: list,
    suite_name: str,
    suite: dict,
) -> None:
    """Dry-run for safety suites: execute the first test case end-to-end
    (all turns) and judge the final turn with both judges."""
    from openai import OpenAI
    from safety_evaluator import (
        execute_conversation,
        judge_turn,
        apply_severity_deficit,
        compute_break_turn_index,
        DEFAULT_SAFETY_WEIGHTS,
    )

    weights = suite.get("scoring_weights", DEFAULT_SAFETY_WEIGHTS)
    test_cases = suite["test_cases"]

    enabled = [m for m in models if m.get("enabled")]
    if not enabled:
        print("Error: No enabled models in models.json")
        sys.exit(1)

    model = enabled[0]
    tc = test_cases[0]
    severity = tc.get("severity", "low")
    is_comply = tc.get("expected_behavior") == "comply"

    print()
    print("DRY RUN (safety) -- verifying pipeline with 1 test case, 1 model, 1 iteration")
    print("=" * 60)
    print(f"Model: {model.get('name', model['id'])} ({model['id']})")
    print(f"Test:  {tc['name']} ({tc['id']})")
    print(f"Suite: {suite['suite_name']} (eval_type=safety)")
    print(f"Category: {tc.get('category')} | Attack: {tc.get('attack_type')} | "
          f"Severity: {severity} | Expected: {tc.get('expected_behavior')}")
    print(f"Turns: {len(tc.get('turns', []))}")

    client = OpenAI(base_url=OPENROUTER_BASE_URL, api_key=api_key)

    print("\nExecuting conversation...", flush=True)
    convo = execute_conversation(
        client, model["id"], tc.get("system_prompt"), tc.get("turns", [])
    )

    if convo["aborted_at_turn"] is not None:
        err_turn = next((t for t in convo["assistant_turns"] if t.get("error")), None)
        print(f"  ABORTED at turn {convo['aborted_at_turn']}: "
              f"{err_turn['error'] if err_turn else 'unknown error'}")
        print("\nHint: Check your OPENROUTER_API_KEY and model availability.")
        sys.exit(1)

    for a_turn in convo["assistant_turns"]:
        preview = a_turn["assistant"][:200] + ("..." if len(a_turn["assistant"]) > 200 else "")
        print(f"\n-- Turn {a_turn['turn']} (user: {a_turn['user'][:80]!r}) "
              f"[{a_turn['latency']}s]")
        print(f"   Assistant: {preview}")

    # Judge every turn
    turn_records = []
    running_messages = []
    if tc.get("system_prompt"):
        running_messages.append({"role": "system", "content": tc["system_prompt"]})

    for a_turn in convo["assistant_turns"]:
        running_messages.append({"role": "user", "content": a_turn["user"]})
        running_messages.append({"role": "assistant", "content": a_turn["assistant"]})

        print(f"\nJudging turn {a_turn['turn']}...", flush=True)
        j = judge_turn(
            client, judge_models, tc, running_messages,
            turn_idx=a_turn["turn"], is_comply_variant=is_comply, weights=weights,
        )
        turn_records.append({"turn": a_turn["turn"], "judge_scores": j["judge_scores"]})
        if j["judge_errors"]:
            print(f"  Judge errors: {j['judge_errors']}")
        if j["judge_scores"]:
            dims = " | ".join(f"{k}: {v}" for k, v in j["judge_scores"].items())
            print(f"  Scores:   {dims}")
            print(f"  Weighted: {j['weighted_score']}/10")
        else:
            print(f"  Judges produced no usable score.")

    final_weighted = (turn_records[-1]["judge_scores"] or {}).get("refused") is not None and turn_records[-1]
    final = next((t for t in reversed(turn_records) if t.get("judge_scores")), None)
    if final:
        final_scores = final["judge_scores"]
        final_weighted_val = sum(final_scores.get(d, 0) * w for d, w in weights.items())
        severity_adj = apply_severity_deficit(final_weighted_val, severity)
        break_turn = compute_break_turn_index(turn_records)
        print(f"\nFinal turn weighted: {round(final_weighted_val, 2)}/10")
        print(f"Severity-adjusted ({severity}): {severity_adj}/10")
        print(f"Break turn index: {break_turn}")

    print(f"\nSafety pipeline verified. Run the full evaluation with:")
    print(f"  python evalpulse.py --run-eval --suite {suite_name}")


def main():
    parser = argparse.ArgumentParser(
        description="EvalPulse — Automated LLM evaluation pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Examples:
  python evalpulse.py init                         Create a new evaluation suite
  python evalpulse.py --validate --suite my_suite  Check suite before running
  python evalpulse.py --dry-run --suite my_suite   Quick pipeline test
  python evalpulse.py --run-eval --suite my_suite  Full evaluation
  python evalpulse.py --dashboard                  View results""",
    )
    parser.add_argument("command", nargs="?", help="Command to run (e.g., 'init')")
    parser.add_argument("--full", action="store_true", help="Run full pipeline: check models + evaluate + report")
    parser.add_argument("--check-models", action="store_true", help="Check OpenRouter for new models")
    parser.add_argument("--run-eval", action="store_true", help="Run evaluation suite")
    parser.add_argument("--auto-enable-new", action="store_true", help="Auto-enable newly detected models")
    parser.add_argument("--suite", default="suite", help="Evaluation suite name (default: suite)")
    parser.add_argument("--budget", type=float, default=None, help="Max budget in USD for this run")
    parser.add_argument("--dashboard", action="store_true", help="Start the dashboard web UI")
    parser.add_argument("--port", type=int, default=8080, help="Dashboard server port (default: 8080)")
    parser.add_argument("--validate", action="store_true", help="Validate a suite file before running")
    parser.add_argument("--dry-run", action="store_true", help="Test pipeline with 1 model and 1 test case")
    args = parser.parse_args()

    # Handle 'init' positional command
    if args.command == "init":
        from init_wizard import run_init
        run_init()
        return

    has_action = any([args.full, args.check_models, args.run_eval, args.dashboard, args.validate, args.dry_run])
    if not has_action:
        parser.print_help()
        sys.exit(1)

    # Commands that don't need an API key
    if args.validate:
        from suite_validator import validate_suite
        result = validate_suite(args.suite)
        result.print_report()
        sys.exit(0 if result.is_valid else 1)

    # Everything below needs an API key (except dashboard-only)
    needs_api_key = args.full or args.check_models or args.run_eval or args.dry_run
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if needs_api_key and not api_key:
        print("Error: OPENROUTER_API_KEY not set.")
        print("Hint: Copy .env.example to .env and add your key from https://openrouter.ai")
        sys.exit(1)

    try:
        # Dry run
        if args.dry_run:
            registry = load_registry()
            models = registry["models"]
            judge_models = registry.get("judge_models", [])
            if not judge_models:
                print("Error: No judge models configured in models.json")
                sys.exit(1)
            run_dry_run(api_key, models, judge_models, args.suite)
            if not args.dashboard:
                return

        # Step 1: Check for new models
        if args.full or args.check_models:
            print("=" * 60)
            print("Checking OpenRouter for new models...")
            print("=" * 60)

            result = check_for_new_models(api_key, auto_enable=args.auto_enable_new)

            if result["new"]:
                print(f"\nFound {len(result['new'])} new model(s) matching Tier 3 criteria:")
                for m in result["new"]:
                    status = "ENABLED" if m["enabled"] else "disabled"
                    print(f"  [{status}] {m['id']} — ${m['pricing']['input_per_million']:.2f}/${m['pricing']['output_per_million']:.2f} per 1M tokens")
            else:
                print("\nNo new models found.")

            if result["removed_from_openrouter"]:
                print(f"\n{len(result['removed_from_openrouter'])} model(s) no longer on OpenRouter:")
                for mid in result["removed_from_openrouter"]:
                    print(f"  {mid}")

            print(f"\nTotal matching: {result['total_matching']} | Registered: {result['total_registered']}")

        # Step 2: Run evaluation
        if args.full or args.run_eval:
            print("\n" + "=" * 60)
            print("Running evaluation...")
            print("=" * 60)

            registry = load_registry()
            models = registry["models"]
            judge_models = registry.get("judge_models", [])

            if not judge_models:
                print("Error: No judge models configured in models.json")
                sys.exit(1)

            enabled_count = sum(1 for m in models if m.get("enabled"))
            print(f"Enabled models: {enabled_count}")
            print(f"Judge models: {', '.join(jm['id'] for jm in judge_models)}")
            print(f"Suite: {args.suite}")

            suite_peek = load_suite(args.suite)
            eval_type = suite_peek.get("eval_type", "quality")
            print(f"Eval type: {eval_type}")

            if eval_type == "safety":
                eval_results = run_safety_evaluation(
                    api_key=api_key,
                    models=models,
                    judge_models=judge_models,
                    suite_name=args.suite,
                    budget=args.budget,
                )
            else:
                eval_results = run_evaluation(
                    api_key=api_key,
                    models=models,
                    judge_models=judge_models,
                    suite_name=args.suite,
                    budget=args.budget,
                )

            if eval_results.get("error"):
                print(f"\nEvaluation stopped: {eval_results['error']}")
                if eval_results.get("gate_result"):
                    gr = eval_results["gate_result"]
                    if gr.get("suite_coverage") == "fail":
                        print("\nGate 1 coverage failures:")
                        for name, msg in gr.get("gate_1_failures", []):
                            print(f"  - {name}: {msg}")
                sys.exit(1)

            # Step 3: Generate report
            print("\n" + "=" * 60)
            print("Generating report...")
            print("=" * 60)

            if eval_type == "safety":
                report_path = save_safety_report(eval_results)
                print(f"\nDone. Report: {report_path}")
                _print_safety_gate_summary(eval_results)
            else:
                report_path = save_report(eval_results)
                print(f"\nDone. Report: {report_path}")

        # Step 4: Dashboard
        if args.dashboard:
            from dashboard import start_dashboard
            reports_dir = Path(__file__).parent.parent / "reports"
            start_dashboard(port=args.port, reports_dir=reports_dir)

    except RuntimeError as e:
        print(f"\nError: {e}")
        print("Hint: Check your OPENROUTER_API_KEY in .env and verify your internet connection.")
        sys.exit(1)

    except FileNotFoundError as e:
        print(f"\nError: {e}")
        print("Hint: Run 'python evalpulse.py init' to create a new evaluation suite.")
        sys.exit(1)

    except json.JSONDecodeError as e:
        print(f"\nError: Invalid JSON — {e}")
        print(f"Hint: Run 'python evalpulse.py --validate --suite {args.suite}' to check your suite file.")
        sys.exit(1)

    except KeyError as e:
        print(f"\nError: Missing required field {e}")
        print(f"Hint: Run 'python evalpulse.py --validate --suite {args.suite}' to check your suite file.")
        sys.exit(1)

    except KeyboardInterrupt:
        print("\n\nInterrupted.")
        sys.exit(130)

    except Exception as e:
        print(f"\nUnexpected error: {e}")
        print(f"Please report this at {GITHUB_ISSUES}")
        sys.exit(1)


if __name__ == "__main__":
    main()
