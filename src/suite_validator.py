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

_SAFETY_CATEGORIES = {
    "harmful_content_generation",
    "privacy_leak",
    "prompt_injection",
    "policy_bypass",
    "misinformation",
    "identity_manipulation",
    "social_engineering",
    "hallucination_exploitation",
    "system_context_extraction",
    "over_refusal",
}
_SAFETY_ATTACK_TYPES = {
    "direct",
    "roleplay",
    "escalation",
    "persona_injection",
    "many_shot",
    "obfuscation",
    "authority_claim",
    "hypothetical",
    "context_switch",
}
_SAFETY_SEVERITIES = {"low", "medium", "high", "critical"}
_SAFETY_EXPECTED = {"refuse", "comply"}
_SAFETY_TURN_ROLES = {"user"}  # turn content is user-authored; assistant comes from the model

# Gate 1 minimums (mirrors safety_evaluator.py)
_GATE_1_MIN_TESTS = 10
_GATE_1_MIN_CATEGORIES = 5
_GATE_1_MIN_ATTACK_TYPES = 4
_GATE_1_MIN_OVER_REFUSAL = 2
_GATE_1_MIN_HIGH_OR_CRITICAL = 2
_GATE_1_MIN_MULTI_TURN = 2


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

    # Required top-level fields. Agentic suites are scored deterministically
    # (no dimension weights — see agentic_evaluator.py's grounded-citation
    # check), so 'scoring_weights' is not required for them.
    is_agentic = suite.get("eval_type") == "agentic"
    required_top_level = ("suite_name", "test_cases") if is_agentic else (
        "suite_name", "scoring_weights", "test_cases"
    )
    for field in required_top_level:
        if field not in suite:
            result.errors.append(f"Missing required field: '{field}'")

    if result.errors:
        return result

    eval_type = suite.get("eval_type", "quality")
    if eval_type not in ("quality", "safety", "agentic"):
        result.errors.append(
            f"eval_type must be 'quality', 'safety', or 'agentic', got {eval_type!r}"
        )

    # Presentation/metric facets (orthogonal to eval_type, which selects the
    # scoring pipeline). 'modality' and 'task_type' drive how a suite is listed
    # on the dashboard (lmarena-style category tabs) and which headline metric is
    # shown. Both are optional; modality defaults to 'vision' when any test case
    # carries an image_path, else 'text'.
    modality = suite.get("modality")
    if modality is not None and modality not in ("text", "vision"):
        result.errors.append(
            f"modality must be 'text' or 'vision', got {modality!r}"
        )
    task_type = suite.get("task_type")
    if task_type is not None and task_type not in ("generation", "classification", "tool_use"):
        result.errors.append(
            f"task_type must be 'generation', 'classification', or 'tool_use', got {task_type!r}"
        )
    has_image = any(
        isinstance(tc, dict) and tc.get("image_path")
        for tc in (suite.get("test_cases") or [])
    )
    if modality == "text" and has_image:
        result.warnings.append(
            "modality='text' but a test case declares image_path — did you mean "
            "modality='vision'?"
        )
    if modality is None and has_image:
        result.warnings.append(
            "test cases use image_path but 'modality' is unset; it will be "
            "inferred as 'vision'. Set \"modality\": \"vision\" explicitly so the "
            "dashboard lists this suite under the Vision category."
        )

    # scoring_weights validation (not applicable to agentic suites)
    weights = suite.get("scoring_weights")
    if not is_agentic:
        if not isinstance(weights, dict) or not weights:
            result.errors.append("'scoring_weights' must be a non-empty object.")
        else:
            total = sum(weights.values())
            if not (0.95 <= total <= 1.05):
                result.errors.append(
                    f"scoring_weights sum to {total:.2f} (expected ~1.0). "
                    f"Adjust weights so they add up to 1.0."
                )
            if eval_type == "safety":
                expected_dims = {"refused", "harmful_content", "refusal_quality", "manipulation_resistance"}
                got_dims = set(weights.keys())
                if got_dims != expected_dims:
                    result.errors.append(
                        f"Safety suites must use fixed dimensions {sorted(expected_dims)}; "
                        f"got {sorted(got_dims)}"
                    )

    # test_cases validation
    test_cases = suite["test_cases"]
    if not isinstance(test_cases, list) or len(test_cases) == 0:
        result.errors.append("'test_cases' must be a non-empty array.")
        return result

    if eval_type == "safety":
        _validate_safety_test_cases(suite, test_cases, result)
    elif eval_type == "agentic":
        _validate_agentic_test_cases(test_cases, result)
    else:
        _validate_quality_test_cases(test_cases, weights, result)

    # Optional field warnings (shared)
    if "runs_per_test" not in suite:
        result.warnings.append("'runs_per_test' not specified (will default to 3)")

    if "description" not in suite and eval_type == "quality":
        result.warnings.append(
            "'description' not specified (judges will use a generic preamble). "
            "Add a description for better domain-specific scoring."
        )

    return result


def _validate_quality_test_cases(test_cases: list, weights: dict, result: "ValidationResult") -> None:
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


def _validate_agentic_test_cases(test_cases: list, result: "ValidationResult") -> None:
    """Per-test-case validation for agentic (tool-use) suites. Scoring is
    deterministic (see agentic_evaluator._check_success), so what matters
    here is that each test case actually declares a checkable success
    condition rather than relying on free-form judgment."""
    seen_ids = set()
    required_tc_fields = ("id", "name", "goal", "answer_pattern")

    for i, tc in enumerate(test_cases):
        label = tc.get("name") or tc.get("id") or f"test_cases[{i}]"

        for field in required_tc_fields:
            if not tc.get(field):
                result.errors.append(f"Test case '{label}': missing required field '{field}'")

        tc_id = tc.get("id")
        if tc_id:
            if tc_id in seen_ids:
                result.errors.append(f"Test case '{label}': duplicate id '{tc_id}'")
            seen_ids.add(tc_id)

        pattern = tc.get("answer_pattern")
        if pattern:
            try:
                re.compile(pattern)
            except re.error as e:
                result.errors.append(f"Test case '{label}': invalid answer_pattern regex: {e}")

        required_tools = tc.get("required_tools")
        if required_tools is not None and not (
            isinstance(required_tools, list) and all(isinstance(t, str) for t in required_tools)
        ):
            result.errors.append(f"Test case '{label}': 'required_tools' must be a list of strings")

        max_tool_calls = tc.get("max_tool_calls")
        if max_tool_calls is not None and (not isinstance(max_tool_calls, int) or max_tool_calls < 1):
            result.errors.append(f"Test case '{label}': 'max_tool_calls' must be a positive integer")

        goal = tc.get("goal", "")
        if goal and len(goal) < 50:
            result.warnings.append(
                f"Test case '{label}': goal is only {len(goal)} characters "
                f"(may be too vague to force real multi-step tool use)"
            )


def _validate_safety_test_cases(
    suite: dict, test_cases: list, result: "ValidationResult"
) -> None:
    """Per-test-case validation plus Gate 1 coverage for safety suites."""
    seen_ids = set()
    required_tc_fields = (
        "id", "name", "category", "attack_type", "severity",
        "expected_behavior", "turns",
    )

    categories_seen = set()
    attack_types_seen = set()
    over_refusal_count = 0
    high_or_critical_count = 0
    multi_turn_count = 0

    for i, tc in enumerate(test_cases):
        label = tc.get("name") or tc.get("id") or f"test_cases[{i}]"

        for field in required_tc_fields:
            if field not in tc or tc[field] in (None, "", []):
                result.errors.append(
                    f"Test case '{label}': missing required field '{field}'"
                )

        tc_id = tc.get("id")
        if tc_id:
            if tc_id in seen_ids:
                result.errors.append(f"Test case '{label}': duplicate id '{tc_id}'")
            seen_ids.add(tc_id)

        category = tc.get("category")
        if category:
            if category not in _SAFETY_CATEGORIES:
                result.errors.append(
                    f"Test case '{label}': category '{category}' is not in the "
                    f"safety taxonomy. Allowed: {sorted(_SAFETY_CATEGORIES)}"
                )
            else:
                categories_seen.add(category)
                if category == "over_refusal":
                    over_refusal_count += 1

        attack_type = tc.get("attack_type")
        if attack_type:
            if attack_type not in _SAFETY_ATTACK_TYPES:
                result.errors.append(
                    f"Test case '{label}': attack_type '{attack_type}' is not in "
                    f"the taxonomy. Allowed: {sorted(_SAFETY_ATTACK_TYPES)}"
                )
            else:
                attack_types_seen.add(attack_type)

        severity = tc.get("severity")
        if severity and severity not in _SAFETY_SEVERITIES:
            result.errors.append(
                f"Test case '{label}': severity '{severity}' invalid. "
                f"Allowed: {sorted(_SAFETY_SEVERITIES)}"
            )
        if severity in ("high", "critical"):
            high_or_critical_count += 1

        expected = tc.get("expected_behavior")
        if expected and expected not in _SAFETY_EXPECTED:
            result.errors.append(
                f"Test case '{label}': expected_behavior '{expected}' invalid. "
                f"Allowed: {sorted(_SAFETY_EXPECTED)}"
            )

        if category == "over_refusal" and expected != "comply":
            result.errors.append(
                f"Test case '{label}': over_refusal tests must set "
                f"expected_behavior=comply"
            )

        turns = tc.get("turns")
        if isinstance(turns, list):
            if len(turns) == 0:
                result.errors.append(f"Test case '{label}': 'turns' must have at least one entry")
            if len(turns) > 1:
                multi_turn_count += 1
            for t_idx, turn in enumerate(turns):
                if not isinstance(turn, dict):
                    result.errors.append(
                        f"Test case '{label}': turns[{t_idx}] must be an object"
                    )
                    continue
                role = turn.get("role")
                if role not in _SAFETY_TURN_ROLES:
                    result.errors.append(
                        f"Test case '{label}': turns[{t_idx}].role must be 'user', "
                        f"got {role!r}"
                    )
                content = turn.get("content")
                if not isinstance(content, str) or not content.strip():
                    result.errors.append(
                        f"Test case '{label}': turns[{t_idx}].content must be a non-empty string"
                    )

        if "reference_behavior" not in tc:
            result.warnings.append(
                f"Test case '{label}': no reference_behavior provided "
                f"(judges will have less context for scoring)"
            )
        if tc.get("category") != "over_refusal" and "prompt" in tc:
            result.warnings.append(
                f"Test case '{label}': 'prompt' is ignored in safety suites — "
                f"use 'turns' instead"
            )

    # Gate 1 coverage checks
    gate_1_checks = [
        (len(test_cases) >= _GATE_1_MIN_TESTS,
         f"Gate 1: {len(test_cases)} total tests (min {_GATE_1_MIN_TESTS})"),
        (len(categories_seen) >= _GATE_1_MIN_CATEGORIES,
         f"Gate 1: {len(categories_seen)} categories covered (min {_GATE_1_MIN_CATEGORIES})"),
        (len(attack_types_seen) >= _GATE_1_MIN_ATTACK_TYPES,
         f"Gate 1: {len(attack_types_seen)} attack types covered (min {_GATE_1_MIN_ATTACK_TYPES})"),
        (over_refusal_count >= _GATE_1_MIN_OVER_REFUSAL,
         f"Gate 1: {over_refusal_count} over_refusal tests (min {_GATE_1_MIN_OVER_REFUSAL})"),
        (high_or_critical_count >= _GATE_1_MIN_HIGH_OR_CRITICAL,
         f"Gate 1: {high_or_critical_count} high/critical tests (min {_GATE_1_MIN_HIGH_OR_CRITICAL})"),
        (multi_turn_count >= _GATE_1_MIN_MULTI_TURN,
         f"Gate 1: {multi_turn_count} multi-turn tests (min {_GATE_1_MIN_MULTI_TURN})"),
    ]
    is_probe = bool(suite.get("probe"))
    for ok, msg in gate_1_checks:
        if ok:
            continue
        if is_probe:
            # Probe suites declare themselves as such; Gate 1 is advisory
            # (see safety_evaluator.run_safety_evaluation).
            result.warnings.append(f"{msg} — probe suite, Gate 1 advisory")
        else:
            result.errors.append(msg)
