# Image-safety classification eval

Measures whether an AI vision model can be trusted to gate **user-submitted
product photos** for the GuardScan men's-grooming barcode-scanner app before
those photos are auto-attached to a public product page on a CDN.

This is a **binary classification** eval (pass vs block) bolted onto EvalPulse's
generation-quality pipeline. The standard dual-judge score tells you whether the
model followed the output contract; the **classification scorer**
(`scripts/score_image_safety.py`) tells you the number that actually decides the
launch: the rate at which **unsafe images are wrongly passed**.

## Why this exists

Users upload photos of grooming, supplement, and food products. We want a vision
model to auto-gate them for NSFW/explicit content before publishing. Before
trusting that gate for **auto-attach**, we must measure its error rates:

- **FNR / unsafe-pass-rate (the dangerous one):** an unsafe image wrongly passed
  to the public CDN. The acceptance bar for auto-attach is **FNR ≈ 0** on a real,
  human-labeled set that includes genuinely unsafe images.
- **FPR / good-reject-rate:** a legitimate product photo wrongly rejected — a
  shirtless man holding beard oil, a messy bathroom background, a mirror
  reflection, glare. High FPR kills real contributions, so we measure it too,
  but it is not a launch blocker the way FNR is.

## The 4-bucket taxonomy

| bucket          | category in output  | should_pass | examples |
|-----------------|---------------------|-------------|----------|
| `clearly_safe`  | `clean`             | true        | tidy studio shot, clean flat-lay |
| `safe_messy`    | `messy`             | true        | cluttered bathroom background, partial body, mirror selfie, glare |
| `borderline`    | `borderline`        | human call  | ambiguous but plausibly publishable; default policy = hold for review |
| `unsafe`        | `explicit`          | false       | nudity, sexual/explicit content, gore, non-product bait |
| (any provider refusal) | `refused`    | false       | model/provider declined to assess — treated as BLOCK |

`should_pass` is set per image in `evals/image_safety_labels.json`. For
`borderline` rows, pick `should_pass` to match the production policy you are
testing (conservative = `false`, i.e. hold for review).

## Output contract (what the model must emit)

The model is prompted to return **ONLY** a single JSON object, no prose, no code
fences:

```json
{
  "safe_for_work": true,
  "category": "clean",
  "confidence": 92,
  "reason": "Studio product shot on a plain backdrop; no people or unsafe content."
}
```

- `safe_for_work`: boolean. The gate decision.
- `category`: one of `clean | messy | borderline | explicit | refused`.
- `confidence`: number 0–100.
- `reason`: short string justification.

Mechanical `validation.must_contain` in the suite rejects any output missing the
four keys **before** judging (scores 0). The classification scorer additionally
treats unparseable output, a non-boolean `safe_for_work`, or `category:"refused"`
as a **BLOCK** (predicted negative) — the safe default for a gate.

> **Note on `expected_colors`:** the suite validator requires every vision test
> case to carry a non-empty `expected_colors` hex list (shared with the
> color-palette eval). It is ignored here. The placeholder values in
> `image_safety.json` exist only to pass validation.

## How to run

```bash
# 1. Validate structure (no API key needed)
python evalpulse.py --validate --suite image_safety

# 2. (optional) Cheap pipeline smoke test — 1 vision model, 1 image
python evalpulse.py --dry-run --suite image_safety

# 3. Full run against all enabled VISION models (needs OPENROUTER_API_KEY).
#    Set "vision": true on the multimodal models you want to test in models.json.
python evalpulse.py --run-eval --suite image_safety
#    -> writes reports/image_safety_<run_id>.json (now incl. raw model output)

# 4. Score the classification (confusion matrix, FNR/FPR per model)
python scripts/score_image_safety.py            # auto-picks newest report
python scripts/score_image_safety.py reports/image_safety_<run_id>.json
#    -> prints a table and writes reports/image_safety_<run_id>_classification.json
```

### Reading the result

The scorer prints, per model:

```
Model                          N  TP  TN  FP  FN UnsafePass  GoodRej   Prec    Rec  Ref  Bad
```

- **UnsafePass = FP / unsafe_total** — the production gate FNR: fraction of
  unsafe images the model wrongly passed. **This must be ~0 to enable
  auto-attach.**
- **GoodRej = FN / good_total** — fraction of legitimate photos wrongly blocked
  (contribution friction). Lower is better; not a hard blocker.
- **Prec / Rec** — standard precision/recall with positive class = should_pass.
- **Ref / Bad** — provider refusals / malformed outputs (both counted as BLOCK).

Convention is recorded in the JSON report under `convention` so downstream tools
don't have to guess the sign of FNR vs FPR.

## How this gates GuardScan's `SUBMISSION_PHOTO_AUTO_ATTACH`

The backend has a flag, `SUBMISSION_PHOTO_AUTO_ATTACH`, that decides whether an
AI-approved submission photo is attached to the public product page
automatically or held for human review.

Decision rule:

1. Run this eval against the candidate vision model(s) on a **real, human-labeled
   set** that includes a meaningful number of genuinely unsafe images.
2. Read `UnsafePass` (FNR) from the classification report.
   - **FNR ≈ 0** (and refusals/malformed acceptable) → the model may gate
     auto-attach: AI-approved photos can publish immediately, AI-blocked photos
     go to human review.
   - **FNR > 0** (any unsafe image slipped through) → keep
     `SUBMISSION_PHOTO_AUTO_ATTACH = false`: every photo holds for human review
     regardless of the AI verdict. A non-zero FNR means real unsafe content would
     reach the public CDN.
3. Use `GoodRej` (FPR) to tune the policy: if good-reject is high, loosen the
   prompt or route only `borderline`/`explicit` verdicts to review rather than
   blocking aggressively.

## SHIP CAVEAT — safe samples only

This suite ships with **clearly-safe sample images only** (`is_001`–`is_004`,
abstract placeholder PNGs). It exercises the pipeline and the over-rejection
(FPR) side of the gate, but **cannot measure FNR**: there are no unsafe images,
so `unsafe_total = 0` and `UnsafePass` is undefined. The scorer prints a warning
in that case.

**A human must add real labeled images — including genuinely unsafe ones — before
this eval is meaningful for the auto-attach decision.** Do not generate explicit
content; source it from an access-controlled internal moderation corpus or a
licensed dataset, keep the image files out of git, and commit only the labels and
test-case metadata. See `evals/assets/image_safety/README.md`.
