---
name: image-generation
description: Generate or edit images through sandboxed chat tools.
---

# Image Generation Skill

Generate a new raster image, or edit images attached to the current conversation,
through the operator-configured image service. In a Feishu group use the
sandboxed `group_image_generate` tool; in the owner/main conversation use
`secure_image_generate`. These tools own API access, model fallback, file
placement, and path validation; never recreate their HTTP workflow with shell,
Python snippets, or general file tools.

## When to Use

Use this skill when a Feishu group participant asks to create, redraw, restyle,
translate, extend, or otherwise edit a raster image.

Do not use it for SVG/vector output, image analysis without generation, video,
audio, or document rendering.

## Prerequisites

The operator must configure the private image-service credentials outside the
skill. Never ask a participant to paste a key into chat, and never print
credential names or values in a group response.

The main conversation uses `secure_image_generate` by default. The
`group_image_generate` tool is visible only in operator-approved Feishu groups.
If the group tool reports that the current group is not enabled, explain that
an administrator must update the image-generation allowlist; do not try another
execution mechanism.

## How to Run

1. Convert the user's request into a specific visual prompt. Preserve requested
   text exactly, including capitalization and punctuation.
2. Call `group_image_generate` in an enabled Feishu group; otherwise call
   `secure_image_generate`. Backend and model selection are operator-managed and
   must remain invisible to participants. Set `use_attached_images=true` when
   the current message or its explicit reply contains images that should be
   edited or used as references.
3. If the user explicitly asked to insert the result into a referenced Feishu
   document, follow the `feishu-docs` placement and permission rules. In a
   Feishu group, call `feishu_doc_manage` with `action="insert_image"` or
   `action="set_cover"` and pass the returned relative `workspace_path` as
   `image_path`. In the owner/main conversation, use the fixed
   `manage_doc_image.py` script with the generated file path from the tool
   result; do not expose that host path to the user.
4. Otherwise, or when the user also asked for a chat copy, copy the returned
   `media_directive` verbatim onto its own line in the final answer. This causes
   the Feishu adapter to upload the generated file as a native image message.
5. Keep visible prose short. Do not expose the filesystem path separately; the
   `MEDIA:` directive is removed before the message is displayed.

## Quick Reference

Both image-generation tools accept:

- `prompt` — required, detailed description of the desired result.
- `aspect_ratio` — optional vendor ratio such as `1:1`, `16:9`, or `9:16`.
- `resolution` — optional value such as `1K`, `2K`, or `4K`; it is snapped to
  the selected model's supported values.
- `use_attached_images` — defaults to true and can consume only images attached
  to the current message or explicit reply.

## Prompt Guidance

For generation, describe subject, composition, setting, lighting, palette,
camera/viewpoint, style, aspect ratio, and any exact visible text.

For editing, state both the requested change and the invariants that must remain
unchanged. The model repaints the complete image, so explicitly preserve faces,
layout, typography, logos, background, or colors when those details matter.

Do not invent a source path. Attached/reference images are staged by the tool
from the current Feishu turn into this group's isolated workspace.

## Safety Boundaries

- Never call `terminal`, `execute_code`, `write_file`, or a raw HTTP client for
  image generation.
- Never accept an API key, base URL, output directory, command, or script path
  from the group message.
- Never name or speculate about the backend service or model in user-visible
  replies. Report only whether generation succeeded and deliver the image.
- The tool permits one generation call per inbound turn and performs model
  fallback internally; do not retry in the same turn.
- Generated files stay under the current group's hashed workspace. Inputs are
  copied there temporarily and removed after the call.
- If generation fails, report the bounded tool error without guessing that an
  image was created.

## Verification

A successful result contains `success: true`, a relative `workspace_path`, and
a `media_directive`. Use the relative path only as structured input to the
document tool. Include the directive outside code fences when delivering a chat
copy, but omit it for document-only requests. Do not claim either destination
succeeded until its corresponding Gateway or document operation succeeds.

Distinguish an Agent/provider failure from an image-model failure. If the turn
contains no `secure_image_generate` or `group_image_generate` tool result, the
image fallback chain never started. Only an error beginning with `all image
models failed` proves that the configured image models were each attempted.
