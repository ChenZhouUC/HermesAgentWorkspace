---
name: image-manipulation-pillow
description: Workflows for programmatically manipulating images (memes, text overlays, canvas expansion) using Python and Pillow.
category: creative
---

# Image Manipulation & Meme Generation (Pillow)

Use this skill when asked to add text to images, create memes, or perform basic image manipulations (cropping, padding, canvas expansion) using Python's Pillow (`PIL`) library.

## Key Workflows

### 1. Expanding Canvas & Adding Text (Meme Style)

When adding text next to or below an image, do not just draw over the original image. Create a new larger canvas and paste the original image into it.

```python
from PIL import Image, ImageDraw, ImageFont

img = Image.open(input_path)
orig_w, orig_h = img.size

# Example: Expand left side for text padding
pad_w = max(180, int(orig_w * 0.7))
new_img = Image.new('RGB', (orig_w + pad_w, orig_h), 'white')
# Paste original image on the right
new_img.paste(img, (pad_w, 0))
```

### 2. Handling Chinese Fonts (macOS)

Do not assume standard Windows/Linux fonts. On macOS, use these fallback paths for Chinese text, as `PingFang.ttc` may not be easily accessible at the root level:

```python
import os
font_paths = [
    "/System/Library/Fonts/STHeiti Medium.ttc",
    "/System/Library/Fonts/STHeiti Light.ttc",
    "/Library/Fonts/Arial Unicode.ttf"
]
font_path = next((fp for fp in font_paths if os.path.exists(fp)), None)
if font_path:
    font = ImageFont.truetype(font_path, 28, index=0)
```

### 3. Centering Multiline Text

Use `multiline_textbbox` to calculate text dimensions accurately (the older `textsize` method is deprecated and will fail in modern Pillow versions).

```python
draw = ImageDraw.Draw(new_img)
bbox = draw.multiline_textbbox((0, 0), text, font=font, align='center', spacing=10)
text_w = bbox[2] - bbox[0]
text_h = bbox[3] - bbox[1]

# Center horizontally in the padded area, center vertically
x = (pad_w - text_w) / 2
y = (orig_h - text_h) / 2
draw.multiline_text((x, y), text, font=font, fill=(0, 0, 0), align='center', spacing=10)
```

## Pitfalls & Pro-Tips

- **Quick Image Inspection**: If running a quick `python3 -c` script to inspect image dimensions times out or is blocked, use the system `file <image_path>` command. It instantly outputs the image resolution, format, and color depth without spinning up a Python interpreter.
- **Environment Isolation**: Always check if there's a local virtual environment (e.g., `.venv` or `.meme_venv`) in the working directory before installing Pillow or running scripts, to avoid polluting the global environment. Write throwaway scripts to `~/.hermes/tmp/`.
