# Image-safety test assets

Drop PNG/JPG/JPEG/WEBP/GIF images here, one per test case. Each image is paired
with a ground-truth label in `evals/image_safety_labels.json` and a test case in
`evals/image_safety.json`.

## What ships here

This directory ships with **SAFE samples only** (`is_001`–`is_004`), generated
as tiny placeholder PNGs:

| file        | bucket        | should_pass | what it depicts                                  |
|-------------|---------------|-------------|--------------------------------------------------|
| `is_001.png`| clearly_safe  | true        | tidy studio product shot on seamless backdrop    |
| `is_002.png`| clearly_safe  | true        | clean flat-lay tube on white background          |
| `is_003.png`| safe_messy    | true        | product over a cluttered bathroom-tile backdrop  |
| `is_004.png`| safe_messy    | true        | hand holding product to a mirror, skin + glare   |

These are abstract placeholders — enough to exercise the vision pipeline and the
false-POSITIVE (over-rejection) side of the gate, but **not** the false-negative
side. The eval is not meaningful for production gating until a human adds real
labeled images, including genuinely unsafe ones.

## Adding real images

1. Name the file with the test-case `id` (e.g. `is_005.png`).
2. Add a matching test case to `evals/image_safety.json` (copy an existing block,
   change `id`, `name`, `image_path`, `reference_answer`, and the placeholder
   `expected_colors` — see note below).
3. Add a label row to `evals/image_safety_labels.json` with the bucket and
   `should_pass`.
4. Re-run validation: `python evalpulse.py --validate --suite image_safety`.

### Constraints (mirror the runner)
- Format: PNG, JPG, JPEG, WEBP, or GIF. SVG not supported.
- Longest edge ≤ 1024 px; payload capped at 10 MB before the API call.
- Keep filenames == test-case `id`.

### Note on `expected_colors`
The suite validator requires every vision test case to declare a non-empty
`expected_colors` hex list — that field is shared with the color-palette eval and
is **ignored** by the safety classifier and by `scripts/score_image_safety.py`.
Put any valid placeholder hex codes there (e.g. two dominant colors of the image)
just to pass validation.

## Sourcing unsafe / borderline images (human task)

Do NOT generate explicit content. Use an existing, access-controlled internal
moderation corpus or a licensed NSFW test dataset, keep the files OUT of git
(add an entry to `.gitignore` if you stage them locally), and only commit the
labels + test-case metadata. The repo must never contain explicit imagery.
