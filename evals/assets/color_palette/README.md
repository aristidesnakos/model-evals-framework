# Color palette test assets

Drop PNG/JPG/WEBP images here. Each image is paired with a ground-truth list of
hex codes in `evals/color_palette.json`.

## Naming convention

Use the test case `id` as the filename:

```
cp_001.png
cp_002.jpg
cp_003.webp
```

The suite JSON refers to the file via the `image_path` field, relative to
`evals/`:

```json
{
  "id": "cp_001",
  "image_path": "assets/color_palette/cp_001.png",
  "expected_colors": ["#f2a65a", "#e94f37", "#1e1e2e", "#44355b"]
}
```

## Recommended constraints

- **Format:** PNG, JPG, JPEG, WEBP, or GIF. SVG is not supported.
- **Size:** keep the longest edge ≤ 1024 px. The runner caps image payloads at
  10 MB; larger files are rejected before the API call to avoid wasted cost.
- **Count:** 4–6 dominant colors per image is a good target for this eval —
  fewer makes the test too easy; more dilutes the signal.

## Picking ground-truth hex codes

1. Open the image in an eyedropper tool (e.g. macOS Digital Color Meter,
   <https://imagecolorpicker.com>, or Photoshop).
2. Sample the 4–6 largest visually distinct regions.
3. Record each as a 6-digit hex code (e.g. `#f2a65a`). 3-digit shorthand
   (`#f00`) is also accepted.
4. Add them to the test case's `expected_colors` list in descending order of
   dominance.

## Scoring

Model outputs are scored against these hex codes using CIEDE2000 delta-E:

| ΔE     | Interpretation                    |
|--------|-----------------------------------|
| ≤ 2.3  | Visually indistinguishable        |
| ≤ 5    | Visually close                    |
| ≤ 10   | **Default match threshold**       |
| ≤ 25   | Noticeable difference             |
| > 25   | Large perceptual error            |

Override the per-test threshold with `"color_tolerance": <number>` in the test
case if a particular image warrants a stricter or looser match.
