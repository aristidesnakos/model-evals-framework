"""
Registry of tool packs for the agentic eval pipeline (agentic_evaluator.py).

A tool pack is just a (TOOL_SCHEMAS, execute_tool_call) pair — the same shape
agentic_tools.py already exposed. This registry exists so agentic_evaluator.py
can load the right pack per suite (via the suite JSON's "tool_pack" field)
instead of hardcoding a single import, which is what let the OSHA/eCFR/openFDA
tools leak into the loop as an unstated assumption. Adding a new pack (e.g. a
browser/computer-use one) means writing a module with the same TOOL_SCHEMAS +
execute_tool_call shape and registering it below — agentic_evaluator.py,
suite_validator.py, reporter.py, and dashboard.py all key off generic fields
and need no changes.
"""

import agentic_tools

TOOL_PACKS = {
    "government_data": {
        "schemas": agentic_tools.TOOL_SCHEMAS,
        "execute": agentic_tools.execute_tool_call,
    },
}

DEFAULT_TOOL_PACK = "government_data"


def get_tool_pack(name: str) -> tuple[list[dict], callable]:
    """Return (TOOL_SCHEMAS, execute_tool_call) for the named pack."""
    pack = TOOL_PACKS.get(name)
    if pack is None:
        raise ValueError(f"Unknown tool_pack: {name!r}. Available: {sorted(TOOL_PACKS)}")
    return pack["schemas"], pack["execute"]
