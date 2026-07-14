#!/usr/bin/env python3
"""Validate Hermes LLM wiki Layer 2 consistency.

This script intentionally uses only the Python standard library so it can run
from hooks, agents, or ad-hoc maintenance sessions without dependency setup.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlsplit


ACTIVE_DIRS = {
    "entities": "entity",
    "concepts": "concept",
    "comparisons": "comparison",
    "queries": "query",
}

INDEX_SECTIONS = {
    "Entities": "entities",
    "Concepts": "concepts",
    "Comparisons": "comparisons",
    "Queries": "queries",
}

INDEX_ENTRY_RE = re.compile(r"^- `(entities|concepts|comparisons|queries)/([a-z0-9]+(?:-[a-z0-9]+)*)\.md` - .+$")

META_FILES = {"SCHEMA.md", "index.md", "log.md"}
META_FILES_CASEFOLD = {name.casefold() for name in META_FILES}
META_SLUGS = {Path(name).stem for name in META_FILES}
META_SLUGS_CASEFOLD = {slug.casefold() for slug in META_SLUGS}
ACTIVE_FILENAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*\.md$")
LIVING_TOPIC_DIR_RE = re.compile(r"^[A-Za-z0-9]+(?:-[A-Za-z0-9]+){1,2}$")
LIVING_SEMANTIC_FIELDS = {"type", "tags", "concepts", "links", "aliases", "category"}
LAYER1_SOURCE_PREFIXES = ("_living/", "raw/")

ALLOWED_TAGS = {
    "edge-inference",
    "rk3576",
    "sophgo",
    "npu",
    "tpu",
    "edge-computing",
    "architecture",
    "llm",
    "vlm",
    "transformer",
    "state-space",
    "reasoning",
    "quantization",
    "tensorrt",
    "onnx",
    "system-prompt",
    "alignment",
    "agent",
    "orchestration",
    "harness",
    "react",
    "context-management",
    "sandbox",
    "hitl",
    "protocol",
    "multi-agent",
    "macos",
    "ops",
    "gateway",
    "pipeline",
    "spacesight",
    "product-management",
    "compliance",
    "computer-vision",
    "reid",
    "clustering",
    "tcs",
    "statistics",
    "proof",
    "complexity",
    "algorithm",
    "math",
    "logic",
    "wiki",
    "markdown",
    "obsidian",
    "tool",
    "comparison",
    "benchmark",
    "paper",
}

REQUIRED_FRONTMATTER = {
    "title",
    "created",
    "updated",
    "type",
    "tags",
    "sources",
    "confidence",
}

CHECKS = (
    (
        "Active Layer 2 directories contain no zero-byte Markdown files",
        ("zero_byte_active",),
    ),
    (
        "Active Layer 2 filenames use lowercase kebab-case",
        ("invalid_active_filenames",),
    ),
    (
        "Wiki root contains no floating Active Layer 2 nodes",
        ("root_floating_nodes",),
    ),
    (
        "Active Layer 2 slugs are unique across the wiki",
        ("duplicate_slugs",),
    ),
    (
        "Meta pages exist and start with YAML frontmatter",
        ("missing_meta_pages", "missing_meta_frontmatter"),
    ),
    (
        "Active Layer 2 frontmatter is complete and schema-aligned",
        (
            "missing_frontmatter",
            "missing_fields",
            "type_dir_mismatch",
            "invalid_dates",
            "empty_tags",
            "invalid_tags",
            "empty_sources",
            "invalid_source_entries",
            "invalid_source_scope",
            "missing_source_files",
            "invalid_confidence",
            "invalid_contradictions",
        ),
    ),
    (
        "Active Layer 2 wikilinks resolve to existing pages",
        ("broken_links_active",),
    ),
    (
        "Active Layer 2 wikilinks target only active graph nodes",
        (
            "non_active_wikilinks",
            "invalid_living_provenance_format",
            "invalid_raw_provenance_format",
            "missing_provenance_files",
        ),
    ),
    (
        "index.md registers every active node exactly once in the right section",
        (
            "unindexed_active",
            "invalid_index_entries",
            "duplicate_index_entries",
            "wrong_index_section",
        ),
    ),
    (
        "index.md contains no stale or non-active node entries",
        ("stale_index_entries", "index_case_mismatch"),
    ),
    (
        "index.md Total pages matches the registered active node count",
        ("index_count_mismatch",),
    ),
    (
        "_living sources contain no graph wikilinks or semantic frontmatter",
        ("living_wikilinks", "living_semantic_frontmatter"),
    ),
    (
        "_living top-level topic directories use 2-3 word kebab-case names",
        ("invalid_living_topic_dirs",),
    ),
    (
        "log.md uses one daily top-level maintenance entry per date",
        ("invalid_log_headings", "duplicate_log_dates"),
    ),
    (
        "Meta pages have no inbound or outbound local document graph edges",
        (
            "meta_graph_wikilinks",
            "meta_graph_markdown_links",
            "meta_graph_inbound_wikilinks",
            "meta_graph_inbound_markdown_links",
        ),
    ),
    (
        "Obsidian enabled plugin list matches local plugin manifests",
        (
            "obsidian_missing_community_plugins",
            "obsidian_invalid_community_plugins",
            "obsidian_enabled_missing_plugin_dirs",
            "obsidian_missing_plugin_manifests",
            "obsidian_invalid_plugin_manifests",
            "obsidian_manifest_id_mismatch",
            "obsidian_unenabled_plugin_dirs",
        ),
    ),
    (
        "SCHEMA taxonomy and validation checklist stay aligned with wiki_lint",
        (
            "schema_tags_missing_from_lint",
            "schema_tags_extra_in_lint",
            "schema_validation_check_count_mismatch",
        ),
    ),
    (
        "Graph references and local source paths use exact filesystem case",
        (
            "link_case_mismatch",
            "index_case_mismatch",
            "source_case_mismatch",
            "contradiction_case_mismatch",
            "provenance_case_mismatch",
        ),
    ),
)

LINK_RE = re.compile(r"\[\[([^\]|#]+)(?:#[^\]|]+)?(?:\|[^\]]+)?\]\]")
MARKDOWN_INLINE_LINK_RE = re.compile(
    r"!?\[[^\]\n]*\]\(\s*(?:<([^>\n]+)>|([^\s)\n]+))"
    r"(?:\s+(?:\"[^\"]*\"|'[^']*'|\([^\)\n]*\)))?\s*\)"
)
MARKDOWN_REFERENCE_DEFINITION_RE = re.compile(
    r"^\s{0,3}\[[^\]\n]+\]:\s*(?:<([^>\n]+)>|([^\s]+))",
    re.M,
)
LIVING_PROVENANCE_RE = re.compile(r"\^\[\[\[(_living/[^\]|#\]\n]+)(?:#[^\]\n]+)?(?:\|[^\]\n]+)?\]\]\]")
LOOSE_LIVING_PROVENANCE_RE = re.compile(
    r"\^\s*\[\s*\[\[\s*(_living/[^\]|#\]\s]+)(?:#[^\]\n]+)?(?:\|[^\]\n]+)?\]\]\s*\]"
)
RAW_PROVENANCE_RE = re.compile(r"\^\[(raw/[^\]\s]+)\]")
LOOSE_RAW_PROVENANCE_RE = re.compile(r"\^\s*\[\s*(raw/[^\]\s]+)\s*\]")
TOTAL_PAGES_RE = re.compile(r"Total pages:\s*(\d+)")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
LOG_DAILY_HEADING_RE = re.compile(r"^## \[(\d{4}-\d{2}-\d{2})\] daily \| .+$")
LOG_HEADING_DATE_RE = re.compile(r"^## \[(\d{4}-\d{2}-\d{2})\] ")
SCHEMA_TAG_TAXONOMY_RE = re.compile(r"## Tag Taxonomy .*?(?=\n## |\Z)", re.S)
SCHEMA_VALIDATION_RE = re.compile(r"## Validation Invariants .*?(?=\n### |\n## |\Z)", re.S)

ISSUE_GUIDANCE = {
    "zero_byte_active": {
        "rule": "Active Layer 2 must not contain empty Markdown nodes.",
        "fix": "Fill the node with valid frontmatter/body or delete the ghost file and update index/log if needed.",
    },
    "invalid_active_filenames": {
        "rule": "Active Layer 2 filenames must be lowercase kebab-case.",
        "fix": "Rename the file and update wikilinks, contradictions, index.md, and log.md.",
    },
    "root_floating_nodes": {
        "rule": "The wiki root may only contain Meta pages.",
        "fix": "Move the file into an allowed layer or delete it if it is a ghost node.",
    },
    "duplicate_slugs": {
        "rule": "Active Layer 2 slugs must be globally unique across the wiki.",
        "fix": "Rename one node and update every reference to the old slug.",
    },
    "missing_meta_pages": {
        "rule": "SCHEMA.md, index.md, and log.md are required Meta pages.",
        "fix": "Restore the missing Meta page with valid frontmatter.",
    },
    "missing_meta_frontmatter": {
        "rule": "Meta pages must start with YAML frontmatter.",
        "fix": "Add the standard summary frontmatter block to the Meta page.",
    },
    "missing_frontmatter": {
        "rule": "Active Layer 2 pages must start with YAML frontmatter.",
        "fix": "Add frontmatter with title, created, updated, type, tags, sources, and confidence.",
    },
    "missing_fields": {
        "rule": "Active Layer 2 frontmatter must include all required fields.",
        "fix": "Add the missing fields listed in the issue value.",
    },
    "type_dir_mismatch": {
        "rule": "frontmatter type must match the containing active directory.",
        "fix": "Change type or move the file so entities/concepts/comparisons/queries align with entity/concept/comparison/query.",
    },
    "invalid_dates": {
        "rule": "created and updated must be real YYYY-MM-DD calendar dates.",
        "fix": "Replace the invalid value with an ISO date such as 2026-07-14.",
    },
    "empty_tags": {
        "rule": "Active Layer 2 tags must be a non-empty list.",
        "fix": "Add at least one registered taxonomy tag.",
    },
    "invalid_tags": {
        "rule": "Active Layer 2 tags must be registered in SCHEMA.md Tag Taxonomy.",
        "fix": "Use an existing tag or update SCHEMA.md and ALLOWED_TAGS together.",
    },
    "empty_sources": {
        "rule": "Active Layer 2 sources must be a non-empty list.",
        "fix": "Add at least one _living/... or raw/... source path.",
    },
    "invalid_source_entries": {
        "rule": "Active Layer 2 sources entries must be non-empty strings.",
        "fix": "Replace malformed entries with local source paths.",
    },
    "invalid_source_scope": {
        "rule": "Active Layer 2 sources must point to Layer 1 local sources only.",
        "fix": "Use _living/... for private living docs or raw/... for public versioned references; do not put URLs directly here.",
    },
    "missing_source_files": {
        "rule": "Local source paths in Active Layer 2 frontmatter must exist.",
        "fix": "Correct the path, create/import the source, or remove stale provenance.",
    },
    "source_case_mismatch": {
        "rule": "Local source paths must match filesystem case exactly.",
        "fix": "Replace the path with the exact path shown in the issue value.",
    },
    "invalid_confidence": {
        "rule": "confidence must be high, medium, or low.",
        "fix": "Normalize the confidence value.",
    },
    "invalid_contradictions": {
        "rule": "contradictions entries must resolve to active Layer 2 slugs.",
        "fix": "Replace stale slugs, remove invalid contradictions, or create the missing active node intentionally.",
    },
    "contradiction_case_mismatch": {
        "rule": "contradictions slugs must match active slug case exactly.",
        "fix": "Use the exact slug shown in the issue value.",
    },
    "broken_links_active": {
        "rule": "Active Layer 2 wikilinks must resolve to existing pages.",
        "fix": "Fix the target slug/path, create the target node, or remove the wikilink.",
    },
    "link_case_mismatch": {
        "rule": "Wikilink targets must match existing page case exactly.",
        "fix": "Use the exact target shown in the issue value.",
    },
    "non_active_wikilinks": {
        "rule": "Active semantic wikilinks may only target active graph nodes.",
        "fix": "Use a provenance footnote for _living/raw sources, plain text for Meta pages, or remove archive links.",
    },
    "invalid_living_provenance_format": {
        "rule": "Living provenance must use compact syntax with no spaces: ^[[[_living/path|alias]]].",
        "fix": "Remove spaces between ^[, [[, ]], and ], and keep the target under _living/.",
    },
    "invalid_raw_provenance_format": {
        "rule": "Raw provenance must use compact syntax: ^[raw/path.md].",
        "fix": "Remove spaces inside the raw provenance marker and keep the target under raw/.",
    },
    "missing_provenance_files": {
        "rule": "Provenance markers must point to existing Layer 1 source files.",
        "fix": "Correct the provenance path, import the source, or remove stale provenance.",
    },
    "provenance_case_mismatch": {
        "rule": "Provenance marker paths must match filesystem case exactly.",
        "fix": "Replace the marker target with the exact path shown in the issue value.",
    },
    "unindexed_active": {
        "rule": "Every active node must be registered exactly once in index.md.",
        "fix": "Add one index entry in the section matching the node directory.",
    },
    "invalid_index_entries": {
        "rule": "index.md active entries must start with a code path such as `concepts/slug.md`.",
        "fix": "Rewrite the malformed bullet using the required code-path format.",
    },
    "stale_index_entries": {
        "rule": "index.md must not register missing, archived, or non-active nodes.",
        "fix": "Remove stale entries or update them to the current active slug.",
    },
    "index_case_mismatch": {
        "rule": "index.md entries must match active slug case exactly.",
        "fix": "Use the exact slug shown in the issue value.",
    },
    "duplicate_index_entries": {
        "rule": "Each active node must appear exactly once in index.md.",
        "fix": "Remove duplicate index entries.",
    },
    "wrong_index_section": {
        "rule": "index.md entries must be in the section matching their directory.",
        "fix": "Move the entry or correct its code path directory.",
    },
    "index_count_mismatch": {
        "rule": "index.md Total pages must equal the registered active node count.",
        "fix": "Update Total pages after fixing index entries.",
    },
    "living_wikilinks": {
        "rule": "_living sources must not contain graph wikilinks.",
        "fix": "Replace wikilinks with plain text or code paths inside _living.",
    },
    "living_semantic_frontmatter": {
        "rule": "_living sources must not contain semantic graph frontmatter.",
        "fix": "Remove type, tags, concepts, links, aliases, or category from _living frontmatter.",
    },
    "invalid_living_topic_dirs": {
        "rule": "_living top-level topic directories must be 2-3 word kebab-case names.",
        "fix": "Rename the top-level topic directory and update source/provenance paths.",
    },
    "invalid_log_headings": {
        "rule": "log.md top-level entries must use ## [YYYY-MM-DD] daily | subject.",
        "fix": "Normalize the heading or merge it into the daily entry for that date.",
    },
    "duplicate_log_dates": {
        "rule": "log.md should keep one top-level daily entry per date.",
        "fix": "Merge duplicate date headings into one daily entry with subsections.",
    },
    "meta_graph_wikilinks": {
        "rule": "Meta pages must have no outbound wikilinks.",
        "fix": "Replace Meta-page wikilinks with plain text or code paths.",
    },
    "meta_graph_markdown_links": {
        "rule": "Meta pages must have no outbound local Markdown document links.",
        "fix": "Replace local Markdown links with plain text or code paths.",
    },
    "meta_graph_inbound_wikilinks": {
        "rule": "No wiki page may wikilink to Meta pages.",
        "fix": "Replace inbound Meta wikilinks with plain text or code paths.",
    },
    "meta_graph_inbound_markdown_links": {
        "rule": "No wiki page may link to Meta pages with local Markdown links.",
        "fix": "Replace inbound Meta Markdown links with plain text or code paths.",
    },
    "obsidian_missing_community_plugins": {
        "rule": "Obsidian community-plugins.json must exist when .obsidian exists.",
        "fix": "Restore the enabled plugin list or remove stale plugin directories intentionally.",
    },
    "obsidian_invalid_community_plugins": {
        "rule": "community-plugins.json must be a JSON array of plugin id strings.",
        "fix": "Fix the JSON syntax and value shape.",
    },
    "obsidian_enabled_missing_plugin_dirs": {
        "rule": "Every enabled Obsidian plugin must have a local plugin directory.",
        "fix": "Install the plugin directory or remove the stale id from community-plugins.json.",
    },
    "obsidian_missing_plugin_manifests": {
        "rule": "Every local Obsidian plugin directory must include manifest.json.",
        "fix": "Restore manifest.json or remove the incomplete plugin directory.",
    },
    "obsidian_invalid_plugin_manifests": {
        "rule": "Obsidian plugin manifest.json files must be valid JSON.",
        "fix": "Fix the manifest JSON syntax.",
    },
    "obsidian_manifest_id_mismatch": {
        "rule": "Plugin manifest id must match its directory name.",
        "fix": "Rename the directory or correct manifest id.",
    },
    "obsidian_unenabled_plugin_dirs": {
        "rule": "Local Obsidian plugin directories must be enabled or removed.",
        "fix": "Add the plugin id to community-plugins.json or remove the unused directory.",
    },
    "schema_tags_missing_from_lint": {
        "rule": "SCHEMA.md Tag Taxonomy and ALLOWED_TAGS must stay aligned.",
        "fix": "Add missing taxonomy tags to ALLOWED_TAGS.",
    },
    "schema_tags_extra_in_lint": {
        "rule": "ALLOWED_TAGS must not contain tags absent from SCHEMA.md.",
        "fix": "Remove stale fallback tags or register them in SCHEMA.md.",
    },
    "schema_validation_check_count_mismatch": {
        "rule": "SCHEMA.md Validation Invariants count must match CHECKS count.",
        "fix": "Update CHECKS or SCHEMA.md so the check count stays aligned.",
    },
}


def strip_code(text: str) -> str:
    """Remove fenced and inline code before graph-link extraction."""
    text = re.sub(r"```.*?```", "", text, flags=re.S)
    return re.sub(r"`[^`]*`", "", text)


def strip_non_graph_markup(text: str) -> str:
    """Remove markup that contains brackets but is not a graph edge."""
    return LOOSE_LIVING_PROVENANCE_RE.sub("", strip_code(text))


def strip_inline_code(line: str) -> str:
    return re.sub(r"`[^`]*`", "", line)


def non_code_lines(text: str) -> list[tuple[int, str]]:
    """Return line-numbered text outside fenced and inline code spans."""
    lines: list[tuple[int, str]] = []
    in_fence = False
    for line_number, line in enumerate(text.splitlines(), start=1):
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        lines.append((line_number, strip_inline_code(line)))
    return lines


def is_valid_iso_date(value: Any) -> bool:
    if not isinstance(value, str) or not DATE_RE.match(value):
        return False
    try:
        date.fromisoformat(value)
    except ValueError:
        return False
    return True


def parse_frontmatter(text: str) -> dict[str, Any] | None:
    if not text.startswith("---\n"):
        return None
    end = text.find("\n---\n", 4)
    if end == -1:
        return None

    frontmatter: dict[str, Any] = {}
    lines = text[4:end].splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        if not line.strip() or line.startswith("  - ") or ":" not in line:
            i += 1
            continue

        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip()

        if not value:
            values: list[str] = []
            i += 1
            while i < len(lines) and lines[i].startswith("  - "):
                values.append(lines[i][4:].strip())
                i += 1
            frontmatter[key] = values
            continue

        if value.startswith("[") and value.endswith("]"):
            frontmatter[key] = [item.strip() for item in value[1:-1].split(",") if item.strip()]
        else:
            frontmatter[key] = value
        i += 1

    return frontmatter


def frontmatter_key_order(text: str) -> list[str]:
    if not text.startswith("---\n"):
        return []
    end = text.find("\n---\n", 4)
    if end == -1:
        return []

    keys: list[str] = []
    for line in text[4:end].splitlines():
        if not line.strip() or line.startswith("  - ") or ":" not in line:
            continue
        keys.append(line.split(":", 1)[0].strip())
    return keys


def relative(path: Path, root: Path) -> str:
    return str(path.relative_to(root))


def wiki_markdown_pages(root: Path) -> list[Path]:
    pages: list[Path] = []
    for path in sorted(root.rglob("*.md")):
        rel = path.relative_to(root)
        if any(part.startswith(".") for part in rel.parts):
            continue
        pages.append(path)
    return pages


def active_pages(root: Path) -> list[Path]:
    pages: list[Path] = []
    for path in wiki_markdown_pages(root):
        rel = path.relative_to(root)
        if rel.parts and rel.parts[0] in ACTIVE_DIRS:
            pages.append(path)
    return pages


def build_slug_index(root: Path) -> dict[str, list[str]]:
    slugs: dict[str, list[str]] = {}
    for path in wiki_markdown_pages(root):
        slugs.setdefault(path.stem, []).append(relative(path, root))
    return slugs


def build_casefold_slug_index(root: Path) -> dict[str, list[str]]:
    slugs: dict[str, list[str]] = {}
    for slug, paths in build_slug_index(root).items():
        slugs.setdefault(slug.casefold(), []).extend(paths)
    return slugs


def extract_links(text: str) -> list[str]:
    return LINK_RE.findall(strip_non_graph_markup(text))


def extract_markdown_link_destinations(text: str) -> list[str]:
    """Extract inline and reference-definition Markdown destinations."""
    text = strip_non_graph_markup(text)
    destinations: list[str] = []
    for pattern in (MARKDOWN_INLINE_LINK_RE, MARKDOWN_REFERENCE_DEFINITION_RE):
        for match in pattern.finditer(text):
            destination = next((group for group in match.groups() if group is not None), "").strip()
            if destination:
                destinations.append(destination)
    return destinations


def resolve_local_markdown_document_link(source: Path, destination: str, root: Path) -> str | None:
    """Resolve a local Markdown document destination relative to the wiki root."""
    parsed = urlsplit(destination)
    if parsed.scheme or parsed.netloc or not parsed.path:
        return None

    path_text = unquote(parsed.path)
    candidate = root / path_text.lstrip("/") if path_text.startswith("/") else source.parent / path_text
    if candidate.suffix.casefold() != ".md":
        extension_candidate = candidate.with_suffix(".md")
        if candidate.suffix or not extension_candidate.exists():
            return None
        candidate = extension_candidate

    try:
        return candidate.resolve(strict=False).relative_to(root.resolve()).as_posix()
    except ValueError:
        return None


def exact_existing_path(path: Path) -> Path | None:
    current = path.anchor and Path(path.anchor) or Path(".")
    parts = path.parts[1:] if path.anchor else path.parts
    for part in parts:
        if part in {"", "."}:
            continue
        if part == "..":
            current = current / part
            continue
        if not current.is_dir():
            return None
        entries = {entry.name: entry for entry in current.iterdir()}
        if part not in entries:
            return None
        current = entries[part]
    return current


def resolve_casefold_path(path: Path) -> Path | None:
    current = path.anchor and Path(path.anchor) or Path(".")
    parts = path.parts[1:] if path.anchor else path.parts
    for part in parts:
        if part in {"", "."}:
            continue
        if part == "..":
            current = current / part
            continue
        if not current.is_dir():
            return None
        matches = [entry for entry in current.iterdir() if entry.name.casefold() == part.casefold()]
        if len(matches) != 1:
            return None
        current = matches[0]
    return current


def resolve_existing_reference(
    root: Path,
    reference: str,
    *,
    allow_markdown_extension_fallback: bool = False,
) -> tuple[str | None, str | None]:
    """Resolve a local wiki reference with exact case, then casefold fallback.

    Returns (exact_relative_path, casefold_relative_path). Exactly one value is
    non-None when the reference exists; both are None when it is missing.
    """
    reference_path = Path(reference)
    if reference_path.is_absolute() or ".." in reference_path.parts:
        return None, None

    candidates = [reference]
    if allow_markdown_extension_fallback and not reference.endswith(".md"):
        candidates.append(f"{reference}.md")

    for candidate in candidates:
        exact_path = exact_existing_path(root / candidate)
        if exact_path and exact_path.is_file():
            return relative(exact_path, root), None

    for candidate in candidates:
        casefold_path = resolve_casefold_path(root / candidate)
        if casefold_path and casefold_path.is_file():
            return None, relative(casefold_path, root)

    return None, None


def resolve_wikilink_target(
    target: str,
    root: Path,
    slug_index: dict[str, list[str]],
    casefold_slug_index: dict[str, list[str]],
) -> dict[str, Any]:
    """Resolve an Obsidian wikilink target.

    Path-qualified wikilinks must resolve by exact path. Pathless wikilinks
    resolve by slug, matching Obsidian's title-based addressing.
    """
    normalized = target.replace("\\", "/")
    if "/" in normalized:
        reference = normalized if normalized.endswith(".md") else f"{normalized}.md"
        exact_path, casefold_path = resolve_existing_reference(root, reference)
        if exact_path:
            return {"status": "ok", "slug": Path(exact_path).stem, "paths": [exact_path]}
        if casefold_path:
            return {"status": "case_mismatch", "slug": Path(casefold_path).stem, "paths": [casefold_path]}
        return {"status": "missing", "slug": Path(normalized).stem, "paths": []}

    slug = Path(target).name
    if slug in slug_index:
        return {"status": "ok", "slug": slug, "paths": slug_index[slug]}

    case_matches = casefold_slug_index.get(slug.casefold(), [])
    if case_matches:
        return {"status": "case_mismatch", "slug": slug, "paths": case_matches}

    return {"status": "missing", "slug": slug, "paths": []}


def parse_schema_tags(root: Path) -> set[str]:
    schema_path = root / "SCHEMA.md"
    if not schema_path.exists():
        return set(ALLOWED_TAGS)

    text = schema_path.read_text()
    tags = extract_schema_tags(text)
    return tags or set(ALLOWED_TAGS)


def extract_schema_tags(schema_text: str) -> set[str]:
    match = SCHEMA_TAG_TAXONOMY_RE.search(schema_text)
    if not match:
        return set()
    return set(re.findall(r"`([^`]+)`", match.group(0)))


def count_schema_validation_items(schema_text: str) -> int:
    match = SCHEMA_VALIDATION_RE.search(schema_text)
    if not match:
        return 0
    return len(re.findall(r"^\d+\.\s+", match.group(0), flags=re.M))


def parse_index_entries(index_text: str) -> tuple[list[tuple[str, str | None, str]], list[dict[str, Any]]]:
    entries: list[tuple[str, str | None, str]] = []
    invalid_entries: list[dict[str, Any]] = []
    current_dir: str | None = None

    for line_number, line in enumerate(index_text.splitlines(), start=1):
        if line.startswith("## "):
            heading = line[3:].split("(", 1)[0].strip()
            current_dir = INDEX_SECTIONS.get(heading)
            continue
        match = INDEX_ENTRY_RE.match(line)
        if match:
            path_dir, slug = match.groups()
            entries.append((slug, current_dir, path_dir))
        elif current_dir and line.startswith("- "):
            invalid_entries.append(
                {
                    "line": line_number,
                    "section": current_dir,
                    "text": line,
                    "expected": "- `entities|concepts|comparisons|queries/slug.md` - summary",
                }
            )

    return entries, invalid_entries


def load_json(path: Path) -> Any:
    with path.open() as f:
        return json.load(f)


def validate_log_policy(root: Path, issues: dict[str, list[Any]]) -> None:
    log_path = root / "log.md"
    if not log_path.exists():
        return

    dates: list[str] = []
    for line_number, line in enumerate(log_path.read_text().splitlines(), start=1):
        if not line.startswith("## "):
            continue
        daily_match = LOG_DAILY_HEADING_RE.match(line)
        if not daily_match:
            issues["invalid_log_headings"].append([line_number, line])
            date_match = LOG_HEADING_DATE_RE.match(line)
            if date_match:
                dates.append(date_match.group(1))
            continue
        dates.append(daily_match.group(1))

    for date, count in sorted(Counter(dates).items()):
        if count > 1:
            issues["duplicate_log_dates"].append([date, count])


def validate_meta_graph_isolation(root: Path, issues: dict[str, list[Any]]) -> None:
    for name in sorted(META_FILES):
        path = root / name
        if not path.exists():
            continue
        text = path.read_text()
        wikilinks = extract_links(text)
        if wikilinks:
            issues["meta_graph_wikilinks"].append([name, wikilinks])
        markdown_links = [
            [destination, target]
            for destination in extract_markdown_link_destinations(text)
            if (target := resolve_local_markdown_document_link(path, destination, root)) is not None
        ]
        if markdown_links:
            issues["meta_graph_markdown_links"].append([name, markdown_links])

    for path in wiki_markdown_pages(root):
        if path.parent == root and path.name in META_FILES:
            continue
        text = path.read_text()
        for target in extract_links(text):
            if Path(target).stem.casefold() in META_SLUGS_CASEFOLD:
                issues["meta_graph_inbound_wikilinks"].append([relative(path, root), target])
        for destination in extract_markdown_link_destinations(text):
            target = resolve_local_markdown_document_link(path, destination, root)
            if target is not None and Path(target).name.casefold() in META_FILES_CASEFOLD:
                issues["meta_graph_inbound_markdown_links"].append([relative(path, root), destination, target])


def validate_obsidian_plugins(root: Path, issues: dict[str, list[Any]]) -> None:
    obsidian_root = root / ".obsidian"
    if not obsidian_root.exists():
        return

    community_plugins_path = obsidian_root / "community-plugins.json"
    plugins_root = obsidian_root / "plugins"
    if not community_plugins_path.exists():
        issues["obsidian_missing_community_plugins"].append(relative(community_plugins_path, root))
        return

    try:
        enabled_plugins = load_json(community_plugins_path)
    except json.JSONDecodeError as exc:
        issues["obsidian_invalid_community_plugins"].append(
            [relative(community_plugins_path, root), f"line {exc.lineno}: {exc.msg}"]
        )
        return

    if not isinstance(enabled_plugins, list) or not all(isinstance(plugin, str) for plugin in enabled_plugins):
        issues["obsidian_invalid_community_plugins"].append(
            [relative(community_plugins_path, root), "expected a JSON array of plugin id strings"]
        )
        return

    enabled_set = set(enabled_plugins)
    for plugin_id in sorted(enabled_set):
        plugin_dir = plugins_root / plugin_id
        manifest_path = plugin_dir / "manifest.json"
        if not plugin_dir.is_dir():
            issues["obsidian_enabled_missing_plugin_dirs"].append(plugin_id)
            continue
        if not manifest_path.exists():
            issues["obsidian_missing_plugin_manifests"].append(relative(manifest_path, root))

    if not plugins_root.exists():
        return

    for plugin_dir in sorted(path for path in plugins_root.iterdir() if path.is_dir()):
        manifest_path = plugin_dir / "manifest.json"
        if not manifest_path.exists():
            if plugin_dir.name not in enabled_set:
                issues["obsidian_unenabled_plugin_dirs"].append(relative(plugin_dir, root))
            continue

        try:
            manifest = load_json(manifest_path)
        except json.JSONDecodeError as exc:
            issues["obsidian_invalid_plugin_manifests"].append(
                [relative(manifest_path, root), f"line {exc.lineno}: {exc.msg}"]
            )
            continue

        manifest_id = manifest.get("id") if isinstance(manifest, dict) else None
        if manifest_id != plugin_dir.name:
            issues["obsidian_manifest_id_mismatch"].append(
                [relative(manifest_path, root), manifest_id, plugin_dir.name]
            )
        if plugin_dir.name not in enabled_set:
            issues["obsidian_unenabled_plugin_dirs"].append(relative(plugin_dir, root))


def validate_schema_lint_alignment(root: Path, issues: dict[str, list[Any]]) -> None:
    schema_path = root / "SCHEMA.md"
    if not schema_path.exists():
        return

    schema_text = schema_path.read_text()
    schema_tags = extract_schema_tags(schema_text)
    if schema_tags:
        missing_from_lint = sorted(schema_tags - ALLOWED_TAGS)
        extra_in_lint = sorted(ALLOWED_TAGS - schema_tags)
        if missing_from_lint:
            issues["schema_tags_missing_from_lint"].append(missing_from_lint)
        if extra_in_lint:
            issues["schema_tags_extra_in_lint"].append(extra_in_lint)

    validation_count = count_schema_validation_items(schema_text)
    if validation_count and validation_count != len(CHECKS):
        issues["schema_validation_check_count_mismatch"].append({"schema": validation_count, "wiki_lint": len(CHECKS)})


def validate_provenance_markers(root: Path, path: Path, text: str, issues: dict[str, list[Any]]) -> None:
    rel = relative(path, root)

    for line_number, line in non_code_lines(text):
        for match in LOOSE_LIVING_PROVENANCE_RE.finditer(line):
            marker = match.group(0)
            source = match.group(1)
            if not LIVING_PROVENANCE_RE.fullmatch(marker):
                issues["invalid_living_provenance_format"].append(
                    {
                        "path": rel,
                        "line": line_number,
                        "marker": marker,
                        "expected": "^[[[_living/path/to/source|alias]]]",
                    }
                )
                continue

            exact_path, casefold_path = resolve_existing_reference(
                root,
                source,
                allow_markdown_extension_fallback=True,
            )
            if exact_path:
                continue
            if casefold_path:
                issues["provenance_case_mismatch"].append(
                    {"path": rel, "line": line_number, "target": source, "actual": casefold_path}
                )
            else:
                issues["missing_provenance_files"].append({"path": rel, "line": line_number, "target": source})

        for match in LOOSE_RAW_PROVENANCE_RE.finditer(line):
            marker = match.group(0)
            source = match.group(1)
            if not RAW_PROVENANCE_RE.fullmatch(marker):
                issues["invalid_raw_provenance_format"].append(
                    {
                        "path": rel,
                        "line": line_number,
                        "marker": marker,
                        "expected": "^[raw/path/to/source.md]",
                    }
                )
                continue

            exact_path, casefold_path = resolve_existing_reference(root, source)
            if exact_path:
                continue
            if casefold_path:
                issues["provenance_case_mismatch"].append(
                    {"path": rel, "line": line_number, "target": source, "actual": casefold_path}
                )
            else:
                issues["missing_provenance_files"].append({"path": rel, "line": line_number, "target": source})


def validate(root: Path) -> dict[str, list[Any]]:
    issues: dict[str, list[Any]] = {
        "zero_byte_active": [],
        "invalid_active_filenames": [],
        "root_floating_nodes": [],
        "duplicate_slugs": [],
        "missing_meta_pages": [],
        "missing_meta_frontmatter": [],
        "missing_frontmatter": [],
        "missing_fields": [],
        "type_dir_mismatch": [],
        "invalid_dates": [],
        "empty_tags": [],
        "invalid_tags": [],
        "empty_sources": [],
        "invalid_source_entries": [],
        "invalid_source_scope": [],
        "invalid_confidence": [],
        "invalid_contradictions": [],
        "contradiction_case_mismatch": [],
        "missing_source_files": [],
        "source_case_mismatch": [],
        "broken_links_active": [],
        "link_case_mismatch": [],
        "non_active_wikilinks": [],
        "invalid_living_provenance_format": [],
        "invalid_raw_provenance_format": [],
        "missing_provenance_files": [],
        "provenance_case_mismatch": [],
        "unindexed_active": [],
        "invalid_index_entries": [],
        "stale_index_entries": [],
        "index_case_mismatch": [],
        "duplicate_index_entries": [],
        "wrong_index_section": [],
        "index_count_mismatch": [],
        "living_wikilinks": [],
        "living_semantic_frontmatter": [],
        "invalid_living_topic_dirs": [],
        "invalid_log_headings": [],
        "duplicate_log_dates": [],
        "meta_graph_wikilinks": [],
        "meta_graph_markdown_links": [],
        "meta_graph_inbound_wikilinks": [],
        "meta_graph_inbound_markdown_links": [],
        "obsidian_missing_community_plugins": [],
        "obsidian_invalid_community_plugins": [],
        "obsidian_enabled_missing_plugin_dirs": [],
        "obsidian_missing_plugin_manifests": [],
        "obsidian_invalid_plugin_manifests": [],
        "obsidian_manifest_id_mismatch": [],
        "obsidian_unenabled_plugin_dirs": [],
        "schema_tags_missing_from_lint": [],
        "schema_tags_extra_in_lint": [],
        "schema_validation_check_count_mismatch": [],
    }

    pages = active_pages(root)
    active_slugs = {path.stem for path in pages}
    slug_index = build_slug_index(root)
    casefold_slug_index = build_casefold_slug_index(root)
    allowed_tags = parse_schema_tags(root)

    for path in pages:
        if path.stat().st_size == 0:
            issues["zero_byte_active"].append(relative(path, root))
        if not ACTIVE_FILENAME_RE.match(path.name):
            issues["invalid_active_filenames"].append(relative(path, root))

    for path in sorted(root.glob("*.md")):
        if path.name not in META_FILES:
            issues["root_floating_nodes"].append(path.name)

    for slug, paths in sorted(slug_index.items()):
        active_paths = [path for path in paths if path.split("/")[0] in ACTIVE_DIRS]
        if active_paths and len(paths) > 1:
            issues["duplicate_slugs"].append({slug: paths})

    for name in sorted(META_FILES):
        path = root / name
        if not path.exists():
            issues["missing_meta_pages"].append(name)
            continue
        if parse_frontmatter(path.read_text()) is None:
            issues["missing_meta_frontmatter"].append(name)

    for path in pages:
        rel = relative(path, root)
        text = path.read_text()
        frontmatter = parse_frontmatter(text)
        if frontmatter is None:
            issues["missing_frontmatter"].append(rel)
            continue

        missing = sorted(REQUIRED_FRONTMATTER - set(frontmatter))
        if missing:
            issues["missing_fields"].append([rel, missing])

        expected_type = ACTIVE_DIRS[path.relative_to(root).parts[0]]
        actual_type = frontmatter.get("type")
        if actual_type != expected_type:
            issues["type_dir_mismatch"].append([rel, actual_type, expected_type])

        for key in ("created", "updated"):
            value = frontmatter.get(key)
            if not is_valid_iso_date(value):
                issues["invalid_dates"].append([rel, key, value])

        tags = frontmatter.get("tags") if isinstance(frontmatter.get("tags"), list) else []
        if not tags:
            issues["empty_tags"].append(rel)
        invalid_tags = [tag for tag in tags if tag not in allowed_tags]
        if invalid_tags:
            issues["invalid_tags"].append([rel, invalid_tags])

        sources = frontmatter.get("sources") if isinstance(frontmatter.get("sources"), list) else []
        if not sources:
            issues["empty_sources"].append(rel)
        else:
            missing_sources: list[str] = []
            for source in sources:
                if not isinstance(source, str) or not source:
                    issues["invalid_source_entries"].append([rel, source])
                    continue

                if not source.startswith(LAYER1_SOURCE_PREFIXES):
                    issues["invalid_source_scope"].append(
                        {"path": rel, "source": source, "expected_prefixes": list(LAYER1_SOURCE_PREFIXES)}
                    )
                    continue

                exact_source_path, casefold_source_path = resolve_existing_reference(root, source)
                if not exact_source_path:
                    if casefold_source_path:
                        issues["source_case_mismatch"].append([rel, source, casefold_source_path])
                    else:
                        missing_sources.append(source)
            if missing_sources:
                issues["missing_source_files"].append([rel, missing_sources])

        confidence = frontmatter.get("confidence")
        if confidence not in {"high", "medium", "low"}:
            issues["invalid_confidence"].append([rel, confidence])

        contradictions = frontmatter.get("contradictions", [])
        if isinstance(contradictions, str):
            contradictions = [contradictions]
        if contradictions:
            invalid_contradictions: list[str] = []
            for slug in contradictions:
                if slug in active_slugs:
                    continue
                case_matches = [
                    Path(path).stem
                    for path in casefold_slug_index.get(slug.casefold(), [])
                    if path.split("/")[0] in ACTIVE_DIRS
                ]
                if case_matches:
                    issues["contradiction_case_mismatch"].append([rel, slug, sorted(set(case_matches))])
                    continue
                invalid_contradictions.append(slug)
            if invalid_contradictions:
                issues["invalid_contradictions"].append([rel, invalid_contradictions])

        for target in extract_links(text):
            resolved = resolve_wikilink_target(target, root, slug_index, casefold_slug_index)
            slug = resolved["slug"]
            if resolved["status"] == "missing":
                issues["broken_links_active"].append([rel, target])
                continue
            if resolved["status"] == "case_mismatch":
                issues["link_case_mismatch"].append([rel, target, resolved["paths"]])
                continue
            if slug not in active_slugs:
                issues["non_active_wikilinks"].append([rel, target, resolved["paths"]])

        validate_provenance_markers(root, path, text, issues)

    index_path = root / "index.md"
    if index_path.exists():
        index_text = index_path.read_text()
        index_entries, invalid_index_entries = parse_index_entries(index_text)
        issues["invalid_index_entries"].extend(invalid_index_entries)
        index_links = [slug for slug, _section_dir, _path_dir in index_entries]

        counts = Counter(index_links)
        for slug, count in sorted(counts.items()):
            if count > 1:
                issues["duplicate_index_entries"].append([slug, count])

        for path in pages:
            if counts[path.stem] != 1:
                issues["unindexed_active"].append(relative(path, root))

        for slug in index_links:
            if slug not in active_slugs:
                case_matches = [
                    Path(path).stem
                    for path in casefold_slug_index.get(slug.casefold(), [])
                    if path.split("/")[0] in ACTIVE_DIRS
                ]
                if case_matches:
                    issues["index_case_mismatch"].append([slug, sorted(set(case_matches))])
                else:
                    issues["stale_index_entries"].append(slug)

        active_dirs_by_slug = {path.stem: path.relative_to(root).parts[0] for path in pages}
        for slug, section_dir, path_dir in index_entries:
            active_dir = active_dirs_by_slug.get(slug)
            if active_dir and section_dir != active_dir:
                issues["wrong_index_section"].append([slug, section_dir, active_dir])
            if active_dir and path_dir != active_dir:
                issues["wrong_index_section"].append([slug, path_dir, active_dir])

        match = TOTAL_PAGES_RE.search(index_text)
        if match and int(match.group(1)) != len(pages):
            issues["index_count_mismatch"].append({"declared": int(match.group(1)), "actual_active": len(pages)})
    else:
        issues["stale_index_entries"].append("index.md is missing")

    for path in sorted(root.glob("_living/**/*.md")):
        text = path.read_text()
        links = extract_links(text)
        if links:
            issues["living_wikilinks"].append([relative(path, root), links])
        semantic_fields = sorted(LIVING_SEMANTIC_FIELDS & set(frontmatter_key_order(text)))
        if semantic_fields:
            issues["living_semantic_frontmatter"].append([relative(path, root), semantic_fields])

    living_root = root / "_living"
    if living_root.exists():
        for path in sorted(living_root.iterdir()):
            if path.is_dir() and not LIVING_TOPIC_DIR_RE.match(path.name):
                issues["invalid_living_topic_dirs"].append(relative(path, root))

    validate_log_policy(root, issues)
    validate_meta_graph_isolation(root, issues)
    validate_obsidian_plugins(root, issues)
    validate_schema_lint_alignment(root, issues)

    return issues


def has_issues(issues: dict[str, list[Any]]) -> bool:
    return any(values for values in issues.values())


def issue_count(issues: dict[str, list[Any]], keys: tuple[str, ...]) -> int:
    return sum(len(issues.get(key, [])) for key in keys)


def format_issue_value(value: Any) -> str:
    if isinstance(value, (dict, list, tuple)):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def print_text_report(issues: dict[str, list[Any]]) -> None:
    print("wiki_lint: checks")
    for index, (label, keys) in enumerate(CHECKS, start=1):
        count = issue_count(issues, keys)
        status = "OK" if count == 0 else "FAIL"
        suffix = "" if count == 0 else f" ({count} issue{'s' if count != 1 else ''})"
        print(f"{index}. [{status}] {label}{suffix}")

    if has_issues(issues):
        print("\nwiki_lint: issue details")
        for name, values in issues.items():
            if not values:
                continue
            print(f"\n{name}:")
            guidance = ISSUE_GUIDANCE.get(name)
            if guidance:
                print(f"  rule: {guidance['rule']}")
                print(f"  fix: {guidance['fix']}")
            for value in values:
                print(f"  - {format_issue_value(value)}")
        print("\nwiki_lint: FAILED")
    else:
        print("wiki_lint: OK")


def parse_args() -> argparse.Namespace:
    repo_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--wiki-root",
        type=Path,
        default=repo_root / "wiki",
        help="Path to the wiki root. Defaults to ../wiki relative to this script.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print machine-readable JSON instead of a text report.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = args.wiki_root.resolve()
    if not root.exists():
        print(f"wiki_lint: wiki root does not exist: {root}", file=sys.stderr)
        return 2
    if not root.is_dir():
        print(f"wiki_lint: wiki root is not a directory: {root}", file=sys.stderr)
        return 2

    issues = validate(root)
    if args.json:
        print(json.dumps(issues, ensure_ascii=False, indent=2))
    else:
        print_text_report(issues)
    return 1 if has_issues(issues) else 0


if __name__ == "__main__":
    raise SystemExit(main())
