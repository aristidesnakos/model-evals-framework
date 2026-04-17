# Running the color-palette eval

Four steps from here to a scored run.

## 1. Drop images

Place images in this folder, named by test-case `id`:

```
evals/assets/color_palette/
  cp_001.png
  cp_002.png
```

Constraints: PNG/JPG/JPEG/WEBP/GIF, longest edge ≤ 1024 px, ≤ 10 MB.

## 2. Set ground-truth hex codes

Edit `evals/color_palette.json`. For each test case, replace the placeholder
`name` and `expected_colors` with the real palette (4–6 hex codes, descending
dominance):

```json
{
  "id": "cp_001",
  "name": "<describe the image>",
  "image_path": "assets/color_palette/cp_001.png",
  "expected_colors": ["#f2a65a", "#e94f37", "#1e1e2e", "#44355b"],
  "color_tolerance": 10.0
}
```

Sample colors with an eyedropper (macOS Digital Color Meter,
imagecolorpicker.com). Default tolerance `10.0` ΔE is fine; tighten per-case
if needed.

## 3. Enable a vision model

In `models.json`, flip `"vision": true` on at least one enabled model that
actually supports image input (e.g. a GPT-5.4 / Gemini / Claude vision variant).
Non-vision models will be skipped (not errored) for this suite.

```json
{
  "id": "openai/gpt-5.4-mini",
  "enabled": true,
  "vision": true
}
```

## 4. Run

```bash
# Validate the suite + assets
.venv/bin/python evalpulse.py --validate --suite color_palette

# Smoke-test one vision model on one test case
.venv/bin/python evalpulse.py --dry-run --suite color_palette

# Full run against all enabled models (budget in USD)
.venv/bin/python evalpulse.py --run-eval --suite color_palette --budget 1.00
```

The report (under `reports/`) will show per-model CIEDE2000 match stats
(`matched / expected within ΔE ≤ tolerance, mean ΔE`) and mark non-vision
models as `SKIPPED` rather than failed.
