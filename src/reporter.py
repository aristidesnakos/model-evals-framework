"""
Generates markdown comparison reports from evaluation results.
Includes summary table, per-test-case breakdown, and cross-model analysis.
"""

import json
from datetime import datetime, timezone
from pathlib import Path

REPORTS_DIR = Path(__file__).parent.parent / "reports"


def generate_report(eval_results: dict) -> str:
    """Generate a full markdown report from evaluation results."""
    run_id = eval_results["run_id"]
    suite_name = eval_results["suite_name"]
    results = eval_results["results"]
    runs_per_test = eval_results.get("runs_per_test", 3)
    judge_models = eval_results.get("judge_models", [])

    lines = []
    lines.append(f"# Evaluation Report: {suite_name}")
    lines.append("")
    lines.append(f"**Run ID:** {run_id}")
    lines.append(f"**Date:** {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    lines.append(f"**Runs per test:** {runs_per_test}")
    lines.append(f"**Judges:** {', '.join(judge_models)}")
    lines.append("")

    # --- Summary table ---
    lines.append("## Summary")
    lines.append("")
    lines.append("| Model | Avg Score | Min | Max | Std Dev | Avg Latency | Cost | Total Tokens | Errors |")
    lines.append("|-------|-----------|-----|-----|---------|-------------|------|-------------|--------|")

    model_summaries = []
    for model_result in results:
        test_results = model_result["test_results"]
        # Exclude skipped tests (avg_score=None) and zero-scored tests from rollup.
        all_scores = [
            tr["avg_score"]
            for tr in test_results
            if tr.get("avg_score") not in (None, 0)
        ]
        all_latencies = []
        total_tokens = 0
        errors = model_result["errors"]
        skipped_tests = sum(1 for tr in test_results if tr.get("skipped"))

        total_cost = 0.0
        for tr in test_results:
            for run in tr["runs"]:
                if run.get("latency"):
                    all_latencies.append(run["latency"])
                tokens = run.get("tokens", {})
                total_tokens += tokens.get("input", 0) + tokens.get("output", 0)
                total_cost += run.get("cost", 0)

        avg_score = round(sum(all_scores) / len(all_scores), 1) if all_scores else 0
        min_score = min(all_scores) if all_scores else 0
        max_score = max(all_scores) if all_scores else 0
        std_devs = [tr["std_dev"] for tr in test_results if tr.get("std_dev", 0) > 0]
        avg_std = round(sum(std_devs) / len(std_devs), 2) if std_devs else 0
        avg_lat = round(sum(all_latencies) / len(all_latencies), 1) if all_latencies else 0

        model_summaries.append({
            "model_id": model_result["model_id"],
            "model_name": model_result["model_name"],
            "avg_score": avg_score,
            "min_score": min_score,
            "max_score": max_score,
            "avg_std": avg_std,
            "avg_latency": avg_lat,
            "total_cost": round(total_cost, 4),
            "total_tokens": total_tokens,
            "errors": errors,
            "skipped_tests": skipped_tests,
        })

    # Sort by avg score descending
    model_summaries.sort(key=lambda x: x["avg_score"], reverse=True)

    for ms in model_summaries:
        errors_cell = (
            f"{ms['errors']} ({ms['skipped_tests']} skipped)"
            if ms.get("skipped_tests")
            else str(ms["errors"])
        )
        cost_str = f"${ms['total_cost']:.4f}"
        lines.append(
            f"| {ms['model_name']} | {ms['avg_score']}/10 "
            f"| {ms['min_score']} | {ms['max_score']} "
            f"| {ms['avg_std']} | {ms['avg_latency']}s "
            f"| {cost_str} | {ms['total_tokens']:,} "
            f"| {errors_cell} |"
        )

    lines.append("")

    # --- Per-test-case breakdown ---
    lines.append("## Per-Test-Case Results")
    lines.append("")

    # Collect all test case names from first model
    if results:
        test_cases = results[0]["test_results"]
        for tc in test_cases:
            tc_id = tc["test_case_id"]
            tc_name = tc["test_case_name"]
            category = tc["category"]

            lines.append(f"### {tc_name}")
            lines.append(f"*Category: {category} | ID: {tc_id}*")
            lines.append("")
            lines.append("| Model | Avg | Std Dev | Completeness | Accuracy | Format | Domain | Clarity |")
            lines.append("|-------|-----|---------|-------------|----------|--------|--------|---------|")

            tc_rows = []
            color_match_lines: list[str] = []
            for model_result in results:
                # Find matching test case
                matching = [
                    tr for tr in model_result["test_results"]
                    if tr["test_case_id"] == tc_id
                ]
                if not matching:
                    continue
                tr = matching[0]

                # Average dimension scores across valid runs
                dim_avgs = {"completeness": 0, "accuracy": 0, "format": 0, "domain_relevance": 0, "clarity": 0}
                valid_runs = [r for r in tr["runs"] if r.get("scores")]
                if valid_runs:
                    for dim in dim_avgs:
                        vals = [r["scores"].get(dim, 0) for r in valid_runs]
                        dim_avgs[dim] = round(sum(vals) / len(vals), 1)

                tc_rows.append({
                    "model_name": model_result["model_name"],
                    "avg": tr.get("avg_score"),
                    "std_dev": tr.get("std_dev", 0.0),
                    "skipped": bool(tr.get("skipped")),
                    **dim_avgs,
                })

                # Collect color-match summary across runs (if present).
                cm_runs = [r.get("color_match") for r in tr["runs"] if r.get("color_match")]
                if cm_runs:
                    first = cm_runs[0]
                    matched = sum(r.get("matched_count", 0) for r in cm_runs) / len(cm_runs)
                    expected_ct = first.get("expected_count", 0)
                    deltas = [r.get("mean_delta_e") for r in cm_runs if r.get("mean_delta_e") is not None]
                    mean_de = round(sum(deltas) / len(deltas), 2) if deltas else None
                    color_match_lines.append(
                        f"- **{model_result['model_name']}** — "
                        f"matched {matched:.1f}/{expected_ct} within ΔE ≤ "
                        f"{first.get('tolerance')}, mean ΔE = "
                        f"{mean_de if mean_de is not None else 'n/a'}"
                    )

            # Sort: skipped rows last, then by avg descending.
            tc_rows.sort(
                key=lambda x: (x["skipped"], -(x["avg"] if x["avg"] is not None else -1))
            )
            for row in tc_rows:
                if row["skipped"]:
                    lines.append(
                        f"| {row['model_name']} | SKIPPED | — | — | — | — | — | — |"
                    )
                else:
                    lines.append(
                        f"| {row['model_name']} | {row['avg']} | {row['std_dev']} | "
                        f"{row['completeness']} | {row['accuracy']} | {row['format']} | "
                        f"{row['domain_relevance']} | {row['clarity']} |"
                    )
            if color_match_lines:
                lines.append("")
                lines.append("**Color match (CIEDE2000):**")
                lines.extend(color_match_lines)
            lines.append("")

    # --- Reliability analysis ---
    lines.append("## Reliability Analysis")
    lines.append("")
    lines.append("Models with high standard deviation across runs may produce inconsistent results.")
    lines.append("")
    lines.append("| Model | Avg Std Dev | Reliability |")
    lines.append("|-------|-----------|-------------|")

    for ms in model_summaries:
        if ms["avg_std"] < 0.5:
            reliability = "High"
        elif ms["avg_std"] < 1.0:
            reliability = "Medium"
        else:
            reliability = "Low"
        lines.append(f"| {ms['model_name']} | {ms['avg_std']} | {reliability} |")

    lines.append("")
    lines.append("---")
    lines.append(f"*Generated by EvalPulse on {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}*")

    return "\n".join(lines)


def save_report(eval_results: dict) -> Path:
    """Generate and save report to the reports directory."""
    REPORTS_DIR.mkdir(exist_ok=True)

    run_id = eval_results["run_id"]
    suite_name = eval_results["suite_name"]

    # Save markdown report
    report_md = generate_report(eval_results)
    md_path = REPORTS_DIR / f"{suite_name}_{run_id}.md"
    md_path.write_text(report_md)

    # Save raw JSON results alongside
    json_path = REPORTS_DIR / f"{suite_name}_{run_id}.json"
    json_path.write_text(json.dumps(eval_results, indent=2, default=str))

    print(f"Report saved: {md_path}")
    print(f"Raw results: {json_path}")

    return md_path
