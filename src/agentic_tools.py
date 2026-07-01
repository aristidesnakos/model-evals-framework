"""
Real-API tools for the agentic eval pipeline (agentic_evaluator.py).

Deliberately NOT mocks: models call live government data so the harness
measures real tool-use friction (pagination, schema verbosity, missed
fields) instead of toy responses. To keep results reproducible across
models evaluated at different times, every tool call requires an explicit
date range / version — callers must pin queries themselves rather than
asking for "latest".

OSHA_API_KEY (free, instant) registers at https://dataportal.dol.gov/registration.
eCFR and openFDA need no key at all — openFDA is the practical default for
getting a suite running immediately (see construction_safety_agentic.json
vs. health_safety_agentic.json).
"""

import os

import httpx

OSHA_BASE_URL = "https://api.dol.gov/V1/Compliance/OSHA"
ECFR_BASE_URL = "https://www.ecfr.gov/api/versioner/v1"
OPENFDA_BASE_URL = "https://api.fda.gov/drug"

_HTTP_TIMEOUT = 20.0


def _osha_headers() -> dict:
    api_key = os.environ.get("OSHA_API_KEY", "")
    if not api_key:
        raise RuntimeError(
            "OSHA_API_KEY not set. Register a free key at "
            "https://dataportal.dol.gov/registration and add it to .env."
        )
    return {"X-API-KEY": api_key}


def osha_search_inspections(naics_code: str, date_start: str, date_end: str, limit: int = 25) -> dict:
    """Search OSHA enforcement inspections by NAICS code and a fixed date range.

    Returns a trimmed list of {inspection_id, citations, standards_cited} so
    the model isn't flooded with the full raw payload.
    """
    params = {
        "naics": naics_code,
        "open_date_from": date_start,
        "open_date_to": date_end,
        "limit": min(limit, 100),
    }
    resp = httpx.get(OSHA_BASE_URL, headers=_osha_headers(), params=params, timeout=_HTTP_TIMEOUT)
    resp.raise_for_status()
    data = resp.json()

    records = data.get("results") or data.get("data") or []
    trimmed = []
    for rec in records[:limit]:
        trimmed.append({
            "inspection_id": rec.get("activity_nr") or rec.get("inspection_id"),
            "open_date": rec.get("open_date"),
            "citations": rec.get("nr_violations") or rec.get("citations"),
            "standards_cited": rec.get("standards") or rec.get("standard_cited") or [],
        })
    return {"count": len(trimmed), "inspections": trimmed}


def ecfr_get_section_text(title: str, part: str, section: str, as_of_date: str) -> dict:
    """Fetch the text of one CFR section (e.g. title=29, part=1926, section=501)
    as it read on as_of_date — pinning the date keeps this reproducible even
    though the live regulation can be amended later.
    """
    url = f"{ECFR_BASE_URL}/full/{as_of_date}/title-{title}.xml"
    params = {"part": part, "section": section}
    resp = httpx.get(url, params=params, timeout=_HTTP_TIMEOUT)
    resp.raise_for_status()
    return {
        "title": title,
        "part": part,
        "section": section,
        "as_of_date": as_of_date,
        "text": resp.text[:6000],
    }


def openfda_search_recalls(classification: str, date_start: str, date_end: str, limit: int = 25) -> dict:
    """Search real FDA drug enforcement (recall) records by classification
    (e.g. "Class I") and a fixed report_date range. No API key required.

    Deliberately returns product_ndc codes but NOT the linked manufacturer/
    labeler name — that lives behind openfda_get_ndc_manufacturer, so a model
    has to make the second hop rather than reading manufacturer off this
    record's own (sometimes-inconsistent) recalling_firm field.
    """
    date_start_compact = date_start.replace("-", "")
    date_end_compact = date_end.replace("-", "")
    params = {
        "search": (
            f'classification:"{classification}" '
            f"AND report_date:[{date_start_compact} TO {date_end_compact}] "
            f"AND _exists_:openfda.product_ndc"
        ),
        "limit": min(limit, 100),
    }
    resp = httpx.get(f"{OPENFDA_BASE_URL}/enforcement.json", params=params, timeout=_HTTP_TIMEOUT)
    resp.raise_for_status()
    data = resp.json()

    records = data.get("results") or []
    trimmed = []
    for rec in records[:limit]:
        trimmed.append({
            "recall_number": rec.get("recall_number"),
            "recalling_firm": rec.get("recalling_firm"),
            "product_description": rec.get("product_description"),
            "reason_for_recall": rec.get("reason_for_recall"),
            "report_date": rec.get("report_date"),
            "product_ndc": rec.get("openfda", {}).get("product_ndc", []),
        })
    return {"total_available": data.get("meta", {}).get("results", {}).get("total"), "recalls": trimmed}


def openfda_get_ndc_manufacturer(product_ndc: str) -> dict:
    """Look up the real labeler/manufacturer of record for one NDC via the
    FDA NDC Directory. This is the canonical manufacturer field — it can
    differ from a recall's recalling_firm (distributor/reseller) — so
    cross-referencing here is a genuine second hop, not busywork.
    """
    params = {"search": f'product_ndc:"{product_ndc}"', "limit": 1}
    resp = httpx.get(f"{OPENFDA_BASE_URL}/ndc.json", params=params, timeout=_HTTP_TIMEOUT)
    resp.raise_for_status()
    data = resp.json()
    results = data.get("results") or []
    if not results:
        return {"product_ndc": product_ndc, "labeler_name": None, "error": "no NDC record found"}
    rec = results[0]
    return {
        "product_ndc": product_ndc,
        "labeler_name": rec.get("labeler_name"),
        "brand_name": rec.get("brand_name"),
        "generic_name": rec.get("generic_name"),
    }


TOOL_REGISTRY = {
    "osha_search_inspections": osha_search_inspections,
    "ecfr_get_section_text": ecfr_get_section_text,
    "openfda_search_recalls": openfda_search_recalls,
    "openfda_get_ndc_manufacturer": openfda_get_ndc_manufacturer,
}

TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "osha_search_inspections",
            "description": (
                "Search real OSHA enforcement inspection records by NAICS industry code "
                "and a fixed open_date range. Returns citation counts and cited standard numbers."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "naics_code": {"type": "string", "description": "6-digit NAICS code, e.g. 236220"},
                    "date_start": {"type": "string", "description": "YYYY-MM-DD"},
                    "date_end": {"type": "string", "description": "YYYY-MM-DD"},
                    "limit": {"type": "integer", "description": "Max records to return, default 25"},
                },
                "required": ["naics_code", "date_start", "date_end"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "ecfr_get_section_text",
            "description": (
                "Fetch the real regulatory text of a specific Code of Federal Regulations section "
                "as it read on a given date, e.g. title=29, part=1926, section=501 (fall protection)."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "CFR title number, e.g. '29'"},
                    "part": {"type": "string", "description": "CFR part number, e.g. '1926'"},
                    "section": {"type": "string", "description": "CFR section number, e.g. '501'"},
                    "as_of_date": {"type": "string", "description": "YYYY-MM-DD version to fetch"},
                },
                "required": ["title", "part", "section", "as_of_date"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "openfda_search_recalls",
            "description": (
                "Search real FDA drug recall/enforcement records by classification "
                "(e.g. 'Class I', 'Class II', 'Class III') and a fixed report_date range. "
                "No API key required. Returns recalling_firm, reason, and product_ndc codes "
                "(but not the manufacturer of record — use openfda_get_ndc_manufacturer for that)."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "classification": {"type": "string", "description": "e.g. 'Class I'"},
                    "date_start": {"type": "string", "description": "YYYY-MM-DD"},
                    "date_end": {"type": "string", "description": "YYYY-MM-DD"},
                    "limit": {"type": "integer", "description": "Max records to return, default 25"},
                },
                "required": ["classification", "date_start", "date_end"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "openfda_get_ndc_manufacturer",
            "description": (
                "Look up the real manufacturer/labeler of record for a single NDC code "
                "via the FDA NDC Directory. No API key required."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "product_ndc": {"type": "string", "description": "e.g. '51754-1007'"},
                },
                "required": ["product_ndc"],
            },
        },
    },
]


def execute_tool_call(name: str, arguments: dict) -> dict:
    """Run one tool call and return a JSON-serializable result, or an error dict.

    Errors are returned (not raised) so the agent loop can feed them back to
    the model as a tool result — that recovery behavior is itself part of
    what an efficiency comparison should capture.
    """
    fn = TOOL_REGISTRY.get(name)
    if fn is None:
        return {"error": f"Unknown tool: {name}"}
    try:
        return fn(**arguments)
    except TypeError as e:
        return {"error": f"Bad arguments for {name}: {e}"}
    except httpx.HTTPStatusError as e:
        return {"error": f"{name} HTTP {e.response.status_code}: {e.response.text[:300]}"}
    except Exception as e:
        return {"error": f"{name} failed: {e}"}
