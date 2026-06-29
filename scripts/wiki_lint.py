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

META_FILES = {"SCHEMA.md", "index.md", "log.md"}
META_SLUGS = {Path(name).stem for name in META_FILES}
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
    "macos",
    "ops",
    "gateway",
    "pipeline",
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
            "invalid_confidence",
            "invalid_contradictions",
        ),
    ),
    (
        "Active Layer 2 sources resolve to local files or URLs",
        ("missing_source_files",),
    ),
    (
        "Active Layer 2 wikilinks resolve to active graph nodes",
        ("broken_links_active", "non_active_wikilinks"),
    ),
    (
        "index.md registers every active node exactly once in the right section",
        (
            "unindexed_active",
            "stale_index_entries",
            "duplicate_index_entries",
            "wrong_index_section",
            "index_count_mismatch",
        ),
    ),
    (
        "_living sources contain no graph wikilinks",
        ("living_wikilinks",),
    ),
    (
        "_living frontmatter stays metadata-minimal",
        ("living_semantic_frontmatter",),
    ),
    (
        "_living top-level topic directories use 2-3 word kebab-case names",
        ("invalid_living_topic_dirs",),
    ),
)

LINK_RE = re.compile(r"\[\[([^\]|#]+)(?:#[^\]|]+)?(?:\|[^\]]+)?\]\]")
LIVING_PROVENANCE_RE = re.compile(r"\^\[\[\[_living/[^\]]+\]\]\]")
TOTAL_PAGES_RE = re.compile(r"Total pages:\s*(\d+)")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


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


def extract_links(text: str) -> list[str]:
    return LINK_RE.findall(strip_non_graph_markup(text))


def parse_schema_tags(root: Path) -> set[str]:
    schema_path = root / "SCHEMA.md"
    if not schema_path.exists():
        return set(ALLOWED_TAGS)

    text = schema_path.read_text()
    match = re.search(r"## Tag Taxonomy .*?(?=\n## |\Z)", text, flags=re.S)
    if not match:
        return set(ALLOWED_TAGS)
    tags = set(re.findall(r"`([^`]+)`", match.group(0)))
    return tags or set(ALLOWED_TAGS)


def parse_index_entries(index_text: str) -> list[tuple[str, str | None]]:
    entries: list[tuple[str, str | None]] = []
    current_dir: str | None = None

    for line in strip_non_graph_markup(index_text).splitlines():
        if line.startswith("## "):
            heading = line[3:].split("(", 1)[0].strip()
            current_dir = INDEX_SECTIONS.get(heading)
            continue
        if not line.startswith("- "):
            continue
        for target in LINK_RE.findall(line):
            slug = Path(target).name
            if slug in META_SLUGS:
                continue
            entries.append((slug, current_dir))

    return entries


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
        "missing_source_files": [],
        "broken_links_active": [],
        "non_active_wikilinks": [],
        "unindexed_active": [],
        "stale_index_entries": [],
        "duplicate_index_entries": [],
        "wrong_index_section": [],
        "index_count_mismatch": [],
        "living_wikilinks": [],
        "living_semantic_frontmatter": [],
        "invalid_living_topic_dirs": [],
    }

    pages = active_pages(root)
    active_slugs = {path.stem for path in pages}
    slug_index = build_slug_index(root)
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
                if not (root / source).exists():
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
            invalid_contradictions = [slug for slug in contradictions if slug not in active_slugs]
            if invalid_contradictions:
                issues["invalid_contradictions"].append([rel, invalid_contradictions])

        for target in extract_links(text):
            slug = Path(target).name
            if slug not in slug_index:
                issues["broken_links_active"].append([rel, target])
                continue
            if slug not in active_slugs:
                issues["non_active_wikilinks"].append([rel, target, slug_index[slug]])

    index_path = root / "index.md"
    if index_path.exists():
        index_text = index_path.read_text()
        index_entries = parse_index_entries(index_text)
        index_links = [slug for slug, _section_dir in index_entries]

        counts = Counter(index_links)
        for slug, count in sorted(counts.items()):
            if count > 1:
                issues["duplicate_index_entries"].append([slug, count])

        for path in pages:
            if counts[path.stem] != 1:
                issues["unindexed_active"].append(relative(path, root))

        for slug in index_links:
            if slug not in active_slugs:
                issues["stale_index_entries"].append(slug)

        active_dirs_by_slug = {path.stem: path.relative_to(root).parts[0] for path in pages}
        for slug, section_dir in index_entries:
            active_dir = active_dirs_by_slug.get(slug)
            if active_dir and section_dir != active_dir:
                issues["wrong_index_section"].append([slug, section_dir, active_dir])

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
