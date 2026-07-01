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
EVALS_DIR = ROOT / "evals"


def suite_meta(suite_name: str) -> dict:
    """Resolve a suite's presentation facets (modality, task_type).

    Reads evals/<suite_name>.json when present; otherwise infers from the name.
    These drive the lmarena-style category tabs on the dashboard.
    """
    suite_file = EVALS_DIR / f"{suite_name}.json"
    modality = task_type = None
    if suite_file.exists():
        try:
            s = json.loads(suite_file.read_text())
            modality = s.get("modality")
            task_type = s.get("task_type")
            if modality is None:
                has_image = any(tc.get("image_path") for tc in s.get("test_cases", []))
                modality = "vision" if has_image else "text"
        except (json.JSONDecodeError, OSError):
            pass
    if modality is None:
        modality = "text"
    if task_type is None:
        # Heuristic fallback for reports whose suite file is absent.
        name = suite_name.lower()
        task_type = "classification" if ("classif" in name or "safety_gate" in name) else "generation"
    return {"modality": modality, "task_type": task_type}


# Per-model quality bias for seeded demo scores (higher-tier models score a touch
# better). Single source of truth shared by the quality and image-safety
# synthesizers so the two can't drift apart.
MODEL_BIAS = {
    "openai/gpt-5.4-mini":                  0.7,
    "google/gemini-3.1-flash-lite-preview": 0.2,
    "qwen/qwen3.5-plus-02-15":              0.4,
    "mistralai/mistral-small-2603":         0.0,
    "openai/gpt-5.4-nano":                  0.5,
    "qwen/qwen3.5-flash-02-23":            -0.1,
    # Currently-enabled vision models
    "google/gemini-3.5-flash":              0.6,
    "google/gemini-3.1-flash-lite":         0.2,
    "x-ai/grok-4.3":                        0.5,
    "perceptron/perceptron-mk1":            0.3,
    "stepfun/step-3.7-flash":               0.1,
    "minimax/minimax-m3":                   0.0,
}


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

    results = []
    for model in model_list:
        bias = MODEL_BIAS.get(model["id"], 0.0)
        pricing = model.get("pricing", {})
        input_rate = pricing.get("input_per_million", 0)
        output_rate = pricing.get("output_per_million", 0)
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
                cost = round(
                    (inp_tokens * input_rate + out_tokens * output_rate)
                    / 1_000_000, 6
                )
                runs.append({
                    "run": run_idx,
                    "error": None,
                    "latency": latency,
                    "tokens": {"input": inp_tokens, "output": out_tokens},
                    "cost": cost,
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
                "prompt": tc["prompt"],
                "reference_answer": tc.get("reference_answer", ""),
                "runs": runs,
                "avg_score": avg,
                "std_dev": std_dev,
                "min_score": round(min(score_values), 2),
                "max_score": round(max(score_values), 2),
            })

        results.append({
            "model_id": model["id"],
            "model_name": model["name"],
            "pricing": pricing,
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
        meta = suite_meta(data.get("suite_name", ""))
        model_ids = {r.get("model_id") for r in data.get("results", []) if r.get("model_id")}
        index.append({
            "filename": filename,
            "run_id": data.get("run_id", ""),
            "suite_name": data.get("suite_name", ""),
            "eval_type": data.get("eval_type", "quality"),
            "modality": meta["modality"],
            "task_type": meta["task_type"],
            "model_count": len(model_ids) if model_ids else len(data.get("results", [])),
            "top_model": model_scores[0] if model_scores else None,
            "score_range": [model_scores[-1]["avg"], model_scores[0]["avg"]] if model_scores else None,
        })
    return index


# Production-viability latency cutoff (seconds). Keep in sync with the frontend constant.
PRODUCTION_LATENCY_CUTOFF = 15


def _model_summary(model_result: dict) -> dict:
    """Per-model summary for a single run. Mirrors modelSummaries() in site/demo/index.html."""
    test_results = model_result.get("test_results", [])
    scores = [tr["avg_score"] for tr in test_results if tr.get("avg_score", 0) > 0]
    stds = [tr["std_dev"] for tr in test_results if tr.get("std_dev", 0) > 0]
    lats, tokens, cost = [], 0, 0.0
    for tr in test_results:
        for r in tr.get("runs", []):
            if r.get("latency"):
                lats.append(r["latency"])
            tok = r.get("tokens") or {}
            tokens += (tok.get("input", 0) or 0) + (tok.get("output", 0) or 0)
            cost += r.get("cost", 0)

    def mean(xs): return sum(xs) / len(xs) if xs else 0.0

    return {
        "avg":    round(mean(scores), 1) if scores else 0.0,
        "min":    round(min(scores), 1) if scores else 0.0,
        "max":    round(max(scores), 1) if scores else 0.0,
        "std":    round(mean(stds), 2) if stds else 0.0,
        "lat":    round(mean(lats), 1) if lats else 0.0,
        "cost":   round(cost, 4),
        "tokens": tokens,
        "errors": model_result.get("errors", 0),
    }


def build_leaderboard(reports: list[tuple[str, dict]]) -> dict:
    """
    Materialize the cross-run leaderboard at build time.

    For models that appear in multiple runs, scalar metrics are averaged across
    runs (mean-of-means), tokens and errors are summed, and min/max are taken
    as the extremes across runs. Preserves the exact semantics of the prior
    client-side aggregateAllRuns() function so we can delete it.
    """
    model_map: dict[str, dict] = {}
    for _, data in reports:
        for mr in data.get("results", []):
            mid = mr["model_id"]
            summary = _model_summary(mr)
            if mid not in model_map:
                model_map[mid] = {"id": mid, "name": mr["model_name"], "runs": []}
            model_map[mid]["runs"].append({"runId": data.get("run_id", ""), "summary": summary})

    def mean(xs): return sum(xs) / len(xs) if xs else 0.0

    aggregated = []
    for entry in model_map.values():
        rs = [r["summary"] for r in entry["runs"]]
        avg = round(mean([s["avg"] for s in rs]), 2)
        lat = round(mean([s["lat"] for s in rs]), 1)
        std = round(mean([s["std"] for s in rs]), 2)
        aggregated.append({
            "id":     entry["id"],
            "name":   entry["name"],
            "avg":    avg,
            "min":    round(min(s["min"] for s in rs), 1),
            "max":    round(max(s["max"] for s in rs), 1),
            "std":    std,
            "lat":    lat,
            "cost":   round(sum(s["cost"] for s in rs), 4),
            "tokens": sum(s["tokens"] for s in rs),
            "errors": sum(s["errors"] for s in rs),
            "runCount": len(rs),
            "runIds":   [r["runId"] for r in entry["runs"]],
            "productionViable": lat <= PRODUCTION_LATENCY_CUTOFF,
        })
    aggregated.sort(key=lambda m: m["avg"], reverse=True)

    # Calibration: models appearing in >1 run — small deltas confirm runs are comparable.
    calibration = []
    for entry in model_map.values():
        if len(entry["runs"]) >= 2:
            avgs = [r["summary"]["avg"] for r in entry["runs"]]
            calibration.append({
                "name": entry["name"],
                "delta": round(max(avgs) - min(avgs), 2),
                "runCount": len(entry["runs"]),
            })
    calibration.sort(key=lambda c: c["delta"])

    # Test-case count: read from first report's first model (matches prior JS).
    test_case_count = 0
    if reports:
        first_results = reports[0][1].get("results", [])
        if first_results:
            test_case_count = len(first_results[0].get("test_results", []))

    return {
        "aggregated":    aggregated,
        "calibration":   calibration,
        "reportCount":   len(reports),
        "testCaseCount": test_case_count,
        "productionLatencyCutoff": PRODUCTION_LATENCY_CUTOFF,
    }


def _load_classification_scorer():
    """Import scripts/score_image_safety.py by path (scripts/ isn't a package)."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "score_image_safety", ROOT / "scripts" / "score_image_safety.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# Deterministic over-rejection model for the seeded demo: a model over-rejects a
# SAFE case when its "strictness" (1 - leniency, derived from quality bias) meets
# the case's threshold. Harder false-positive traps have lower thresholds (more
# models trip on them). Deterministic — no RNG — so the demo is reproducible and
# the per-model spread is stable.
_CASE_BLOCK_THRESHOLD = {
    "is_001": 1.10,  # clean label close-up — never over-rejected
    "is_002": 0.70,  # clean bottle label
    "is_003": 0.42,  # messy mirror selfie, clothed
    "is_004": 0.18,  # shirtless grooming — the classic false-positive trap
}


def generate_image_safety_report(suite_path: Path, run_id: str, vision_models: list, seed: int) -> dict:
    """Synthesize a deterministic SAFE-only image_safety run with raw `output`.

    Every committed case is should_pass=true, so the only error a model can make
    here is over-rejection (a false block of a legitimate photo). Stronger models
    over-reject less. Output is a strict JSON verdict so the real classification
    scorer (scripts/score_image_safety.py) can grade it unchanged.
    """
    rng = random.Random(seed)
    suite = json.loads(suite_path.read_text())
    weights = suite.get("scoring_weights", {})
    dims = list(weights.keys())

    results = []
    for model in vision_models:
        # Map the model's quality bias into a "leniency" (0..1): higher = blocks less.
        bias = MODEL_BIAS.get(model["id"], 0.0)
        leniency = min(1.0, max(0.0, 0.42 + bias))

        pricing = model.get("pricing", {})
        in_rate = pricing.get("input_per_million", 0)
        out_rate = pricing.get("output_per_million", 0)
        test_results = []
        for tc in suite["test_cases"]:
            tc_id = tc["id"]
            strictness = 1.0 - leniency
            blocked = strictness >= _CASE_BLOCK_THRESHOLD.get(tc_id, 1.10)
            if blocked:
                verdict = {
                    "safe_for_work": False,
                    "category": "borderline" if tc_id == "is_004" else "explicit",
                    "confidence": rng.randint(55, 80),
                    "reason": "Visible person/skin in frame; flagged for review.",
                }
            else:
                cat = {"is_001": "clean", "is_002": "clean", "is_003": "messy", "is_004": "borderline"}.get(tc_id, "clean")
                verdict = {
                    "safe_for_work": True,
                    "category": cat,
                    "confidence": rng.randint(82, 98),
                    "reason": "Good-faith product photo; product clearly visible.",
                }
            # Quality dims (output-contract adherence) — kept for report-shape parity.
            scores = {d: round(min(10.0, max(1.0, rng.uniform(7.0, 9.5) + bias)), 1) for d in dims}
            ws = weighted_score(scores, weights) if dims else 0.0
            latency = round(rng.uniform(0.8, 4.5), 2)
            inp_tokens = rng.randint(800, 1400)  # image tokens dominate
            out_tokens = rng.randint(40, 90)
            cost = round((inp_tokens * in_rate + out_tokens * out_rate) / 1_000_000, 6)
            run = {
                "run": 0, "error": None, "latency": latency,
                "tokens": {"input": inp_tokens, "output": out_tokens}, "cost": cost,
                "scores": scores, "weighted_score": ws,
                "validation": {"passed": True, "failures": []},
                "output": json.dumps(verdict),
            }
            test_results.append({
                "test_case_id": tc_id, "test_case_name": tc["name"],
                "category": tc["category"], "prompt": tc["prompt"],
                "reference_answer": tc.get("reference_answer", ""),
                "runs": [run], "avg_score": ws, "std_dev": 0.0,
                "min_score": ws, "max_score": ws,
            })
        results.append({
            "model_id": model["id"], "model_name": model["name"],
            "pricing": pricing, "test_results": test_results, "errors": 0,
        })

    return {
        "run_id": run_id, "suite_name": suite["suite_name"],
        "runs_per_test": 1,
        "judge_models": ["anthropic/claude-sonnet-4.6", "openai/gpt-5.4"],
        "results": results,
    }


def _gate_rows(report: dict, classification: dict) -> list:
    """Join the classification summary with per-model latency/cost from the report."""
    lat_cost = {}
    for mr in report.get("results", []):
        lats, cost = [], 0.0
        for tr in mr.get("test_results", []):
            for r in tr.get("runs", []):
                if r.get("latency"):
                    lats.append(r["latency"])
                cost += r.get("cost", 0)
        lat_cost[mr["model_id"]] = {
            "lat": round(sum(lats) / len(lats), 1) if lats else 0.0,
            "cost": round(cost, 4),
        }
    rows = []
    for m in classification.get("models", []):
        lc = lat_cost.get(m["model_id"], {"lat": 0.0, "cost": 0.0})
        rows.append({
            "id": m["model_id"], "name": m["model_name"],
            "n": m["scored_cases"], "tp": m["tp"], "tn": m["tn"],
            "fp": m["fp"], "fn": m["fn"],
            "good_total": m["good_total"], "unsafe_total": m["unsafe_total"],
            "accuracy": m["accuracy"], "precision": m["precision"], "recall": m["recall"],
            "good_reject_rate": m["good_reject_rate"],
            "unsafe_pass_rate": m["unsafe_pass_rate"],
            "refused": m["refused"], "malformed": m["malformed"],
            "lat": lc["lat"], "cost": lc["cost"],
        })
    # Best gate first: lowest good-reject, then highest accuracy.
    rows.sort(key=lambda r: ((r["good_reject_rate"] if r["good_reject_rate"] is not None else 1.0),
                             -(r["accuracy"] or 0)))
    return rows


def _agentic_rows(pairs: list) -> list:
    """Aggregate agentic reports into a per-model efficiency leaderboard.

    Agentic reports have no test_results/avg_score to average — results[] is a
    flat list of per (model, test_case, run) records with a deterministic
    success flag plus efficiency metrics. Mirrors _gate_rows()'s role for the
    classification-gate category: a dedicated aggregation, not a reuse of
    build_leaderboard()'s quality-score math.
    """
    by_model: dict[str, dict] = {}
    for _, data in pairs:
        for r in data.get("results", []):
            mid = r.get("model_id")
            if mid is None:
                continue
            by_model.setdefault(mid, {"id": mid, "name": r.get("model_name", mid), "runs": []})["runs"].append(r)

    rows = []
    for entry in by_model.values():
        runs = entry["runs"]
        n = len(runs)
        if not n:
            continue
        tokens_sum = sum((r.get("tokens") or {}).get("input", 0) + (r.get("tokens") or {}).get("output", 0) for r in runs)
        rows.append({
            "id": entry["id"], "name": entry["name"], "n": n,
            "successRate": round(sum(1 for r in runs if r.get("success")) / n, 4),
            "avgModelCalls": round(sum(r.get("model_calls", 0) for r in runs) / n, 1),
            "avgToolCalls": round(sum(r.get("tool_calls", 0) for r in runs) / n, 1),
            "avgTokens": round(tokens_sum / n),
            "avgCost": round(sum(r.get("cost", 0) for r in runs) / n, 4),
            "avgLatency": round(sum(r.get("latency", 0) for r in runs) / n, 1),
        })
    # Best first: highest success rate, then fewest tool calls (efficiency).
    rows.sort(key=lambda r: (-r["successRate"], r["avgToolCalls"]))
    return rows


def build_categories(pairs: list, gate_data: dict | None = None) -> list:
    """Group runs into lmarena-style category tabs by (modality, task_type).

    Quality categories carry the standard 1-10 aggregated leaderboard; the
    vision classification-gate category carries confusion-matrix metrics;
    the agentic category carries success-rate/efficiency metrics.
    """
    groups: dict[tuple, list] = {}
    for filename, data in pairs:
        meta = suite_meta(data.get("suite_name", ""))
        groups.setdefault((meta["modality"], meta["task_type"]), []).append((filename, data))

    label_word = {"text": "Text", "vision": "Vision",
                  "generation": "Generation", "classification": "Classification",
                  "tool_use": "Agentic"}
    categories = []
    for (modality, task_type), grp in groups.items():
        suites = sorted({d.get("suite_name", "") for _, d in grp})
        is_gate = gate_data is not None and gate_data["suite_name"] in suites
        is_agentic = any(d.get("eval_type") == "agentic" for _, d in grp)
        cat = {
            "key": f"{modality}-{task_type}",
            "label": f"{label_word[modality]} · {label_word[task_type]}",
            "modality": modality, "task_type": task_type,
            "suites": suites,
            "reportCount": len(grp),
            "productionLatencyCutoff": PRODUCTION_LATENCY_CUTOFF,
            "metric_kind": "agentic" if is_agentic else ("classification_gate" if is_gate else "quality"),
        }
        if is_agentic:
            cat["agentic"] = _agentic_rows(grp)
            cat["isNew"] = True
        elif is_gate:
            cat["gate"] = _gate_rows(gate_data["report"], gate_data["classification"])
            cat["gateNote"] = (
                "Committed set is SAFE-only, so unsafe_total=0 and the dangerous "
                "Unsafe-Pass rate is not measurable here (shown as —). Only the "
                "over-rejection side (Good-Reject) is graded. Add a private, "
                "access-controlled unsafe set to measure the gate FNR."
            )
        else:
            lb = build_leaderboard(grp)
            cat["leaderboard"] = lb["aggregated"]
            cat["calibration"] = lb["calibration"]
            cat["testCaseCount"] = lb["testCaseCount"]
        categories.append(cat)

    # Stable, readable order: text-gen, text-classification, vision-*, agentic, then rest.
    order = {"text-generation": 0, "text-classification": 1,
             "vision-classification": 2, "vision-generation": 3, "text-tool_use": 4}
    categories.sort(key=lambda c: order.get(c["key"], 99))
    return categories


def compose_leaderboard(pairs_sorted: list, gate_data: dict | None = None) -> dict:
    """Build the full leaderboard payload: lmarena-style `categories` plus legacy
    `aggregated`/`calibration` fields (over quality runs) for back-compat.

    Shared by both the synthetic (main) and --from-reports build paths so the two
    can't diverge in shape.
    """
    categories = build_categories(pairs_sorted, gate_data)
    gate_suite = gate_data["suite_name"] if gate_data else None
    quality_pairs = [(f, d) for f, d in pairs_sorted
                      if d.get("suite_name") != gate_suite and d.get("eval_type") != "agentic"]
    legacy = (build_leaderboard(quality_pairs) if quality_pairs
              else {"aggregated": [], "calibration": [], "reportCount": 0, "testCaseCount": 0})
    return {
        "categories": categories,
        "productionLatencyCutoff": PRODUCTION_LATENCY_CUTOFF,
        "aggregated": legacy["aggregated"],
        "calibration": legacy["calibration"],
        "reportCount": legacy["reportCount"],
        "testCaseCount": legacy["testCaseCount"],
    }


def _backfill_report(data: dict, models_data: dict) -> None:
    """Add cost and prompt fields to reports that predate those features."""
    pricing_map = {
        m["id"]: m.get("pricing", {})
        for m in models_data.get("models", [])
    }

    # Load suite to get prompts and reference answers
    suite_name = data.get("suite_name", "")
    suite_dir = ROOT / "evals"
    tc_map = {}
    for candidate in [suite_dir / f"{suite_name}.json", suite_dir / "suite.json"]:
        if candidate.exists():
            suite = json.loads(candidate.read_text())
            tc_map = {
                tc["id"]: tc for tc in suite.get("test_cases", [])
            }
            break

    for mr in data.get("results", []):
        if "pricing" not in mr:
            mr["pricing"] = pricing_map.get(mr["model_id"], {})
        p = mr["pricing"]
        in_rate = p.get("input_per_million", 0)
        out_rate = p.get("output_per_million", 0)
        for tr in mr.get("test_results", []):
            # Backfill prompt and reference_answer
            if "prompt" not in tr:
                tc = tc_map.get(tr.get("test_case_id", ""), {})
                tr["prompt"] = tc.get("prompt", "")
                tr["reference_answer"] = tc.get(
                    "reference_answer", ""
                )
            # Backfill cost
            for run in tr.get("runs", []):
                if "cost" not in run:
                    tok = run.get("tokens") or {}
                    run["cost"] = round(
                        (tok.get("input", 0) * in_rate
                         + tok.get("output", 0) * out_rate)
                        / 1_000_000, 6
                    )


# Curated allowlist of report filenames to publish to the public demo, newest-first.
# Gatekeeping is explicit on purpose: reports/ is the full private audit trail, and
# only the runs named here are surfaced on the public site (so failed, token-capped,
# or unvetted runs never leak). Set to None to fall back to "newest N quality reports
# by run timestamp".
DEMO_ALLOWLIST = [
    "swms_safety_generator_20260623_121911.json",
    "biology_over_refusal_20260610_082550.json",
    "school_classifier_20260416_195602.json",
    "swms_safety_generator_20260410_162637.json",
    "health_safety_agentic_20260701_081224.json",
]
DEMO_FALLBACK_LIMIT = 6  # used only when DEMO_ALLOWLIST is None


def from_real_reports(reports_dir: Path) -> bool:
    # This demo dashboard renders quality / classification categories only.
    # Exclude classification sidecars and safety (jailbreak) reports — the latter
    # have a different report shape (gate_result, no per-dimension avg_score) that
    # the quality leaderboard can't summarize.
    def _is_quality_report(p: Path) -> bool:
        if p.name.endswith("_classification.json"):
            return False
        try:
            return json.loads(p.read_text()).get("eval_type", "quality") != "safety"
        except (json.JSONDecodeError, OSError):
            return False

    def _is_renderable(p: Path) -> bool:
        # Allowlisted runs may be safety-typed (e.g. over-refusal) yet still carry
        # per-test avg_score, so they render on the quality leaderboard. Agentic
        # reports carry no avg_score at all (flat success/tool_calls records) but
        # render via their own category — only true gate-only reports (no
        # avg_score) and classification sidecars can't render.
        if p.name.endswith("_classification.json"):
            return False
        try:
            data = json.loads(p.read_text())
        except (json.JSONDecodeError, OSError):
            return False
        if data.get("eval_type") == "agentic":
            return bool(data.get("results"))
        for r in data.get("results", []):
            for tr in r.get("test_results", []):
                if "avg_score" in tr:
                    return True
        return False

    if DEMO_ALLOWLIST is not None:
        present = {p.name: p for p in reports_dir.glob("*.json")}
        files = []
        for name in DEMO_ALLOWLIST:
            p = present.get(name)
            if p is None:
                print(f"  WARNING: allowlisted report not found, skipped: {name}")
            elif not _is_renderable(p):
                print(f"  WARNING: allowlisted report not renderable (no avg_score / sidecar), skipped: {name}")
            else:
                files.append(p)
    else:
        quality = {p.name: p for p in reports_dir.glob("*.json") if _is_quality_report(p)}
        # Newest-first by the YYYYMMDD_HHMMSS timestamp embedded in the filename.
        files = sorted(
            quality.values(), key=lambda p: p.stem.split("_")[-2:], reverse=True
        )[:DEMO_FALLBACK_LIMIT]

    if not files:
        return False

    models_data = json.loads((ROOT / "models.json").read_text())
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    pairs = []
    for f in files:
        data = json.loads(f.read_text())
        _backfill_report(data, models_data)
        dest = OUT_DIR / f.name
        dest.write_text(json.dumps(data, indent=2))
        pairs.append((f.name, data))
        print(f"  Copied {f.name}")

    index = build_index(pairs)
    (OUT_DIR / "index.json").write_text(json.dumps(index, indent=2))
    print(f"  Wrote index.json ({len(index)} entries)")

    # Real reports may include an image_safety run; if a matching classification
    # sidecar exists alongside it, wire it into the gate category.
    gate_data = None
    for filename, data in pairs:
        if suite_meta(data.get("suite_name", "")) == {"modality": "vision", "task_type": "classification"}:
            sidecar = reports_dir / f"{Path(filename).stem}_classification.json"
            if sidecar.exists():
                gate_data = {"suite_name": data["suite_name"], "report": data,
                             "classification": json.loads(sidecar.read_text())}
            break

    leaderboard = compose_leaderboard(list(reversed(pairs)), gate_data)
    (OUT_DIR / "leaderboard.json").write_text(json.dumps(leaderboard, indent=2))
    print(f"  Wrote leaderboard.json ({len(leaderboard['categories'])} categories)")
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
    vision_models = [m for m in models if m.get("vision")]

    # Quality suites spanning two categories: Text·Generation and Text·Classification.
    suites = [
        (ROOT / "evals" / "getting_started.json",   "20260330_120000", 42),
        (ROOT / "evals" / "suite.json",             "20260315_090000", 99),
        (ROOT / "evals" / "school_classifier.json", "20260416_195602", 7),
    ]

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    pairs = []
    for suite_path, run_id, seed in suites:
        if not suite_path.exists():
            continue
        report = generate_report(suite_path, run_id, models, seed)
        filename = f"{report['suite_name']}_{run_id}.json"
        (OUT_DIR / filename).write_text(json.dumps(report, indent=2))
        pairs.append((filename, report))
        print(f"  Wrote {filename}")

    # Vision·Classification: SAFE-only image_safety run, graded by the real scorer.
    gate_data = None
    is_suite = ROOT / "evals" / "image_safety.json"
    if is_suite.exists() and vision_models:
        is_report = generate_image_safety_report(is_suite, "20260603_140000", vision_models, 2026)
        is_filename = f"{is_report['suite_name']}_20260603_140000.json"
        (OUT_DIR / is_filename).write_text(json.dumps(is_report, indent=2))
        pairs.append((is_filename, is_report))
        print(f"  Wrote {is_filename}")

        scorer = _load_classification_scorer()
        labels = json.loads((EVALS_DIR / "image_safety_labels.json").read_text())
        classification = scorer.score_report(is_report, labels)
        (OUT_DIR / f"{is_report['suite_name']}_20260603_140000_classification.json").write_text(
            json.dumps(classification, indent=2))
        gate_data = {"suite_name": is_report["suite_name"], "report": is_report,
                     "classification": classification}
        print(f"  Wrote {is_report['suite_name']}_20260603_140000_classification.json")

    # index.json sorted newest first (matches dashboard expectation)
    pairs_sorted = list(reversed(pairs))
    index = build_index(pairs_sorted)
    (OUT_DIR / "index.json").write_text(json.dumps(index, indent=2))
    print(f"  Wrote index.json ({len(index)} entries)")

    # Categorized leaderboard (lmarena-style tabs) + legacy back-compat fields.
    leaderboard = compose_leaderboard(pairs_sorted, gate_data)
    (OUT_DIR / "leaderboard.json").write_text(json.dumps(leaderboard, indent=2))
    print(f"  Wrote leaderboard.json ({len(leaderboard['categories'])} categories: "
          f"{', '.join(c['key'] for c in leaderboard['categories'])})")
    print(f"\nDemo data ready in {OUT_DIR.relative_to(ROOT)}/")


if __name__ == "__main__":
    main()
