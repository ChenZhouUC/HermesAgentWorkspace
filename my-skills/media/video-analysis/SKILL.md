---
name: video-analysis
description: Analyze local videos with native tools or sampled frames.
---

# Video Analysis

Analyze local or linked video while preserving the best available source
quality. Prefer Hermes' native video path; use frame extraction only as a
deliberate fallback or when the user specifically needs frame-level evidence.

## When to Use

Use this skill for video description, event inspection, visual comparison,
timeline analysis, or checking a specific moment in an `.mp4`, `.mov`, `.webm`,
`.avi`, `.mkv`, or `.mpeg` file.

## Routing

1. **Already analyzed by the inbound Gateway:** Use the supplied native or
   sidecar analysis. Do not reprocess the same attachment unless the user asks
   for a more specific inspection or the existing result is explicitly
   incomplete.
2. **`video_analyze` is available:** Send the local path or URL directly with a
   focused question. This preserves motion, audio cues, text overlays, and scene
   transitions better than sparse frames.
3. **Native analysis is unavailable, unsupported, too large, or the task is
   frame-specific:** Use the `ffmpeg` fallback below in an owner/private or CLI
   session.

Feishu groups do not have `terminal`; never instruct a group session to run
`ffmpeg` or probe host paths. If the Gateway could not analyze the attachment,
ask the user to continue in an owner/private or CLI session.

## Frame-Extraction Fallback

1. Inspect duration without decoding the whole file:

   ```bash
   ffprobe -v error -show_entries format=duration \
     -of default=noprint_wrappers=1:nokey=1 /path/to/video.mp4
   ```

2. Choose timestamps that match the question. For a general overview, sample
   the beginning, middle, end, and any visible scene boundaries; do not assume
   three arbitrary frames represent rapid motion accurately.

3. Extract individual frames into a task-specific temporary directory:

   ```bash
   ffmpeg -y -ss 00:00:10 -i /path/to/video.mp4 \
     -frames:v 1 /tmp/video-audit/frame-001.jpg
   ```

4. Inspect the images with the available image-vision path. Return frame files
   to the user only when they asked for them; otherwise report the timestamps
   used and the sampling limitation.

## Pitfalls

- Do not claim full-video understanding from a few sampled frames.
- Do not fan out dozens of frame-analysis calls when one native video request is
  available.
- Avoid Python video stacks as the first fallback; `ffprobe` and `ffmpeg` are
  lighter and more predictable for deterministic extraction.
- A single-frame output does not need a `%03d` sequence pattern when
  `-frames:v 1` is present.
