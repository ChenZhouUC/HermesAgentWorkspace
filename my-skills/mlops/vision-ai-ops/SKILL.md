---
name: vision-ai-ops
description: "Operational heuristics for Vision AI, YOLO preprocessing, VLM token economics, and video streams."
version: 1.0.0
author: Hermes Agent
metadata:
  hermes:
    tags: [computer-vision, yolo, vlm, tokens, inference, video-analytics]
    category: mlops
---

# Vision AI Operations & Token Economics

This skill codifies operational best practices, video stream configurations, YOLO preprocessing requirements, and token cost heuristics for Vision-Language Models (VLMs).

## 1. VLM Token Economics (GPT-4o, Gemini 3.1 Pro, GPT-5.5)

When passing images (e.g., 1080p frames) to advanced VLMs, token consumption behaves differently across model generations:

### The Reasoning Token Trap (GPT-5.5 / Gemini 3.1 Pro)

- **Symptom**: A single 1080p image + simple prompt suddenly costs **~5000+ tokens**.
- **Cause**: Next-generation models extract high-resolution spatial features and automatically generate **Hidden Reasoning Tokens (CoT)** before answering. These reasoning tokens are billed as output.
- **Mitigation**: If you only need simple spatial detection ("is there a person?") rather than complex logic, lower the model's reasoning effort (`reasoning_effort=low` for OpenAI, or cap `thinkingBudget` for Gemini).

### High-Resolution Tiling (GPT-4o / Claude 3.5)

- **Native Cost**: Uncompressed 1080p (1920x1080) usually slices into ~6 grid tiles, costing **~1100 to 1500 tokens**.
- **Mitigation**: Before API transmission, explicitly `cv2.resize()` the image to **< 512x512** (low-detail mode). This drops the OpenAI token cost to a flat **85 tokens** while preserving enough spatial accuracy for large object detection.

### Fixed Pricing (Gemini 1.5)

- Gemini 1.5 Pro/Flash uses a flat rate (typically ~258 tokens per image/frame), ignoring aspect-ratio tiling. Highly economical for multi-frame video ingestion (provided reasoning tokens are not bloated).

## 2. YOLO Preprocessing Constraints

Before feeding images to standard YOLO models (e.g., YOLOv5, YOLOv8):

- **The 32-Stride Rule**: YOLO backbone networks typically have a maximum stride of 32. Input dimensions MUST be multiples of 32 (e.g., 416x416, 512x512, 640x640).
- **Default Sizes**: Standard (P5) models default to `640x640`. High-res (P6) models default to `1280x1280` (useful for dense micro-targets like crowds or distant license plates).
- **Letterboxing**: To handle wide images (e.g., 16:9 1080p), YOLO scales the longest edge to the target size (e.g., 640) and pads the shorter edge with gray/black pixels to the nearest multiple of 32 (e.g., 640x384). **Never distort/squash** the aspect ratio.

## 3. Video Stream Optimization for AI Analytics

When configuring RTSP streams for Edge/Cloud AI processing:

- **Framerate**: Set to **10-15 FPS**. 30 FPS is visually smooth for humans but wastes 50%+ compute for object detection/ReID tasks.
- **Bitrate Mode**: Use **VBR (Variable Bitrate)** over CBR to drastically save bandwidth during static scenes.
- **Codec**:
  - **H.264 (AVC)**: The universal fallback for hardware decoding (OpenCV/FFmpeg).
  - **H.265 (HEVC)**: Cuts bandwidth in half but requires dedicated hardware decoders (e.g., on Sophgo/RK3576 NPUs).
