---
name: video-analysis
description: Use when visually analyzing local video files such as .mp4 or .mov by extracting representative frames with ffmpeg and returning them via MEDIA.
---

# Video Analysis

When the user provides a local video file (e.g., `.mp4`, `.mov`) and asks you to analyze it visually or "see" what is happening, you cannot directly ingest the video file into your vision tools.

## Core Workflow

Instead of failing or claiming you cannot see the video, use a frame-extraction workaround:

1. **Find Duration:** Use `ffprobe` to determine the video duration.

   ```bash
   ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 /path/to/video.mp4
   ```

2. **Extract Keyframes:** Select 3-5 meaningful timestamps across the duration and extract them as `.jpg` images using `ffmpeg`.

   ```bash
   ffmpeg -y -i /path/to/video.mp4 -ss 00:00:10 -vframes 1 /tmp/frame1.jpg
   ```

3. **Return Images:** Send the extracted frames back to the user inline using the `MEDIA:<absolute_path>` syntax.
   `MEDIA:/tmp/frame1.jpg`
4. **Clarify limitations:** Explain that you extracted representative frames to evaluate the content. If they need a precise evaluation of specific moments (e.g., a rapid animation effect or UI state), instruct them to provide a direct screenshot in the chat.

## Pitfalls

- **No Python Vision Libraries First:** Do not try to read the video with `PIL`, `numpy` (which might not be installed), or `cv2` before simply extracting frames with `ffmpeg`. `ffmpeg` is fast, reliable, and available in the environment.
- **Single Image Syntax:** When using `ffmpeg` to output a single image, if you omit `%03d` formatting, you will get sequence pattern warnings. This is fine as long as `-vframes 1` is supplied.
