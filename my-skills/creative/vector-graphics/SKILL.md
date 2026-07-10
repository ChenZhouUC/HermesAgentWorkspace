---
name: vector-graphics
description: Use when converting an icon or logo from a Feishu image attachment, local PNG/SVG path, image URL, or HTML page with og:image into a normalized square SVG written to ~/.hermes/tmp/.
---

# Vector Graphics — Square Canvas Normalization

## Primary tool

```bash
python3 ~/.hermes/my-skills/creative/vector-graphics/scripts/to_square_svg.py <input> [--name SLUG] [--fuzz PCT] [-o PATH]
```

`<input>` may be:

- a local PNG or SVG path
- an `http(s)://` URL pointing to a PNG / SVG
- an `http(s)://` URL pointing to an HTML page that _contains_ an icon (the script auto-extracts `og:image` / `twitter:image` / `apple-touch-icon` / `rel=icon`, max one redirect hop)

The script prints the absolute output path on the **last line of stdout** (machine-readable). Both the downloaded source and the produced SVG live in `~/.hermes/tmp/`.

## Output guarantees

Every produced SVG satisfies all three:

1. `viewBox` is square (`width == height`).
2. Content's geometric centre coincides with the viewBox centre — strictly centred.
3. Content's long axis is flush against both opposite edges (zero padding on the long axis); short axis is symmetrically padded.

If any of these can't be guaranteed (degenerate bbox, near-zero numbers from unresolved units, no viewBox in the Inkscape output), the script aborts with a clear message rather than emitting a broken file.

## Naming

Default output: `~/.hermes/tmp/<slug>_hermes.svg`.

- `<slug>` = source filename lowercased with non-alphanumeric runs collapsed to a single `_`, e.g. `Gemini-Color.svg` → `gemini_color`.
- `_hermes` suffix marks files normalized by this skill — useful for telling them apart from raw downloads at a glance.
- Use `--name <slug>` when the source filename is meaningless (e.g. a URL whose last segment is `default.png` or `images.bin`).
- Use `-o /full/path.svg` to override location entirely.
- Collisions auto-suffix `_1`, `_2`, ... — never overwrites.

## CLI options

| Flag          | Default                           | When to use                                                                                                                                            |
| ------------- | --------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `--name SLUG` | (derived from source filename)    | Source filename is generic; you want the output named meaningfully.                                                                                    |
| `--fuzz PCT`  | `2`                               | PNG-trim fuzz tolerance in percent. Raise to `~10` if light-grey / off-white borders aren't being detected as background; set `0` for strict matching. |
| `-o PATH`     | `~/.hermes/tmp/<slug>_hermes.svg` | Full override of output path.                                                                                                                          |

## Branch logic (for debugging)

The script picks a branch based on file magic, not extension:

**PNG branch**:

1. `magick -fuzz {fuzz}% -trim +repage` strips near-uniform / transparent borders. `+repage` clears the residual canvas offset — without it, centring breaks.
2. Measure trimmed `w×h`, set `side = max(w, h)`.
3. Wrap in a fresh `viewBox="0 0 side side"` SVG with one base64-embedded `<image>` offset by `((side-w)/2, (side-h)/2)`.

**SVG branch**:

1. **Sanitize root `<svg>` dimensions**: relative units (`em`, `ex`, `%`, `vw`, `vh`, `vmin`, `vmax`, `ch`, `rem`) on the root `width`/`height` are replaced with the absolute pixel values from `viewBox`. Inkscape collapses `1em` to ~0 without a font-size context, which produces garbage `~1e-45` bboxes (lobe-icons ship `width="1em"` — this branch is hit constantly).
2. `inkscape --export-area-drawing --export-plain-svg` rewrites the file so the `viewBox` matches the actual rendered drawing bbox. Fixes "content sits outside the original canvas" cases.
3. Read that bbox `(x, y, w, h)`, compute `side = max(w, h)`, rewrite the root `<svg>` open tag with `viewBox="x-(side-w)/2 y-(side-h)/2 side side"` and matching `width`/`height`. Inner geometry is untouched — paths, strokes, filters, gradients all preserved exactly.

**SVG-wrapped-PNG fast-path** (runs _before_ the SVG branch): if the SVG contains exactly one `<image href="data:image/png;base64,...">` and no other visible drawing primitives (`path` / `rect` / `circle` / `ellipse` / `line` / `polygon` / `polyline` / `text` / `tspan` / `use` / `foreignObject`), the script extracts that PNG to `<slug>_extracted.png` and runs the PNG branch. Otherwise the SVG bbox query would only see the outer 300×300 box and miss the actual PNG's white borders. Triggered by exporters that "save as SVG" by wrapping a raster.

## Reporting back to the user

After the script finishes, tell Chen Zhou the absolute output path (the last stdout line). When the input was an HTML page, also note which meta tag was followed (logged on stderr).

## Feishu gateway integration

This skill is invoked through the Feishu gateway. Two hard constraints:

**Inbound (Feishu image → script input):** Feishu image attachments are cached by `gateway/platforms/base.py::cache_image_from_url` / `cache_image_from_bytes` into `~/.hermes/cache/images/img_<hash>.<ext>`. Pass that absolute path straight to the script — it auto-detects PNG vs SVG by magic bytes, the cache filename's `.jpg` extension is ignored when the bytes are actually PNG.

**Outbound (produced SVG → Feishu user):** Use `send_file`, **not** `send_image` / `send_image_file`. The Feishu `im.v1.image.create` upload endpoint only accepts raster formats (PNG/JPG/GIF/WEBP/BMP) — SVG is XML text and will be rejected with an upload error. The right call shape is:

```python
await platform.send_file(
    chat_id=...,
    file_path=str(output_path),     # the last stdout line of to_square_svg.py
    file_name=output_path.name,     # e.g. "tavily_color_hermes.svg"
    caption=f"已转好：{output_path}",  # optional; useful so the user has the absolute path inline
    reply_to=...,
)
```

If you also want to preview the result inline (Feishu doesn't render SVG previews natively), additionally rasterize a PNG sibling with `magick out.svg out_preview.png` and `send_image_file` that one — but the SVG itself must travel as a file attachment.

## Quick recipes

```bash
# Lobe-icons SVG by URL — hits the SVG branch with em-unit sanitization
to_square_svg.py "https://raw.githubusercontent.com/lobehub/lobe-icons/master/packages/static-svg/icons/tavily-color.svg"

# JetBrains plugin page — hits the HTML→og:image extractor
to_square_svg.py "https://plugins.jetbrains.com/plugin/28946-serena" --name serena

# SVG that's secretly a PNG with white border — hits the wrapped-PNG fast-path
to_square_svg.py "https://tomatocloud.me/assets/img/stisla-fill.svg"

# PNG with off-white anti-aliased border that the default fuzz misses
to_square_svg.py ~/Downloads/icon.png --fuzz 10
```

Where `to_square_svg.py` is shorthand for `python3 ~/.hermes/my-skills/creative/vector-graphics/scripts/to_square_svg.py`.

## Edge cases handled

- HTML page returns no `og:image` / icon link → fails loudly, asks for a direct image URL.
- HTML redirect chain longer than one hop → fails (avoids loops).
- URL with no filename in path / no Content-Type extension → uses content-type to pick `.svg` / `.png` / `.bin`.
- Inkscape produces near-zero bbox (long edge < 1e-3) → fails loudly, suggests fixing absolute units in the source.
- Output path collision → auto-suffixed `_1`, `_2`, ...

## Out of scope

- **Raster-to-vector tracing** (PNG → real vector paths). Embedding the PNG in an SVG is lossless and matches the user's intent here. Only invoke tracing when explicitly asked. References:
  - `references/inkscape-png-to-svg.md` — Inkscape GUI / CLI tracing

  CLI fallback for monochrome / line-art:

  ```bash
  brew install potrace imagemagick   # one-time
  magick input.png temp.pnm
  potrace temp.pnm -s -o output.svg && rm temp.pnm
  ```

- **SVG-to-Plain-SVG cleanup** (object-to-path, strip Inkscape XML):
  ```bash
  inkscape input.svg --actions="select-all;object-to-path;export-plain-svg;export-filename:output.svg;export-do"
  ```
- **Uniform canvas size across multiple icons** (e.g. all output 256×256). Not implemented — current canvas size = `max(content w, h)`. Add `--canvas N` if needed.
