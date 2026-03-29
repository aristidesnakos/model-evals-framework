"""
Validates evaluation suite JSON files before running.
Catches structural errors and warns about potential issues.
"""

import json
from pathlib import Path

EVALS_DIR = Path(__file__).parent.parent / "evals"


class ValidationResult:
    def __init__(self, suite_path: str):
        self.suite_path = suite_path
        self.errors: list[str] = []
        self.warnings: list[str] = []

    @property
    def is_valid(self) -> bool:
        return len(self.errors) == 0

    def print_report(self) -> None:
        print(f"Validating suite: {self.suite_path}")
        print("=" * 50)

        if self.errors:
            print(f"\nERRORS ({len(self.errors)}):")
            for i, err in enumerate(self.errors, 1):
                print(f"  [{i}] {err}")

        if self.warnings:
            print(f"\nWARNINGS ({len(self.warnings)}):")
            for i, warn in enumerate(self.warnings, 1):
                print(f"  [{i}] {warn}")

        if not self.errors and not self.warnings:
            print("\nNo issues found.")

        print()
        if self.is_valid:
            suite_name = Path(self.suite_path).stem
            print(f"Result: VALID -- suite is ready to run.")
            print(f"Run with: python evalpulse.py --run-eval --suite {suite_name}")
        else:
            print(f"Result: INVALID -- fix {len(self.errors)} error(s) before running.")


def validate_suite(suite_name: str) -> ValidationResult:
    """Validate a suite JSON file. Returns ValidationResult."""
    suite_file = EVALS_DIR / f"{suite_name}.json"
    result = ValidationResult(str(suite_file))

    # File existence
    if not suite_file.exists():
        result.errors.append(
            f"File not found: {suite_file}. "
            f"Run 'python evalpulse.py init' to create a suite."
        )
        return result

    # Valid JSON
    try:
        with open(suite_file) as f:
            suite = json.load(f)
    except json.JSONDecodeError as e:
        result.errors.append(f"Invalid JSON: {e}")
        return result

    if not isinstance(suite, dict):
        result.errors.append("Suite file must contain a JSON object, not an array or scalar.")
        return result

    # Required top-level fields
    for field in ("suite_name", "scoring_weights", "test_cases"):
        if field not in suite:
            result.errors.append(f"Missing required field: '{field}'")

    if result.errors:
        return result

    # scoring_weights validation
    weights = suite["scoring_weights"]
    if not isinstance(weights, dict) or not weights:
        result.errors.append("'scoring_weights' must be a non-empty object.")
    else:
        total = sum(weights.values())
        if not (0.95 <= total <= 1.05):
            result.errors.append(
                f"scoring_weights sum to {total:.2f} (expected ~1.0). "
                f"Adjust weights so they add up to 1.0."
            )

    # test_cases validation
    test_cases = suite["test_cases"]
    if not isinstance(test_cases, list) or len(test_cases) == 0:
        result.errors.append("'test_cases' must be a non-empty array.")
        return result

    seen_ids = set()
    required_tc_fields = ("id", "name", "category", "prompt")

    for i, tc in enumerate(test_cases):
        label = tc.get("name") or tc.get("id") or f"test_cases[{i}]"

        # Required fields
        for field in required_tc_fields:
            if field not in tc or not tc[field]:
                result.errors.append(f"Test case '{label}': missing required field '{field}'")

        # Unique IDs
        tc_id = tc.get("id")
        if tc_id:
            if tc_id in seen_ids:
                result.errors.append(f"Test case '{label}': duplicate id '{tc_id}'")
            seen_ids.add(tc_id)

        # Prompt quality warnings
        prompt = tc.get("prompt", "")
        if prompt and len(prompt) < 50:
            result.warnings.append(
                f"Test case '{label}': prompt is only {len(prompt)} characters "
                f"(may be too vague for meaningful evaluation)"
            )

        # Validation block warnings
        validation = tc.get("validation", {})
        must_contain = validation.get("must_contain", [])
        if len(must_contain) > 20:
            result.warnings.append(
                f"Test case '{label}': {len(must_contain)} must_contain terms "
                f"(may be overly restrictive)"
            )

        min_length = validation.get("min_length")
        if min_length is not None and (not isinstance(min_length, int) or min_length < 0):
            result.errors.append(
                f"Test case '{label}': min_length must be a positive integer, got {min_length}"
            )

        # Missing optional fields that improve judge quality
        if "reference_answer" not in tc:
            result.warnings.append(
                f"Test case '{label}': no reference_answer provided "
                f"(judges will have less context for scoring)"
            )

        if "scoring_criteria" not in tc:
            result.warnings.append(
                f"Test case '{label}': no scoring_criteria provided "
                f"(judges will use generic criteria)"
            )
        elif isinstance(tc.get("scoring_criteria"), dict) and isinstance(weights, dict):
            tc_dims = set(tc["scoring_criteria"].keys())
            weight_dims = set(weights.keys())
            missing = weight_dims - tc_dims
            if missing:
                result.warnings.append(
                    f"Test case '{label}': scoring_criteria missing dimensions: "
                    f"{', '.join(sorted(missing))}"
                )

    # Optional field warnings
    if "runs_per_test" not in suite:
        result.warnings.append("'runs_per_test' not specified (will default to 3)")

    if "description" not in suite:
        result.warnings.append(
            "'description' not specified (judges will use a generic preamble). "
            "Add a description for better domain-specific scoring."
        )

    return result
