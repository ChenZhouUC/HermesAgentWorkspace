---
name: image-generation-fallback
description: "Fallback method to generate images via Pollinations AI when native tools are unavailable."
category: creative
---

# Image Generation Fallback

Use this skill when the user requests an image generation (e.g., meme, portrait, artwork) and the built-in `image_gen` tool is disabled, missing, or fails.

## Trigger

- User asks for image generation.
- Built-in `image_gen` tool is not available, lacks API keys, or throws an error.

## Workflow

1. **Prepare the prompt**: Write a highly detailed, descriptive prompt in English. Include style tags (e.g., "Epic fantasy game art style", "dynamic lighting", "high quality").
2. **Execute Python code**: Use `execute_code` to make a GET request to the Pollinations AI endpoint and save the image directly to the isolated temp directory `~/.hermes/tmp/`.

## Code Template

```python
import urllib.request
import urllib.parse
import os

prompt = "A highly detailed portrait of..." # Replace with your English prompt
encoded_prompt = urllib.parse.quote(prompt)
# Options: width, height, nologo=true
url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=1024&height=1024&nologo=true"

# MUST save to ~/.hermes/tmp/
save_dir = os.path.expanduser("~/.hermes/tmp")
os.makedirs(save_dir, exist_ok=True)
save_path = os.path.join(save_dir, "generated_image.jpg")

req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
with urllib.request.urlopen(req) as response, open(save_path, 'wb') as out_file:
    out_file.write(response.read())

print(f"Saved to {save_path}")
```

3. **Return the image**: Once saved, present the image to the user using the native media markdown: `MEDIA:/Users/username/.hermes/tmp/generated_image.jpg` (substitute absolute path).

## Pitfalls

- **DO NOT** save the image to `~/` or the current working directory unless explicitly requested. Always default to `~/.hermes/tmp/`.
- Ensure `nologo=true` is in the URL parameters to remove the watermark.
- URL-encode the prompt properly using `urllib.parse.quote`.
- Always include a `User-Agent` header, or the request might be blocked by the API.
