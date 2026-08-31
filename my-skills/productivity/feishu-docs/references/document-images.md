# Feishu Document Images and Covers

Use this reference only for writing raster images into a Feishu docx document.

## Source selection

- Generated image or chart: pass the producing tool's relative
  `workspace_path` as `image_path`.
- Image embedded in a referenced Feishu docx/wiki document: call
  `feishu_doc_manage(action="read_url", include_images=true)` and use the
  relative `image_path` values from its `[DOCUMENT_IMAGES]` manifest. Each
  raster is downloaded into `feishu-doc-images/<doc-token>/` inside the current
  group's isolated workspace; failed or known import-placeholder blocks are
  reported under `errors` instead of being presented as valid images. A
  document cover is listed first with `role="cover"`; ordinary image blocks use
  `role="body"`.
- Image attached to the current message or explicit reply: pass its zero-based
  image-only `attachment_index`.
- Never pass an arbitrary absolute path in a Feishu group.
- Do not infer an old attachment from chat history. Only the current turn and
  its explicit reply are authorized sources.

Supported inputs are PNG, JPEG, GIF, WebP, BMP, and TIFF, up to 20 MiB. The
current image and chart generators already emit compatible files below this
limit.

## Insert into the document body

Call `feishu_doc_manage` with `action="insert_image"`, `doc_token`, and exactly
one image source. Optional presentation fields are `align`, `caption`, `width`,
and `height`.

Placement options:

- Omit placement fields to append at the end only when the user did not request
  a semantic location.
- Use `position="before"` or `position="after"` with a unique top-level
  `anchor_text` when the user names a section.
- Use `insert_index` only when a reliable top-level block index is already
  known. It cannot precede the document's version table.

The fixed script creates an empty Image Block, uploads the binary with
`parent_type=docx_image`, patches `replace_image`, then appends the standard
version row. If upload, patching, or versioning fails, it removes the image
block and restores the previous version-table rows on a best-effort basis.
When only `width` or `height` is supplied, the script reads the source pixels
and derives the missing dimension. This is required because Feishu otherwise
may retain the source pixel height beside a reduced display width, producing a
tall image block with large blank bands. Omit both dimensions for native sizing,
or provide one dimension and let the script preserve the source aspect ratio.
The success result reports the resolved `width` and `height`; use those values
when verifying a body image that requested an explicit display size.

## Set or replace the cover

Call `feishu_doc_manage` with `action="set_cover"`, `doc_token`, and exactly one
image source. `offset_ratio_x` and `offset_ratio_y` are optional finite crop
offsets; omit them for Feishu's default centered view.

The fixed script uploads the image against the document ID, patches
`update_cover`, and appends the version row. It snapshots the old cover metadata
and restores it if versioning fails.

## Generated media destination

When `group_image_generate` or `group_chart_generate` succeeds for a request
whose explicit destination is a referenced Feishu document, pass its
`workspace_path` to the document action. Do not include the returned
`media_directive` unless the user also asked to receive a separate image in the
chat; document insertion and chat delivery are distinct destinations.

A group document successfully produced by `feishu_doc_manage(action="create")`
may receive generated media during the same turn. Only the exact token parsed
from that successful fixed-script result is authorized; failed creation,
another tool's output, arbitrary tokens, and later turns receive no grant. The
grant is keyed by the internal Hermes turn ID rather than thread-local hook
state, so a create and its follow-up media write may run in different workers.

## Public web images

Do not rely on Feishu's Markdown importer to fetch a remote image URL. The
import task may return success while silently replacing the image with a
standard“无法导入该图片”bitmap.

For sourced web images in a group:

1. Call `feishu_doc_manage(action="stage_image_urls", urls=[...])`. The fixed
   staging script permits public HTTPS only, checks every redirect and TCP
   destination against Hermes SSRF policy, rejects credential-bearing URLs,
   caps bytes, validates raster magic and decodability, and writes only under
   the current group workspace.
2. Keep source attribution as ordinary Markdown text or a link, but remove all
   Markdown/HTML image embedding from content passed to create/append/rebuild.
3. After the target document exists, call `insert_image` with each returned
   `workspace_path`. Use `replace_image` only when repairing a known existing
   top-level image block.
4. Read the document back. `[IMAGE_IMPORT_ERRORS]` means visual verification
   failed and names the affected block IDs.

Only claim images that actually returned a staging path and a successful
document image result. Do not infer that every image mentioned in research or
in the Markdown source was uploaded.

## Reuse in HyperTeX

For a deck based on an existing Feishu document, read it with
`include_images=true`, combine the returned `image_path` values with any
generated/chart `workspace_path` values, and pass those relative paths as
HyperTeX `asset_paths`. The Hermes sandbox accepts only files that resolve
inside the current group's workspace, copies them into HyperTeX's private
staging directory, and rejects missing files, symlinks, cross-group paths, and
requests above the configured count/size bounds.

## Permissions and failure handling

The bot needs document edit permission and media-upload permission. A 403 means
the application cannot edit the target document or upload media there; do not
create an unrelated replacement document. A media token from another document
must never be reused directly.
