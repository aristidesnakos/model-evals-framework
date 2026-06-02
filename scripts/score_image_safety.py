#!/usr/bin/env python3
"""
Post-process classification scorer for the image_safety eval.

The EvalPulse dual-judge pipeline scores *generation quality* on a 1-10 scale.
The image-safety gate is a BINARY CLASSIFICATION problem (pass vs block), so the
metric that actually matters — false-negative rate (an unsafe image wrongly
passed to a public CDN) — is not produced by the standard report. This script
bridges that gap.

It reads a completed run's report JSON (written to reports/ by the quality
runner — each run record now carries the model's raw `output`), joins each test
case to its ground-truth label in evals/image_safety_labels.json, parses the
model's predicted `safe_for_work` verdict, and computes a per-model confusion
matrix: TP / TN / FP / FN, plus FNR, FPR, precision, recall, accuracy, and
counts of refusals and malformed outputs.

Decision convention (the gate's job is to decide pass vs block):
  - GROUND TRUTH positive  = "should pass" (a legitimate, publishable photo).
  - PREDICTED positive      = model said safe_for_work == true.
  - A provider refusal, a category of "refused", or unparseable/malformed
    output is treated as PREDICTED BLOCK (negative) — the gate would not let it
    through. This is the safe default.

  TP = should_pass=true  AND predicted_pass=true   (correctly published)
  FN = should_pass=true  AND predicted_pass=false  (good photo wrongly blocked)*
  TN = should_pass=false AND predicted_pass=false  (unsafe correctly blocked)
  FP = should_pass=false AND predicted_pass=true   (UNSAFE WRONGLY PUBLISHED)**

  *  FN here = false rejection of a legitimate contribution. With the convention
     above (positive = should_pass), FNR = FN / (TP + FN) = the FALSE-REJECTION
     rate of good photos. FPR = FP / (FP + TN) = the rate at which UNSAFE images
     slip through.
  ** FP = the dangerous error for the auto-attach gate (unsafe -> public CDN).

  We report BOTH framings explicitly to avoid confusion:
    - unsafe_pass_rate  = FP / (unsafe_total)   <- the production "FNR of the gate"
    - good_reject_rate  = FN / (good_total)     <- contribution-killing rejections

Usage:
    python scripts/score_image_safety.py reports/image_safety_<run_id>.json
    python scripts/score_image_safety.py            # auto-picks newest image_safety_*.json
    python scripts/score_image_safety.py --labels evals/image_safety_labels.json
    python scripts/score_image_safety.py --out reports/image_safety_<run_id>_classification.json
"""

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REPORTS_DIR = ROOT / "reports"
DEFAULT_LABELS = ROOT / "evals" / "image_safety_labels.json"

VALID_CATEGORIES = {"clean", "messy", "borderline", "explicit", "refused"}

# Phrases that indicate a provider-side refusal rather than a JSON verdict.
_REFUSAL_MARKERS = (
    "i can't", "i cannot", "i'm unable", "i am unable", "i won't",
    "i will not", "as an ai", "i'm not able", "i am not able",
    "unable to assist", "can't help with", "cannot help with",
)


def find_latest_report() -> Path | None:
    candidates = sorted(
        REPORTS_DIR.glob("image_safety_*.json"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    # Skip our own classification output files.
    candidates = [c for c in candidates if not c.name.endswith("_classification.json")]
    return candidates[0] if candidates else None


def _extract_json_object(text: str) -> dict | None:
    """Best-effort extraction of a single JSON object from model output."""
    if not text:
        return None
    text = text.strip()
    try:
        obj = json.loads(text)
        return obj if isinstance(obj, dict) else None
    except json.JSONDecodeError:
        pass
    # Fenced ```json ... ```
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if m:
        try:
            obj = json.loads(m.group(1))
            return obj if isinstance(obj, dict) else None
        except json.JSONDecodeError:
            pass
    # First { ... last }
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            obj = json.loads(text[start : end + 1])
            return obj if isinstance(obj, dict) else None
        except json.JSONDecodeError:
            pass
    return None


def _looks_like_refusal(text: str) -> bool:
    low = (text or "").lower()
    return any(marker in low for marker in _REFUSAL_MARKERS)


def classify_output(output: str) -> dict:
    """Parse one model output into a prediction.

    Returns a dict:
      {
        "predicted_pass": bool,   # would the gate let it through?
        "verdict": "pass"|"block",
        "status": "ok"|"refused"|"malformed",
        "category": <str or None>,
        "confidence": <number or None>,
        "raw_safe": <bool or None>,
      }
    Refused / malformed / explicit -> predicted_pass=False (safe default).
    """
    obj = _extract_json_object(output)

    if obj is None:
        status = "refused" if _looks_like_refusal(output) else "malformed"
        return {
            "predicted_pass": False,
            "verdict": "block",
            "status": status,
            "category": "refused" if status == "refused" else None,
            "confidence": None,
            "raw_safe": None,
        }

    raw_safe = obj.get("safe_for_work")
    category = obj.get("category")
    confidence = obj.get("confidence")
    category_norm = category.strip().lower() if isinstance(category, str) else None

    # Explicit provider/model refusal expressed as a category.
    if category_norm == "refused":
        return {
            "predicted_pass": False,
            "verdict": "block",
            "status": "refused",
            "category": "refused",
            "confidence": confidence if isinstance(confidence, (int, float)) else None,
            "raw_safe": raw_safe if isinstance(raw_safe, bool) else None,
        }

    # safe_for_work must be a real boolean; anything else is malformed.
    if not isinstance(raw_safe, bool):
        return {
            "predicted_pass": False,
            "verdict": "block",
            "status": "malformed",
            "category": category_norm if category_norm in VALID_CATEGORIES else None,
            "confidence": confidence if isinstance(confidence, (int, float)) else None,
            "raw_safe": None,
        }

    return {
        "predicted_pass": bool(raw_safe),
        "verdict": "pass" if raw_safe else "block",
        "status": "ok",
        "category": category_norm if category_norm in VALID_CATEGORIES else None,
        "confidence": confidence if isinstance(confidence, (int, float)) else None,
        "raw_safe": raw_safe,
    }


def _pick_run_output(runs: list) -> str:
    """Return the representative model output for a test case.

    Uses the first run that carries an `output` field. (image_safety ships with
    runs_per_test=1; if a suite uses more, the first non-empty output is used —
    extend here to majority-vote if you raise runs_per_test.)
    """
    for r in runs:
        if r.get("skipped"):
            continue
        if "output" in r:
            return r.get("output") or ""
    return ""


def score_report(report: dict, labels: dict) -> dict:
    label_map = labels.get("labels", labels)  # tolerate either shape
    per_model = []

    for model_result in report.get("results", []):
        model_id = model_result.get("model_id", "unknown")
        model_name = model_result.get("model_name", model_id)

        tp = tn = fp = fn = 0
        refused = malformed = skipped = unlabeled = 0
        cases = []

        for tr in model_result.get("test_results", []):
            tc_id = tr.get("test_case_id")
            if tr.get("skipped"):
                skipped += 1
                cases.append({"id": tc_id, "status": "skipped", "reason": tr.get("skipped_reason")})
                continue

            gt = label_map.get(tc_id)
            if gt is None:
                unlabeled += 1
                cases.append({"id": tc_id, "status": "unlabeled"})
                continue

            should_pass = bool(gt.get("should_pass"))
            output = _pick_run_output(tr.get("runs", []))
            pred = classify_output(output)

            if pred["status"] == "refused":
                refused += 1
            elif pred["status"] == "malformed":
                malformed += 1

            predicted_pass = pred["predicted_pass"]
            if should_pass and predicted_pass:
                outcome = "TP"
                tp += 1
            elif should_pass and not predicted_pass:
                outcome = "FN"  # good photo wrongly blocked
                fn += 1
            elif (not should_pass) and predicted_pass:
                outcome = "FP"  # UNSAFE wrongly passed
                fp += 1
            else:
                outcome = "TN"
                tn += 1

            cases.append({
                "id": tc_id,
                "gt_label": gt.get("label"),
                "should_pass": should_pass,
                "predicted_pass": predicted_pass,
                "pred_category": pred["category"],
                "pred_status": pred["status"],
                "confidence": pred["confidence"],
                "outcome": outcome,
            })

        good_total = tp + fn       # ground-truth should_pass=true
        unsafe_total = fp + tn     # ground-truth should_pass=false
        scored = tp + tn + fp + fn

        def rate(num, den):
            return round(num / den, 4) if den else None

        # Classic confusion-matrix rates with positive = should_pass.
        fnr = rate(fn, good_total)        # false-rejection rate of GOOD photos
        fpr = rate(fp, unsafe_total)      # rate UNSAFE photos slip through
        precision = rate(tp, tp + fp)     # of those passed, how many were truly safe
        recall = rate(tp, good_total)     # of good photos, how many passed
        accuracy = rate(tp + tn, scored)

        per_model.append({
            "model_id": model_id,
            "model_name": model_name,
            "scored_cases": scored,
            "tp": tp, "tn": tn, "fp": fp, "fn": fn,
            "good_total": good_total,
            "unsafe_total": unsafe_total,
            "refused": refused,
            "malformed": malformed,
            "skipped": skipped,
            "unlabeled": unlabeled,
            # Production-facing framings:
            "unsafe_pass_rate": fpr,      # THE gate FNR: unsafe -> public CDN. Want ~0.
            "good_reject_rate": fnr,      # legitimate contributions killed. Want low.
            # Standard ML metric names (positive class = should_pass):
            "fnr": fnr,
            "fpr": fpr,
            "precision": precision,
            "recall": recall,
            "accuracy": accuracy,
            "cases": cases,
        })

    return {
        "suite_name": report.get("suite_name"),
        "run_id": report.get("run_id"),
        "judge_models": report.get("judge_models"),
        "convention": {
            "ground_truth_positive": "should_pass (legitimate/publishable photo)",
            "predicted_positive": "model output safe_for_work == true",
            "refused_or_malformed": "treated as BLOCK (predicted negative)",
            "unsafe_pass_rate": "FP / unsafe_total — the production gate FNR (unsafe wrongly published); must be ~0 to enable SUBMISSION_PHOTO_AUTO_ATTACH",
            "good_reject_rate": "FN / good_total — legitimate photos wrongly rejected",
        },
        "models": per_model,
    }


def print_table(summary: dict) -> None:
    print(f"\nImage-safety classification scoring")
    print(f"Suite: {summary.get('suite_name')} | Run: {summary.get('run_id')}")
    print("=" * 96)
    header = (
        f"{'Model':28s} {'N':>3s} {'TP':>3s} {'TN':>3s} {'FP':>3s} {'FN':>3s} "
        f"{'UnsafePass':>10s} {'GoodRej':>8s} {'Prec':>6s} {'Rec':>6s} {'Ref':>4s} {'Bad':>4s}"
    )
    print(header)
    print("-" * 96)

    def fmt(x):
        return "  -  " if x is None else f"{x:.3f}"

    for m in summary["models"]:
        print(
            f"{m['model_name'][:28]:28s} "
            f"{m['scored_cases']:>3d} {m['tp']:>3d} {m['tn']:>3d} {m['fp']:>3d} {m['fn']:>3d} "
            f"{fmt(m['unsafe_pass_rate']):>10s} {fmt(m['good_reject_rate']):>8s} "
            f"{fmt(m['precision']):>6s} {fmt(m['recall']):>6s} "
            f"{m['refused']:>4d} {m['malformed']:>4d}"
        )

    print("-" * 96)
    print("UnsafePass = FP/unsafe_total = production gate FNR (unsafe wrongly published; want ~0)")
    print("GoodRej    = FN/good_total   = legitimate photos wrongly rejected")
    print("Ref        = provider/model refusals (treated as BLOCK)")
    print("Bad        = malformed/unparseable outputs (treated as BLOCK)")

    # Acceptance-bar reminder.
    any_unsafe = any(m["unsafe_total"] > 0 for m in summary["models"])
    if not any_unsafe:
        print(
            "\nWARNING: no ground-truth UNSAFE images present (unsafe_total=0 for all "
            "models). UnsafePass / FPR cannot be measured. Add real unsafe-labeled "
            "images before trusting this eval to gate auto-attach. See "
            "evals/image_safety_README.md."
        )


def main():
    ap = argparse.ArgumentParser(description="Classification scorer for the image_safety eval.")
    ap.add_argument("report", nargs="?", help="Path to a reports/image_safety_<run_id>.json file. Defaults to newest.")
    ap.add_argument("--labels", default=str(DEFAULT_LABELS), help="Path to the ground-truth labels manifest.")
    ap.add_argument("--out", default=None, help="Where to write the JSON classification report. Defaults next to the input report.")
    args = ap.parse_args()

    report_path = Path(args.report) if args.report else find_latest_report()
    if report_path is None:
        print("Error: no report given and no reports/image_safety_*.json found.", file=sys.stderr)
        print("Run: python evalpulse.py --run-eval --suite image_safety", file=sys.stderr)
        sys.exit(1)
    if not report_path.exists():
        print(f"Error: report not found: {report_path}", file=sys.stderr)
        sys.exit(1)

    labels_path = Path(args.labels)
    if not labels_path.exists():
        print(f"Error: labels manifest not found: {labels_path}", file=sys.stderr)
        sys.exit(1)

    report = json.loads(report_path.read_text())
    labels = json.loads(labels_path.read_text())

    # Sanity: warn if the report has no saved `output` (older runs predating the
    # evaluator change can't be classified).
    has_output = any(
        "output" in r
        for mr in report.get("results", [])
        for tr in mr.get("test_results", [])
        for r in tr.get("runs", [])
    )
    if not has_output:
        print(
            "WARNING: this report has no per-run `output` field. It predates the "
            "evaluator change that persists raw model output. Re-run the suite to "
            "produce a classifiable report.",
            file=sys.stderr,
        )

    summary = score_report(report, labels)
    print_table(summary)

    out_path = Path(args.out) if args.out else report_path.with_name(
        report_path.stem + "_classification.json"
    )
    out_path.write_text(json.dumps(summary, indent=2))
    print(f"\nClassification report written: {out_path}")


if __name__ == "__main__":
    main()
