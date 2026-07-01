"""
Shared utilities used by both the quality evaluator (evaluator.py) and the
safety evaluator (safety_evaluator.py).

call_model accepts a full messages list so both single-turn quality evals and
multi-turn safety evals share one entry point. See docs/eval-suites/
2026-04-22-jailbreak-safety.md §2 for the rationale.
"""

import base64
import json
import re
import time
from pathlib import Path

from openai import OpenAI

EVALS_DIR = Path(__file__).parent.parent / "evals"
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

MAX_IMAGE_BYTES = 10 * 1024 * 1024  # 10MB
_IMAGE_MIME_BY_SUFFIX = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".gif": "image/gif",
}


def _encode_image_data_url(image_path: Path) -> str:
    """Read an image file and return a base64 data URL for OpenAI content-parts."""
    mime = _IMAGE_MIME_BY_SUFFIX.get(image_path.suffix.lower())
    if mime is None:
        raise ValueError(
            f"Unsupported image extension: {image_path.suffix} "
            f"(expected one of {sorted(_IMAGE_MIME_BY_SUFFIX)})"
        )
    data = image_path.read_bytes()
    b64 = base64.b64encode(data).decode("ascii")
    return f"data:{mime};base64,{b64}"


def load_suite(suite_name: str) -> dict:
    suite_file = EVALS_DIR / f"{suite_name}.json"
    if not suite_file.exists():
        fallback = EVALS_DIR / "suite.json"
        if fallback.exists():
            print(f"Warning: Suite '{suite_name}' not found, falling back to suite.json")
            suite_file = fallback
        else:
            raise FileNotFoundError(f"No evaluation suite found: tried {suite_file} and {fallback}")
    with open(suite_file) as f:
        return json.load(f)


def call_model(
    client: OpenAI,
    model_id: str,
    messages: list[dict],
    image_path: Path | None = None,
) -> dict:
    """Call a model via OpenRouter with a full messages list.

    If image_path is provided, the final user message's content is rewritten
    as a multimodal content-parts array (text + image_url data URL). The
    caller is responsible for checking that the model supports vision.
    """
    start = time.time()
    try:
        call_messages = [dict(m) for m in messages]

        if image_path is not None:
            try:
                size = image_path.stat().st_size
            except OSError as e:
                raise RuntimeError(f"Cannot read image {image_path}: {e}") from e
            if size > MAX_IMAGE_BYTES:
                raise RuntimeError(
                    f"Image {image_path.name} is {size / 1_000_000:.1f}MB, "
                    f"exceeds {MAX_IMAGE_BYTES / 1_000_000:.0f}MB limit. Downsize it."
                )
            data_url = _encode_image_data_url(image_path)

            last_user_idx = None
            for i in range(len(call_messages) - 1, -1, -1):
                if call_messages[i].get("role") == "user":
                    last_user_idx = i
                    break
            if last_user_idx is None:
                raise RuntimeError("call_model: image_path set but messages has no user turn")

            existing = call_messages[last_user_idx].get("content", "")
            text = existing if isinstance(existing, str) else ""
            call_messages[last_user_idx] = {
                "role": "user",
                "content": [
                    {"type": "text", "text": text},
                    {"type": "image_url", "image_url": {"url": data_url}},
                ],
            }

        response = client.chat.completions.create(
            model=model_id,
            messages=call_messages,
            temperature=0.3,
            max_tokens=4096,
        )
        latency = time.time() - start
        output = response.choices[0].message.content or ""
        usage = response.usage

        return {
            "output": output,
            "latency": round(latency, 2),
            "tokens": {
                "input": usage.prompt_tokens if usage else 0,
                "output": usage.completion_tokens if usage else 0,
            },
            "error": None,
        }
    except Exception as e:
        latency = time.time() - start
        return {
            "output": "",
            "latency": round(latency, 2),
            "tokens": {"input": 0, "output": 0},
            "error": str(e),
        }


def call_model_with_tools(
    client: OpenAI,
    model_id: str,
    messages: list[dict],
    tools: list[dict],
) -> dict:
    """Call a model with tool-calling enabled, for the agentic eval pipeline.

    Unlike call_model, this returns the raw assistant message (dict, suitable
    for appending straight back into `messages`) plus whatever tool calls the
    model wants executed. The caller owns the tool-execution loop.
    """
    start = time.time()
    try:
        response = client.chat.completions.create(
            model=model_id,
            messages=messages,
            tools=tools,
            tool_choice="auto",
            temperature=0.3,
            max_tokens=4096,
        )
        latency = time.time() - start
        message = response.choices[0].message
        usage = response.usage

        tool_calls = []
        for tc in (message.tool_calls or []):
            try:
                arguments = json.loads(tc.function.arguments)
            except json.JSONDecodeError:
                arguments = {}
            tool_calls.append({"id": tc.id, "name": tc.function.name, "arguments": arguments})

        return {
            "assistant_message": message.model_dump(exclude_none=True),
            "content": message.content,
            "tool_calls": tool_calls,
            "latency": round(latency, 2),
            "tokens": {
                "input": usage.prompt_tokens if usage else 0,
                "output": usage.completion_tokens if usage else 0,
            },
            "error": None,
        }
    except Exception as e:
        latency = time.time() - start
        return {
            "assistant_message": None,
            "content": None,
            "tool_calls": [],
            "latency": round(latency, 2),
            "tokens": {"input": 0, "output": 0},
            "error": str(e),
        }


def parse_judge_response(response_text: str) -> dict | None:
    """Extract JSON scores from judge response."""
    try:
        return json.loads(response_text)
    except json.JSONDecodeError:
        pass

    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", response_text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass

    start = response_text.find("{")
    end = response_text.rfind("}")
    if start != -1 and end != -1:
        try:
            return json.loads(response_text[start : end + 1])
        except json.JSONDecodeError:
            pass

    return None


def compute_weighted_score(scores: dict, weights: dict) -> float:
    """Compute weighted average from dimension scores."""
    total = 0.0
    for dim, weight in weights.items():
        total += scores.get(dim, 0) * weight
    return round(total, 2)
