"""
Interactive wizard for creating evaluation suites.
Generates a valid suite JSON file from user input.
"""

import json
import re
from pathlib import Path

EVALS_DIR = Path(__file__).parent.parent / "evals"

DEFAULT_WEIGHTS = {
    "completeness": 0.30,
    "accuracy": 0.30,
    "format": 0.15,
    "domain_relevance": 0.15,
    "clarity": 0.10,
}

DEFAULT_SCORING_CRITERIA = {
    "completeness": "Covers all aspects requested in the prompt",
    "accuracy": "Information is factually correct and well-reasoned",
    "format": "Output follows the expected structure and formatting",
    "domain_relevance": "Response demonstrates domain-specific knowledge",
    "clarity": "Clear, readable, and actionable for the intended audience",
}


def _sanitize_name(name: str) -> str:
    """Convert a display name to a filesystem-safe suite name."""
    name = name.strip().lower()
    name = re.sub(r"[^a-z0-9_\s-]", "", name)
    name = re.sub(r"[\s-]+", "_", name)
    return name or "my_suite"


def _prompt_input(label: str, default: str = "") -> str:
    """Prompt for single-line input with optional default."""
    if default:
        raw = input(f"  {label} (default: {default}): ").strip()
        return raw or default
    raw = input(f"  {label}: ").strip()
    return raw


def _prompt_multiline(label: str) -> str:
    """Read multi-line input until blank line."""
    print(f"  {label}")
    print("  (Enter a blank line when done)")
    lines = []
    while True:
        line = input("  > ")
        if line.strip() == "":
            break
        lines.append(line)
    return "\n".join(lines)


def _prompt_yes_no(label: str, default: bool = True) -> bool:
    """Prompt for y/n with a default."""
    hint = "Y/n" if default else "y/N"
    raw = input(f"  {label} ({hint}): ").strip().lower()
    if not raw:
        return default
    return raw.startswith("y")


def _collect_test_case(tc_number: int) -> dict:
    """Collect one test case interactively."""
    print(f"\n  --- Test Case {tc_number} ---")
    name = _prompt_input("Test case name")
    category = _prompt_input("Category (e.g., reasoning, generation, classification)")
    prompt = _prompt_multiline("Paste the prompt to evaluate:")

    must_contain_raw = _prompt_input(
        "Terms that must appear in a good response (comma-separated, or Enter to skip)"
    )
    must_contain = [t.strip() for t in must_contain_raw.split(",") if t.strip()] if must_contain_raw else []

    min_length_raw = _prompt_input("Minimum response length in characters", "200")
    try:
        min_length = int(min_length_raw)
    except ValueError:
        min_length = 200

    reference = _prompt_input("What does a good answer look like? (brief description)")

    tc = {
        "id": f"tc_{tc_number:03d}",
        "name": name,
        "category": category,
        "prompt": prompt,
        "expected_format": "text",
        "validation": {},
        "reference_answer": reference,
        "scoring_criteria": dict(DEFAULT_SCORING_CRITERIA),
    }

    if must_contain:
        tc["validation"]["must_contain"] = must_contain
    if min_length > 0:
        tc["validation"]["min_length"] = min_length

    return tc


def run_init() -> None:
    """Main wizard entry point."""
    print()
    print("EvalPulse Suite Creator")
    print("=" * 40)
    print("This wizard will help you create an evaluation suite.\n")

    try:
        domain = _prompt_input("What domain are you evaluating? (e.g., customer support, legal, medical)")
        suite_name = _sanitize_name(domain)

        description = _prompt_input(
            "Brief description of what this suite evaluates",
            f"Evaluates models on {domain} tasks"
        )

        # Collect test cases
        test_cases = []
        tc_number = 1
        while True:
            tc = _collect_test_case(tc_number)
            test_cases.append(tc)
            tc_number += 1

            if not _prompt_yes_no("Add another test case?"):
                break

        if not test_cases:
            print("\nNo test cases added. Suite not created.")
            return

        runs_raw = _prompt_input("How many runs per test case?", "3")
        try:
            runs_per_test = int(runs_raw)
        except ValueError:
            runs_per_test = 3

        # Build suite
        suite = {
            "suite_name": suite_name,
            "description": description,
            "runs_per_test": runs_per_test,
            "scoring_weights": dict(DEFAULT_WEIGHTS),
            "test_cases": test_cases,
        }

        # Check for existing file
        suite_file = EVALS_DIR / f"{suite_name}.json"
        EVALS_DIR.mkdir(exist_ok=True)

        if suite_file.exists():
            if not _prompt_yes_no(f"File {suite_file} already exists. Overwrite?", default=False):
                print("Suite not created.")
                return

        # Write file
        with open(suite_file, "w") as f:
            json.dump(suite, f, indent=2)
            f.write("\n")

        print(f"\nSuite created: {suite_file}")
        print(f"  Test cases: {len(test_cases)}")
        print(f"  Runs per test: {runs_per_test}")

        # Auto-validate
        try:
            from suite_validator import validate_suite
            result = validate_suite(suite_name)
            if result.is_valid:
                print(f"\nValidation: PASSED")
            else:
                print(f"\nValidation: FAILED")
                result.print_report()
                return
        except ImportError:
            pass

        print(f"\nNext steps:")
        print(f"  1. Review: cat evals/{suite_name}.json")
        print(f"  2. Dry run: python evalpulse.py --dry-run --suite {suite_name}")
        print(f"  3. Full run: python evalpulse.py --run-eval --suite {suite_name}")
        print(f"  4. Dashboard: python evalpulse.py --dashboard")

    except (KeyboardInterrupt, EOFError):
        print("\n\nWizard cancelled.")
