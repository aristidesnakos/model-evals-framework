"""
Checks OpenRouter for available models and diffs against the local registry.
Discovers new models that match Tier 3 criteria.
"""

import json
import httpx
from datetime import datetime, timezone
from pathlib import Path


OPENROUTER_MODELS_URL = "https://openrouter.ai/api/v1/models"
MODELS_FILE = Path(__file__).parent.parent / "models.json"


def load_registry() -> dict:
    with open(MODELS_FILE) as f:
        return json.load(f)


def save_registry(registry: dict) -> None:
    registry["metadata"]["last_checked"] = datetime.now(timezone.utc).isoformat()
    with open(MODELS_FILE, "w") as f:
        json.dump(registry, f, indent=2)
        f.write("\n")


def fetch_openrouter_models(api_key: str) -> list[dict]:
    """Fetch all models from OpenRouter API."""
    try:
        resp = httpx.get(
            OPENROUTER_MODELS_URL,
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        if "data" not in data:
            raise RuntimeError("OpenRouter API response missing 'data' key")
        return data["data"]
    except httpx.HTTPStatusError as e:
        raise RuntimeError(f"OpenRouter API returned {e.response.status_code}: {e.response.text[:200]}") from e
    except httpx.RequestError as e:
        raise RuntimeError(f"Failed to connect to OpenRouter API: {e}") from e


def matches_tier_criteria(model: dict, criteria: dict) -> bool:
    """Check if a model matches Tier 3 selection criteria."""
    ctx = model.get("context_length", 0)
    pricing = model.get("pricing", {})

    # Pricing is per-token as a string; convert to per-million float
    try:
        input_cost = float(pricing.get("prompt", "0")) * 1_000_000
        output_cost = float(pricing.get("completion", "0")) * 1_000_000
    except (ValueError, TypeError):
        return False

    # Exclude free models
    if criteria.get("exclude_free") and input_cost == 0 and output_cost == 0:
        return False

    # Must be text output
    arch = model.get("architecture", {})
    output_modalities = arch.get("output_modalities", [])
    if "text" not in output_modalities:
        return False

    return (
        ctx >= criteria.get("min_context_length", 0)
        and input_cost <= criteria.get("max_input_cost_per_million", float("inf"))
        and output_cost <= criteria.get("max_output_cost_per_million", float("inf"))
    )


def check_for_new_models(api_key: str, auto_enable: bool = False) -> dict:
    """
    Compare OpenRouter catalog against local registry.
    Returns a summary of new, removed, and updated models.
    """
    registry = load_registry()
    criteria = registry["metadata"]["tier_criteria"]
    known_ids = {m["id"] for m in registry["models"]}

    remote_models = fetch_openrouter_models(api_key)
    matching = [m for m in remote_models if matches_tier_criteria(m, criteria)]
    remote_matching_ids = {m["id"] for m in matching}

    new_models = []
    for model in matching:
        if model["id"] not in known_ids:
            pricing = model.get("pricing", {})
            arch = model.get("architecture", {})
            input_modalities = arch.get("input_modalities", [])
            entry = {
                "id": model["id"],
                "name": model.get("name", model["id"]),
                "enabled": auto_enable,
                "context_length": model.get("context_length", 0),
                "pricing": {
                    "input_per_million": round(
                        float(pricing.get("prompt", "0")) * 1_000_000, 4
                    ),
                    "output_per_million": round(
                        float(pricing.get("completion", "0")) * 1_000_000, 4
                    ),
                },
                "vision": "image" in input_modalities,
                "added": datetime.now(timezone.utc).isoformat(),
            }
            new_models.append(entry)

    removed_ids = known_ids - remote_matching_ids

    if new_models:
        registry["models"].extend(new_models)

    try:
        save_registry(registry)
    except IOError as e:
        print(f"Warning: Could not save registry: {e}")

    return {
        "new": new_models,
        "removed_from_openrouter": [mid for mid in removed_ids],
        "total_matching": len(matching),
        "total_registered": len(registry["models"]),
    }
