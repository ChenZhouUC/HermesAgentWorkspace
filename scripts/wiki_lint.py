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
from pathlib import Path
from typing import Any


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
META_SLUGS = {Path(name).stem for name in META_FILES}
META_SLUGS_CASEFOLD = {slug.casefold() for slug in META_SLUGS}
ACTIVE_FILENAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*\.md$")
LIVING_TOPIC_DIR_RE = re.compile(r"^[A-Za-z0-9]+(?:-[A-Za-z0-9]+){1,2}$")
LIVING_SEMANTIC_FIELDS = {"type", "tags", "concepts", "links", "aliases", "category"}

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
        ("non_active_wikilinks",),
    ),
    (
        "index.md registers every active node exactly once in the right section",
        (
            "unindexed_active",
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
        "Meta pages are isolated from the semantic wikilink graph",
        ("meta_graph_wikilinks", "meta_graph_inbound_wikilinks"),
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
        ),
    ),
)

LINK_RE = re.compile(r"\[\[([^\]|#]+)(?:#[^\]|]+)?(?:\|[^\]]+)?\]\]")
LIVING_PROVENANCE_RE = re.compile(r"\^\[\[\[_living/[^\]]+\]\]\]")
TOTAL_PAGES_RE = re.compile(r"Total pages:\s*(\d+)")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
LOG_DAILY_HEADING_RE = re.compile(r"^## \[(\d{4}-\d{2}-\d{2})\] daily \| .+$")
LOG_HEADING_DATE_RE = re.compile(r"^## \[(\d{4}-\d{2}-\d{2})\] ")
SCHEMA_TAG_TAXONOMY_RE = re.compile(r"## Tag Taxonomy .*?(?=\n## |\Z)", re.S)
SCHEMA_VALIDATION_RE = re.compile(r"## Validation Invariants .*?(?=\n### |\n## |\Z)", re.S)


def strip_code(text: str) -> str:
    """Remove fenced and inline code before wikilink extraction."""
    text = re.sub(r"```.*?```", "", text, flags=re.S)
    return re.sub(r"`[^`]*`", "", text)


def strip_non_graph_markup(text: str) -> str:
    """Remove markup that contains brackets but is not a graph edge."""
    return LIVING_PROVENANCE_RE.sub("", strip_code(text))


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


def parse_index_entries(index_text: str) -> list[tuple[str, str | None, str]]:
    entries: list[tuple[str, str | None, str]] = []
    current_dir: str | None = None

    for line in index_text.splitlines():
        if line.startswith("## "):
            heading = line[3:].split("(", 1)[0].strip()
            current_dir = INDEX_SECTIONS.get(heading)
            continue
        match = INDEX_ENTRY_RE.match(line)
        if match:
            path_dir, slug = match.groups()
            entries.append((slug, current_dir, path_dir))

    return entries


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
        links = extract_links(path.read_text())
        if links:
            issues["meta_graph_wikilinks"].append([name, links])

    for path in wiki_markdown_pages(root):
        if path.parent == root and path.name in META_FILES:
            continue
        for target in extract_links(path.read_text()):
            if Path(target).stem.casefold() in META_SLUGS_CASEFOLD:
                issues["meta_graph_inbound_wikilinks"].append([relative(path, root), target])


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
        "invalid_confidence": [],
        "invalid_contradictions": [],
        "contradiction_case_mismatch": [],
        "missing_source_files": [],
        "source_case_mismatch": [],
        "broken_links_active": [],
        "link_case_mismatch": [],
        "non_active_wikilinks": [],
        "unindexed_active": [],
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
        "meta_graph_inbound_wikilinks": [],
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
            if not isinstance(value, str) or not DATE_RE.match(value):
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
                if re.match(r"https?://", source):
                    continue
                source_path = root / source
                exact_source_path = exact_existing_path(source_path)
                if exact_source_path is None:
                    casefold_source_path = resolve_casefold_path(source_path)
                    if casefold_source_path and casefold_source_path.exists():
                        issues["source_case_mismatch"].append([rel, source, relative(casefold_source_path, root)])
                        continue
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
            slug = Path(target).name
            if slug not in slug_index:
                case_matches = casefold_slug_index.get(slug.casefold(), [])
                if case_matches:
                    issues["link_case_mismatch"].append([rel, target, case_matches])
                    continue
                issues["broken_links_active"].append([rel, target])
                continue
            if slug not in active_slugs:
                issues["non_active_wikilinks"].append([rel, target, slug_index[slug]])

    index_path = root / "index.md"
    if index_path.exists():
        index_text = index_path.read_text()
        index_entries = parse_index_entries(index_text)
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
            for value in values:
                print(f"  - {value}")
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
