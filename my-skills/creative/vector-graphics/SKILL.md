---
name: vector-graphics
description: Vector graphics manipulation, SVG conversions, and CLI automation (potrace, Inkscape).
---

# Vector Graphics Operations

## Raster to Vector (PNG to SVG)

### GUI Method (Inkscape)

Simple "Save As" will only embed the PNG. To generate a true vector path:

1. Import PNG and select the object.
2. Go to `Path` -> `Trace Bitmap` (Shift+Option+B / Shift+Alt+B).
3. Use "Single scan" (Brightness cutoff) for line-art/monochrome, or "Multiple scans" for colors.
4. Check "Remove background" for transparency.
5. Click "Apply". Delete the original raster layer underneath.
6. Save as "Plain SVG" to strip software-specific XML tags.

### CLI Method (potrace)

Inkscape's headless CLI trace support is poor. For automated or batch processing of pure black/white or line art in the terminal, use `potrace`:

```bash
# Install dependencies (macOS)
brew install potrace imagemagick

# Convert PNG to potrace-compatible PNM format
magick input.png temp.pnm

# Vectorize to SVG and clean up
potrace temp.pnm -s -o output.svg && rm temp.pnm
```
