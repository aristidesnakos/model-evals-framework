"""
EvalPulse — CLI orchestrator.

Usage:
    python main.py --full                      Full pipeline: check models + evaluate + report
    python main.py --check-models              Just check for new models on OpenRouter
    python main.py --run-eval                  Just run evaluation on enabled models
    python main.py --full --auto-enable-new    Auto-enable newly detected models
    python main.py --run-eval --suite my_suite Use a specific evaluation suite
    python main.py --run-eval --budget 5.00    Set max budget in USD
    python main.py --dashboard                 Start the dashboard web UI
"""

import argparse
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

from model_checker import check_for_new_models, load_registry
from evaluator import run_evaluation
from reporter import save_report


def main():
    parser = argparse.ArgumentParser(description="EvalPulse — Automated LLM evaluation pipeline")
    parser.add_argument("--full", action="store_true", help="Run full pipeline: check models + evaluate + report")
    parser.add_argument("--check-models", action="store_true", help="Check OpenRouter for new models")
    parser.add_argument("--run-eval", action="store_true", help="Run evaluation suite")
    parser.add_argument("--auto-enable-new", action="store_true", help="Auto-enable newly detected models")
    parser.add_argument("--suite", default="suite", help="Evaluation suite name (default: suite)")
    parser.add_argument("--budget", type=float, default=None, help="Max budget in USD for this run")
    parser.add_argument("--dashboard", action="store_true", help="Start the dashboard web UI")
    parser.add_argument("--port", type=int, default=8080, help="Dashboard server port (default: 8080)")
    args = parser.parse_args()

    if not any([args.full, args.check_models, args.run_eval, args.dashboard]):
        parser.print_help()
        sys.exit(1)

    # API key required for everything except dashboard-only
    needs_api_key = args.full or args.check_models or args.run_eval
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if needs_api_key and not api_key:
        print("Error: OPENROUTER_API_KEY not set. Copy .env.example to .env and add your key.")
        sys.exit(1)

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

        eval_results = run_evaluation(
            api_key=api_key,
            models=models,
            judge_models=judge_models,
            suite_name=args.suite,
            budget=args.budget,
        )

        if eval_results.get("error"):
            print(f"\nEvaluation stopped: {eval_results['error']}")
            sys.exit(1)

        # Step 3: Generate report
        print("\n" + "=" * 60)
        print("Generating report...")
        print("=" * 60)

        report_path = save_report(eval_results)
        print(f"\nDone. Report: {report_path}")

    # Step 4: Dashboard
    if args.dashboard:
        from dashboard import start_dashboard
        reports_dir = Path(__file__).parent.parent / "reports"
        start_dashboard(port=args.port, reports_dir=reports_dir)


if __name__ == "__main__":
    main()
