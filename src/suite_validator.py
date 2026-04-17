"""
Validates evaluation suite JSON files before running.
Catches structural errors and warns about potential issues.
"""

import json
import re
from pathlib import Path

EVALS_DIR = Path(__file__).parent.parent / "evals"

_SUPPORTED_IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".gif"}
_HEX_COLOR_RE = re.compile(r"^#?([0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")


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

        # Vision / color-palette specific fields (only when image_path is set)
        if "image_path" in tc:
            image_path_raw = tc.get("image_path")
            if not isinstance(image_path_raw, str) or not image_path_raw.strip():
                result.errors.append(
                    f"Test case '{label}': 'image_path' must be a non-empty string "
                    f"relative to evals/ (e.g. 'assets/color_palette/sunset.png')"
                )
            else:
                image_file = EVALS_DIR / image_path_raw
                suffix = image_file.suffix.lower()
                if suffix not in _SUPPORTED_IMAGE_SUFFIXES:
                    result.errors.append(
                        f"Test case '{label}': image '{image_path_raw}' has "
                        f"unsupported extension '{suffix}'. "
                        f"Supported: {sorted(_SUPPORTED_IMAGE_SUFFIXES)}"
                    )
                elif not image_file.exists():
                    result.errors.append(
                        f"Test case '{label}': image file not found at {image_file}. "
                        f"Drop the file into evals/{image_path_raw.rsplit('/', 1)[0] if '/' in image_path_raw else ''}."
                    )

            expected_colors = tc.get("expected_colors")
            if not isinstance(expected_colors, list) or not expected_colors:
                result.errors.append(
                    f"Test case '{label}': vision test cases must declare "
                    f"'expected_colors' as a non-empty list of hex codes "
                    f"(e.g. [\"#ff0000\", \"#00ff00\"])"
                )
            else:
                for idx, code in enumerate(expected_colors):
                    if not isinstance(code, str) or not _HEX_COLOR_RE.match(code.strip()):
                        result.errors.append(
                            f"Test case '{label}': expected_colors[{idx}] = "
                            f"{code!r} is not a valid hex color "
                            f"(expected '#rrggbb' or '#rgb')"
                        )

            tol = tc.get("color_tolerance")
            if tol is not None:
                if not isinstance(tol, (int, float)) or tol < 0 or tol > 100:
                    result.errors.append(
                        f"Test case '{label}': color_tolerance must be a number "
                        f"in [0, 100] (CIEDE2000 units), got {tol!r}"
                    )
                elif tol > 25:
                    result.warnings.append(
                        f"Test case '{label}': color_tolerance={tol} is very "
                        f"permissive — most wrong colors will still match"
                    )

            if isinstance(validation, dict):
                ml = validation.get("min_length")
                if isinstance(ml, int) and ml > 200:
                    result.warnings.append(
                        f"Test case '{label}': min_length={ml} is large for a "
                        f"vision/JSON test case — models typically return short "
                        f"hex arrays and may over-reject"
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
