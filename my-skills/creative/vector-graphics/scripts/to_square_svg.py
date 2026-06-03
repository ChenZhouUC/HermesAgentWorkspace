#!/usr/bin/env python3
"""
to_square_svg.py - Normalize a PNG / SVG / URL into a square SVG where
the content is perfectly centered and the longest edge touches the canvas edge.

Rules enforced on the output:
  - viewBox is square (width == height)
  - content's geometric centre coincides with the viewBox centre
  - content's longest axis is flush against both opposite edges of the canvas
    (i.e. no padding on the long axis); the short axis is symmetrically padded.

Inputs:
  - Local PNG path   (background already removed: -trim handles transparent borders)
  - Local SVG path   (content may sit outside the original viewBox; we fix it)
  - http(s) URL      (downloaded into TMP_DIR before processing)

Outputs:
  - Square SVG written to TMP_DIR (default: ~/.hermes/tmp).
  - Final path printed on stdout (last line) for downstream callers.
"""

from __future__ import annotations

import argparse
import base64
import re
import subprocess
import sys
import tempfile
import urllib.parse
import urllib.request
from pathlib import Path

TMP_DIR = Path.home() / ".hermes" / "tmp"
TMP_DIR.mkdir(parents=True, exist_ok=True)


# ---------- helpers ------------------------------------------------------- #


def _run(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, check=True, capture_output=True, text=True)


def _is_url(s: str) -> bool:
    return s.startswith(("http://", "https://"))


def _absolutize(url: str, base: str) -> str:
    return urllib.parse.urljoin(base, url)


# Order matters: og:image is the most reliable "primary visual" hint, then
# twitter:image, then large rel="icon"/apple-touch-icon links, then any <img>.
_HTML_IMAGE_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (
        re.compile(
            r'<meta\b[^>]*property\s*=\s*["\']og:image(?::secure_url)?["\']'
            r'[^>]*content\s*=\s*["\']([^"\']+)["\']',
            re.IGNORECASE,
        ),
        "og:image",
    ),
    (
        re.compile(
            r'<meta\b[^>]*content\s*=\s*["\']([^"\']+)["\']'
            r'[^>]*property\s*=\s*["\']og:image(?::secure_url)?["\']',
            re.IGNORECASE,
        ),
        "og:image",
    ),
    (
        re.compile(
            r'<meta\b[^>]*name\s*=\s*["\']twitter:image["\']'
            r'[^>]*content\s*=\s*["\']([^"\']+)["\']',
            re.IGNORECASE,
        ),
        "twitter:image",
    ),
    (
        re.compile(
            r'<link\b[^>]*rel\s*=\s*["\'][^"\']*apple-touch-icon[^"\']*["\']'
            r'[^>]*href\s*=\s*["\']([^"\']+)["\']',
            re.IGNORECASE,
        ),
        "apple-touch-icon",
    ),
    (
        re.compile(
            r'<link\b[^>]*rel\s*=\s*["\'][^"\']*icon[^"\']*["\']'
            r'[^>]*href\s*=\s*["\']([^"\']+\.(?:svg|png))(?:\?[^"\']*)?["\']',
            re.IGNORECASE,
        ),
        "rel=icon",
    ),
]


def _extract_image_from_html(html: str, page_url: str) -> tuple[str, str] | None:
    """Return (image_url, source_label) found in an HTML document, or None.
    Only returns hits that resolve to absolute http(s) URLs."""
    for pattern, label in _HTML_IMAGE_PATTERNS:
        m = pattern.search(html)
        if m:
            candidate = _absolutize(m.group(1).strip(), page_url)
            if candidate.startswith(("http://", "https://")):
                return candidate, label
    return None


def _http_get(url: str, *, accept: str | None = None) -> tuple[bytes, str]:
    """Fetch URL and return (body, content_type). Follows redirects (urllib does
    this by default for 301/302). 30s timeout."""
    headers = {"User-Agent": "Mozilla/5.0"}
    if accept:
        headers["Accept"] = accept
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=30) as resp:
        ctype = (resp.headers.get_content_type() or "").lower()
        body = resp.read()
    return body, ctype


def _unique(path: Path) -> Path:
    if not path.exists():
        return path
    stem, suffix, parent = path.stem, path.suffix, path.parent
    i = 1
    while True:
        candidate = parent / f"{stem}_{i}{suffix}"
        if not candidate.exists():
            return candidate
        i += 1


def _slugify(name: str) -> str:
    """lowercase + non-alnum → underscore, collapse runs, trim edges.
    Used so both downloaded files and output files share the user's
    `lower_snake_case` convention."""
    s = re.sub(r"[^a-z0-9]+", "_", name.lower())
    s = re.sub(r"_+", "_", s).strip("_")
    return s or "file"


def _download(url: str, *, _hops: int = 0) -> Path:
    """Fetch a URL into TMP_DIR. If the response is HTML, look for og:image
    (or twitter:image / apple-touch-icon / rel=icon) and recurse into that.
    Recursion is capped at one hop to avoid pathological loops."""
    body, ctype = _http_get(url, accept=("image/svg+xml,image/png,image/*;q=0.9,text/html;q=0.5,*/*;q=0.1"))
    is_html = "html" in ctype or (
        ctype in ("", "text/plain") and body[:512].lstrip().lower().startswith((b"<!doctype html", b"<html"))
    )
    if is_html:
        if _hops >= 1:
            raise SystemExit("[to_square_svg] still HTML after one redirect hop; giving up")
        try:
            decoded = body.decode("utf-8", errors="replace")
        except Exception:
            decoded = ""
        hit = _extract_image_from_html(decoded, url)
        if not hit:
            raise SystemExit(
                f"[to_square_svg] {url} returned HTML but no og:image / icon "
                f"link was found. Pass the direct image URL instead."
            )
        real_url, label = hit
        print(
            f"[to_square_svg] page is HTML; following {label} → {real_url}",
            file=sys.stderr,
        )
        return _download(real_url, _hops=_hops + 1)

    raw_name = Path(urllib.parse.urlparse(url).path).name or "downloaded.bin"
    suffix = Path(raw_name).suffix.lower()
    if not suffix:
        # Pick a suffix from content-type so _detect_kind has a hint.
        suffix = {"image/svg+xml": ".svg", "image/png": ".png"}.get(ctype, ".bin")
    stem = _slugify(Path(raw_name).stem) or "downloaded"
    dest = _unique(TMP_DIR / f"{stem}{suffix}")
    dest.write_bytes(body)
    return dest


def _detect_kind(path: Path) -> str:
    head = path.read_bytes()[:1024]
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if b"<svg" in head or head.lstrip().startswith((b"<?xml", b"<!DOCTYPE")):
        # peek deeper for <svg
        if b"<svg" in path.read_bytes()[:8192]:
            return "svg"
    ext = path.suffix.lower()
    if ext == ".png":
        return "png"
    if ext == ".svg":
        return "svg"
    raise SystemExit(f"[to_square_svg] cannot determine type of {path}")


# ---------- PNG → square SVG --------------------------------------------- #


def png_to_square_svg(src: Path, out: Path, *, fuzz_pct: float = 2.0) -> Path:
    with tempfile.TemporaryDirectory() as td:
        trimmed = Path(td) / "trimmed.png"
        # -fuzz N% lets `-trim` treat near-uniform borders as the same colour.
        # This catches PNGs whose "white" edge is actually #fefefe / #fdfdfd
        # (anti-aliased / JPEG-converted backgrounds) — common for downloaded
        # icons. +repage clears the residual canvas/page metadata so the file
        # is genuinely the trimmed size, not the original with an offset.
        cmd = ["magick", str(src)]
        if fuzz_pct > 0:
            cmd += ["-fuzz", f"{fuzz_pct}%"]
        cmd += ["-trim", "+repage", str(trimmed)]
        _run(cmd)
        dims = _run(["magick", "identify", "-format", "%w %h", str(trimmed)]).stdout.strip()
        w_str, h_str = dims.split()
        w, h = int(w_str), int(h_str)
        side = max(w, h)
        x = (side - w) / 2
        y = (side - h) / 2
        b64 = base64.b64encode(trimmed.read_bytes()).decode("ascii")

    svg = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<svg xmlns="http://www.w3.org/2000/svg" '
        'xmlns:xlink="http://www.w3.org/1999/xlink" '
        f'viewBox="0 0 {side} {side}" width="{side}" height="{side}">'
        f'<image x="{_fmt(x)}" y="{_fmt(y)}" width="{w}" height="{h}" '
        f'preserveAspectRatio="none" '
        f'xlink:href="data:image/png;base64,{b64}"/>'
        "</svg>\n"
    )
    out.write_text(svg, encoding="utf-8")
    return out


# ---------- SVG-wrapped-PNG detection ------------------------------------ #

# Some "SVG" files are really a single base64-embedded PNG inside <image>
# (e.g. exporters that convert raster to SVG by wrapping). For these, our
# SVG bbox path can't see the PNG's actual whitespace borders — we have to
# extract the PNG and run the PNG branch instead.
_SVG_TAG_RE = re.compile(r"<([a-zA-Z][\w:-]*)\b", re.MULTILINE)
_VISIBLE_TAGS = {
    "path",
    "rect",
    "circle",
    "ellipse",
    "line",
    "polygon",
    "polyline",
    "text",
    "tspan",
    "use",
    "foreignObject",
}
_DATA_PNG_RE = re.compile(
    r'href\s*=\s*"data:image/png;base64,([A-Za-z0-9+/=\s]+)"',
    re.IGNORECASE,
)


def _extract_wrapped_png(svg_text: str) -> bytes | None:
    """If the SVG contains a single <image href="data:image/png;base64,..."/>
    and no other visible drawing primitives, return the decoded PNG bytes.
    Otherwise return None."""
    tags = [t.lower() for t in _SVG_TAG_RE.findall(svg_text)]
    image_count = sum(1 for t in tags if t == "image")
    if image_count != 1:
        return None
    if any(t in _VISIBLE_TAGS for t in tags):
        return None
    m = _DATA_PNG_RE.search(svg_text)
    if not m:
        return None
    try:
        return base64.b64decode(re.sub(r"\s+", "", m.group(1)), validate=False)
    except Exception:
        return None


# ---------- SVG → square SVG --------------------------------------------- #

_NUM = r"-?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?"
_VIEWBOX_RE = re.compile(rf'viewBox\s*=\s*"({_NUM})\s+({_NUM})\s+({_NUM})\s+({_NUM})"')
_OPEN_SVG_RE = re.compile(r"<svg\b[^>]*>", re.DOTALL)
# Relative / context-dependent length units that Inkscape collapses to ~0
# when there is no font-size context (e.g. lobe-icons ship `width="1em"`).
_RELATIVE_UNIT_RE = re.compile(
    r"^\s*" + _NUM + r"\s*(em|ex|%|vw|vh|vmin|vmax|ch|rem)\s*$",
    re.IGNORECASE,
)


def _fmt(v: float) -> str:
    """Compact numeric formatting: drop trailing .0 / zeros."""
    if abs(v - round(v)) < 1e-9:
        return str(int(round(v)))
    return f"{v:.6f}".rstrip("0").rstrip(".")


def _strip_attr(open_tag: str, name: str) -> str:
    open_tag = re.sub(rf'\s+{name}\s*=\s*"[^"]*"', "", open_tag)
    open_tag = re.sub(rf"\s+{name}\s*=\s*'[^']*'", "", open_tag)
    return open_tag


def _read_attr(open_tag: str, name: str) -> str | None:
    m = re.search(rf'\s{name}\s*=\s*"([^"]*)"', open_tag)
    if m:
        return m.group(1)
    m = re.search(rf"\s{name}\s*=\s*'([^']*)'", open_tag)
    return m.group(1) if m else None


def _normalize_root_dimensions(text: str) -> str:
    """Replace relative `width`/`height` on the root <svg> with concrete pixel
    values from `viewBox`. Inkscape's bbox query collapses `1em` / `100%` to
    near-zero when there is no font-size / containing-block context; doing this
    rewrite up-front gives Inkscape a sane render box."""
    m = _OPEN_SVG_RE.search(text)
    if not m:
        return text
    open_tag = m.group(0)
    vb = _read_attr(open_tag, "viewBox")
    if not vb:
        return text
    parts = vb.split()
    if len(parts) != 4:
        return text
    try:
        vb_w, vb_h = float(parts[2]), float(parts[3])
    except ValueError:
        return text
    if vb_w <= 0 or vb_h <= 0:
        return text

    width = _read_attr(open_tag, "width")
    height = _read_attr(open_tag, "height")
    needs_w = width is None or _RELATIVE_UNIT_RE.match(width) is not None
    needs_h = height is None or _RELATIVE_UNIT_RE.match(height) is not None
    if not (needs_w or needs_h):
        return text

    new_open = open_tag
    if needs_w:
        new_open = _strip_attr(new_open, "width")
    if needs_h:
        new_open = _strip_attr(new_open, "height")
    inject = ""
    if needs_w:
        inject += f' width="{_fmt(vb_w)}"'
    if needs_h:
        inject += f' height="{_fmt(vb_h)}"'
    new_open = new_open[:-1].rstrip() + inject + ">"
    return text[: m.start()] + new_open + text[m.end() :]


def svg_to_square_svg(src: Path, out: Path) -> Path:
    raw = src.read_text(encoding="utf-8", errors="replace")
    sanitized = _normalize_root_dimensions(raw)

    with tempfile.TemporaryDirectory() as td:
        prepared = Path(td) / "prepared.svg"
        prepared.write_text(sanitized, encoding="utf-8")
        # Step 1: ask Inkscape to rewrite the SVG so its viewBox matches the
        # actual rendered content bounding box. --export-area-drawing is the
        # contract that gives us a tight bbox even when the original viewBox
        # excludes content.
        trimmed = Path(td) / "trimmed.svg"
        _run(
            [
                "inkscape",
                str(prepared),
                "--export-area-drawing",
                "--export-plain-svg",
                "--export-type=svg",
                f"--export-filename={trimmed}",
            ]
        )
        text = trimmed.read_text(encoding="utf-8", errors="replace")

    m = _VIEWBOX_RE.search(text)
    if not m:
        raise SystemExit("[to_square_svg] inkscape output has no viewBox; cannot determine content bbox")
    cx, cy, cw, ch = (float(m.group(i)) for i in range(1, 5))
    if cw <= 0 or ch <= 0:
        raise SystemExit(f"[to_square_svg] degenerate bbox: {cw}x{ch}")
    # Guard against numerical garbage (e.g. ~1e-45) that Inkscape produces
    # when the SVG has unresolvable units. A sane icon bbox is well above 1e-3.
    if max(cw, ch) < 1e-3:
        raise SystemExit(
            f"[to_square_svg] near-zero bbox ({cw}x{ch}); the source SVG "
            f"likely has relative units (em/%) that did not resolve. "
            f"Open the file and ensure root width/height are absolute."
        )

    side = max(cw, ch)
    new_x = cx - (side - cw) / 2.0
    new_y = cy - (side - ch) / 2.0
    new_vb = f"{_fmt(new_x)} {_fmt(new_y)} {_fmt(side)} {_fmt(side)}"

    # Step 2: rewrite the root <svg> opening tag with the new square viewBox
    # and matched width/height. We only touch the *root* svg tag — nested svg
    # elements inside the file are left alone.
    open_match = _OPEN_SVG_RE.search(text)
    if not open_match:
        raise SystemExit("[to_square_svg] no <svg> root element found")
    open_tag = open_match.group(0)
    new_open = open_tag
    for attr in ("viewBox", "width", "height", "preserveAspectRatio"):
        new_open = _strip_attr(new_open, attr)
    new_open = new_open[:-1].rstrip() + f' viewBox="{new_vb}" width="{_fmt(side)}" height="{_fmt(side)}">'
    rewritten = text[: open_match.start()] + new_open + text[open_match.end() :]
    out.write_text(rewritten, encoding="utf-8")
    return out


# ---------- main --------------------------------------------------------- #


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(
        description="Normalize a PNG/SVG/URL into a square SVG with content "
        "centred and the long edge flush against the canvas."
    )
    ap.add_argument("input", help="local path or http(s) URL")
    ap.add_argument(
        "-o",
        "--output",
        help="output path (default: {tmp}/<slug>_hermes.svg)",
    )
    ap.add_argument(
        "--name",
        help="explicit slug for the output filename (e.g. --name serena → "
        "serena_hermes.svg). Overrides the auto-derived slug. Ignored "
        "when -o/--output is supplied.",
    )
    ap.add_argument(
        "--fuzz",
        type=float,
        default=2.0,
        metavar="PCT",
        help="PNG-trim fuzz tolerance in percent (default 2). Use 0 for "
        "strict matching, raise to ~10 if light-gray/off-white borders "
        "are not being detected as background.",
    )
    args = ap.parse_args(argv)

    src_arg = args.input.strip()
    if _is_url(src_arg):
        src = _download(src_arg)
        print(f"[to_square_svg] downloaded → {src}", file=sys.stderr)
    else:
        src = Path(src_arg).expanduser().resolve()
        if not src.is_file():
            raise SystemExit(f"[to_square_svg] file not found: {src}")

    kind = _detect_kind(src)

    # SVG-wrapped-PNG fast-path: if the "SVG" is just a base64 PNG in an
    # <image>, extract and treat as PNG so we can trim its white borders.
    if kind == "svg":
        svg_text = src.read_text(encoding="utf-8", errors="replace")
        png_bytes = _extract_wrapped_png(svg_text)
        if png_bytes is not None:
            extracted = TMP_DIR / f"{_slugify(src.stem)}_extracted.png"
            extracted = _unique(extracted)
            extracted.write_bytes(png_bytes)
            print(
                f"[to_square_svg] svg wraps a single PNG; extracted → {extracted}",
                file=sys.stderr,
            )
            src = extracted
            kind = "png"

    if args.output:
        out = Path(args.output).expanduser().resolve()
        out.parent.mkdir(parents=True, exist_ok=True)
    else:
        slug = _slugify(args.name) if args.name else _slugify(src.stem)
        out = _unique(TMP_DIR / f"{slug}_hermes.svg")

    if kind == "png":
        png_to_square_svg(src, out, fuzz_pct=args.fuzz)
    elif kind == "svg":
        svg_to_square_svg(src, out)
    else:
        raise SystemExit(f"[to_square_svg] unsupported kind: {kind}")

    # Final line on stdout = absolute output path (machine-readable).
    print(out)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
