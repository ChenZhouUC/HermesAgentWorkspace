# Inkscape PNG to SVG Vectorization

- **GUI Method:** `Path` -> `Trace Bitmap` (`Shift + Option + B`). Adjust brightness cutoff for single scan, or multiple scans for color. Check "Remove background". Delete original PNG image underneath after applying.
- **CLI Method:** Inkscape headless tracing is notoriously unreliable. Use `potrace` combined with ImageMagick for terminal-based black & white vectorization:
  ```bash
  magick input.png temp.pnm
  potrace temp.pnm -s -o output.svg
  ```
