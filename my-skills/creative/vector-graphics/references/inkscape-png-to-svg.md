# Converting PNG to SVG (Vectorization)

Simply "saving as SVG" in Inkscape only embeds the PNG in an image tag. True vectorization requires tracing the bitmap to generate paths.

## GUI Method (Inkscape)

1. Import the PNG.
2. Select the image (shortcut `S`).
3. Go to `Path` -> `Trace Bitmap` (shortcut `Shift + Option + B`).
4. Select `Single scan` (Brightness cutoff) for monochrome/line-art, or `Multiple scans` (Colors) for color images.
5. Check `Remove background` to generate a transparent base.
6. Click `Apply`.
7. Delete the original underlying PNG image and save as `Plain SVG` to avoid Inkscape-specific XML bloat.

## CLI Method (Headless/Automation)

Inkscape's headless trace support is unreliable. The standard CLI fallback uses `potrace`:

```bash
# 1. Install dependencies
brew install potrace imagemagick

# 2. Convert PNG to PNM (potrace input format)
magick input.png temp.pnm

# 3. Vectorize and clean up
potrace temp.pnm -s -o output.svg && rm temp.pnm
```
