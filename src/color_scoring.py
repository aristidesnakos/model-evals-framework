"""
Deterministic color-palette scoring for the color_palette evaluation suite.

Extracts hex color codes from model output, converts sRGB -> CIE L*a*b*,
and computes CIEDE2000 perceptual distance against ground-truth colors.

Stdlib only (math, re).
"""

import math
import re
from typing import Optional

# sRGB D65 reference white
_XN = 95.047
_YN = 100.000
_ZN = 108.883

# Matches #rrggbb or #rgb (with or without leading #).
# The \b avoids greedy matching into longer hex-like strings.
_HEX_RE = re.compile(r"#([0-9a-fA-F]{6}|[0-9a-fA-F]{3})\b")


def parse_hex(s: str) -> Optional[tuple[int, int, int]]:
    """Parse a hex color string (#rrggbb, rrggbb, #rgb, rgb) to an (r,g,b) tuple.

    Returns None if the string is not a valid hex color.
    """
    if not isinstance(s, str):
        return None
    s = s.strip().lstrip("#")
    if len(s) == 3:
        if not re.fullmatch(r"[0-9a-fA-F]{3}", s):
            return None
        r = int(s[0] * 2, 16)
        g = int(s[1] * 2, 16)
        b = int(s[2] * 2, 16)
        return (r, g, b)
    if len(s) == 6:
        if not re.fullmatch(r"[0-9a-fA-F]{6}", s):
            return None
        return (int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16))
    return None


def normalize_hex(s: str) -> Optional[str]:
    """Normalize a hex string to lowercase '#rrggbb' form, or None if invalid."""
    rgb = parse_hex(s)
    if rgb is None:
        return None
    return "#{:02x}{:02x}{:02x}".format(*rgb)


def extract_hex_codes(text: str) -> list[str]:
    """Extract hex codes from free-form text.

    Returns normalized lowercase '#rrggbb' strings, de-duplicated while
    preserving first-occurrence order.
    """
    if not text:
        return []
    seen: set[str] = set()
    out: list[str] = []
    for m in _HEX_RE.finditer(text):
        norm = normalize_hex(m.group(0))
        if norm is None or norm in seen:
            continue
        seen.add(norm)
        out.append(norm)
    return out


def _srgb_to_linear(channel_0_255: int) -> float:
    """Inverse sRGB companding."""
    c = channel_0_255 / 255.0
    if c <= 0.04045:
        return c / 12.92
    return ((c + 0.055) / 1.055) ** 2.4


def srgb_to_xyz(rgb: tuple[int, int, int]) -> tuple[float, float, float]:
    """sRGB (D65) -> CIE XYZ (D65). Output scaled to 0-100-ish range."""
    r = _srgb_to_linear(rgb[0])
    g = _srgb_to_linear(rgb[1])
    b = _srgb_to_linear(rgb[2])
    # sRGB D65 matrix (Lindbloom)
    x = (r * 0.4124564 + g * 0.3575761 + b * 0.1804375) * 100.0
    y = (r * 0.2126729 + g * 0.7151522 + b * 0.0721750) * 100.0
    z = (r * 0.0193339 + g * 0.1191920 + b * 0.9503041) * 100.0
    return (x, y, z)


def _xyz_f(t: float) -> float:
    """Lab piecewise function."""
    delta = 6.0 / 29.0
    if t > delta ** 3:
        return t ** (1.0 / 3.0)
    return (t / (3.0 * delta * delta)) + (4.0 / 29.0)


def xyz_to_lab(xyz: tuple[float, float, float]) -> tuple[float, float, float]:
    """CIE XYZ -> CIE L*a*b* (D65)."""
    fx = _xyz_f(xyz[0] / _XN)
    fy = _xyz_f(xyz[1] / _YN)
    fz = _xyz_f(xyz[2] / _ZN)
    L = 116.0 * fy - 16.0
    a = 500.0 * (fx - fy)
    b = 200.0 * (fy - fz)
    return (L, a, b)


def srgb_to_lab(rgb: tuple[int, int, int]) -> tuple[float, float, float]:
    """Convenience: sRGB 0-255 -> CIE L*a*b* (D65)."""
    return xyz_to_lab(srgb_to_xyz(rgb))


def ciede2000(lab1: tuple[float, float, float], lab2: tuple[float, float, float]) -> float:
    """CIEDE2000 color difference between two L*a*b* colors.

    Reference: Sharma, Wu, Dalal (2005).
    Guards hue-average discontinuity at h'=0/360.
    """
    L1, a1, b1 = lab1
    L2, a2, b2 = lab2

    # Step 1: C* and mean C*
    C1 = math.hypot(a1, b1)
    C2 = math.hypot(a2, b2)
    C_bar = (C1 + C2) / 2.0

    G = 0.5 * (1.0 - math.sqrt((C_bar ** 7) / (C_bar ** 7 + 25.0 ** 7)))
    a1p = (1.0 + G) * a1
    a2p = (1.0 + G) * a2

    C1p = math.hypot(a1p, b1)
    C2p = math.hypot(a2p, b2)

    def _h_prime(bp: float, ap: float) -> float:
        if bp == 0.0 and ap == 0.0:
            return 0.0
        h = math.degrees(math.atan2(bp, ap))
        if h < 0.0:
            h += 360.0
        return h

    h1p = _h_prime(b1, a1p)
    h2p = _h_prime(b2, a2p)

    # Deltas
    dLp = L2 - L1
    dCp = C2p - C1p

    # dhp with wrap-around
    if C1p == 0.0 or C2p == 0.0:
        dhp = 0.0
    else:
        diff = h2p - h1p
        if diff > 180.0:
            dhp = diff - 360.0
        elif diff < -180.0:
            dhp = diff + 360.0
        else:
            dhp = diff

    dHp = 2.0 * math.sqrt(C1p * C2p) * math.sin(math.radians(dhp / 2.0))

    # Averages
    L_bar_p = (L1 + L2) / 2.0
    C_bar_p = (C1p + C2p) / 2.0

    # h_bar_p with wrap-around
    if C1p == 0.0 or C2p == 0.0:
        h_bar_p = h1p + h2p
    else:
        if abs(h1p - h2p) > 180.0:
            h_bar_p = (h1p + h2p + 360.0) / 2.0
        else:
            h_bar_p = (h1p + h2p) / 2.0

    T = (
        1.0
        - 0.17 * math.cos(math.radians(h_bar_p - 30.0))
        + 0.24 * math.cos(math.radians(2.0 * h_bar_p))
        + 0.32 * math.cos(math.radians(3.0 * h_bar_p + 6.0))
        - 0.20 * math.cos(math.radians(4.0 * h_bar_p - 63.0))
    )

    delta_theta = 30.0 * math.exp(-(((h_bar_p - 275.0) / 25.0) ** 2))
    R_C = 2.0 * math.sqrt((C_bar_p ** 7) / (C_bar_p ** 7 + 25.0 ** 7))

    S_L = 1.0 + (0.015 * ((L_bar_p - 50.0) ** 2)) / math.sqrt(20.0 + ((L_bar_p - 50.0) ** 2))
    S_C = 1.0 + 0.045 * C_bar_p
    S_H = 1.0 + 0.015 * C_bar_p * T

    R_T = -math.sin(math.radians(2.0 * delta_theta)) * R_C

    kL = kC = kH = 1.0
    dE = math.sqrt(
        (dLp / (kL * S_L)) ** 2
        + (dCp / (kC * S_C)) ** 2
        + (dHp / (kH * S_H)) ** 2
        + R_T * (dCp / (kC * S_C)) * (dHp / (kH * S_H))
    )
    return dE


def score_palette(
    expected: list[str],
    extracted: list[str],
    tolerance: float = 10.0,
) -> dict:
    """Score an extracted palette against ground-truth hex codes.

    For each expected color, computes the minimum CIEDE2000 distance to any
    extracted color. A match counts when delta_e <= tolerance. Returns a
    JSON-serializable dict summarizing matches, misses, and extras.

    Args:
        expected: ground-truth hex codes (e.g. ["#ff0000", "#00ff00"])
        extracted: hex codes extracted from model output
        tolerance: max delta-E for a match. JND ~2.3, 'close' ~5, 10 is forgiving.

    All inputs are normalized; malformed entries are ignored.
    """
    norm_expected = [h for h in (normalize_hex(e) for e in expected) if h]
    norm_extracted = [h for h in (normalize_hex(e) for e in extracted) if h]

    result: dict = {
        "matches": [],
        "extracted_count": len(norm_extracted),
        "expected_count": len(norm_expected),
        "matched_count": 0,
        "unmatched_expected": [],
        "extra_extracted": [],
        "mean_delta_e": None,
        "accuracy_ratio": 0.0,
        "tolerance": tolerance,
    }

    if not norm_expected:
        return result

    if not norm_extracted:
        # No codes extracted — every expected is unmatched.
        result["unmatched_expected"] = list(norm_expected)
        for exp in norm_expected:
            result["matches"].append({
                "expected": exp,
                "best_match": None,
                "delta_e": None,
                "matched": False,
            })
        return result

    # Pre-compute Lab for extracted (reused across expected iterations).
    extracted_labs: list[tuple[str, tuple[float, float, float]]] = []
    for hx in norm_extracted:
        rgb = parse_hex(hx)
        if rgb is None:
            continue
        extracted_labs.append((hx, srgb_to_lab(rgb)))

    deltas: list[float] = []
    used_extracted: set[str] = set()

    for exp_hex in norm_expected:
        exp_rgb = parse_hex(exp_hex)
        if exp_rgb is None:
            result["matches"].append({
                "expected": exp_hex,
                "best_match": None,
                "delta_e": None,
                "matched": False,
            })
            result["unmatched_expected"].append(exp_hex)
            continue

        exp_lab = srgb_to_lab(exp_rgb)

        best_hex = None
        best_delta = float("inf")
        for ext_hex, ext_lab in extracted_labs:
            d = ciede2000(exp_lab, ext_lab)
            if d < best_delta:
                best_delta = d
                best_hex = ext_hex

        matched = best_delta <= tolerance
        deltas.append(best_delta)
        result["matches"].append({
            "expected": exp_hex,
            "best_match": best_hex,
            "delta_e": round(best_delta, 3),
            "matched": matched,
        })
        if matched:
            result["matched_count"] += 1
            if best_hex is not None:
                used_extracted.add(best_hex)
        else:
            result["unmatched_expected"].append(exp_hex)

    result["extra_extracted"] = [
        hx for hx, _ in extracted_labs if hx not in used_extracted
    ]
    if deltas:
        result["mean_delta_e"] = round(sum(deltas) / len(deltas), 3)
    result["accuracy_ratio"] = round(
        result["matched_count"] / result["expected_count"], 3
    )
    return result


def format_color_match_for_judge(color_match: dict) -> str:
    """Render a color_match dict as a markdown block for the judge prompt."""
    lines = []
    lines.append("## Color Matching (objective, deterministic)")
    lines.append("")
    lines.append(
        f"Matched {color_match['matched_count']}/{color_match['expected_count']} "
        f"ground-truth colors within ΔE ≤ {color_match['tolerance']} "
        f"(CIEDE2000). Mean ΔE: {color_match.get('mean_delta_e', 'n/a')}. "
        f"Extracted {color_match['extracted_count']} total hex codes."
    )
    lines.append("")
    lines.append("| Expected | Best extracted | ΔE | Matched? |")
    lines.append("|----------|---------------|----|----------|")
    for m in color_match.get("matches", []):
        lines.append(
            f"| {m['expected']} | {m.get('best_match') or '—'} | "
            f"{m.get('delta_e') if m.get('delta_e') is not None else '—'} | "
            f"{'yes' if m['matched'] else 'no'} |"
        )
    if color_match.get("extra_extracted"):
        lines.append("")
        lines.append(
            "Extra extracted (not nearest to any expected): "
            + ", ".join(color_match["extra_extracted"])
        )
    lines.append("")
    lines.append(
        "**Use these objective deltas as the primary signal when scoring "
        "`accuracy`.** ΔE ≤ 2.3 is indistinguishable to the human eye; "
        "ΔE ≤ 5 is visually close; ΔE > 25 is a large perceptual error."
    )
    return "\n".join(lines)
