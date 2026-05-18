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

META_FILES = {"SCHEMA.md", "index.md", "log.md"}

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
    "quantization",
    "tensorrt",
    "onnx",
    "system-prompt",
    "alignment",
    "agent",
    "macos",
    "ops",
    "gateway",
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

LINK_RE = re.compile(r"\[\[([^\]|#]+)(?:#[^\]|]+)?(?:\|[^\]]+)?\]\]")
TOTAL_PAGES_RE = re.compile(r"Total pages:\s*(\d+)")


def strip_code(text: str) -> str:
    """Remove fenced and inline code before wikilink extraction."""
    text = re.sub(r"```.*?```", "", text, flags=re.S)
    return re.sub(r"`[^`]*`", "", text)


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


def relative(path: Path, root: Path) -> str:
    return str(path.relative_to(root))


def active_pages(root: Path) -> list[Path]:
    pages: list[Path] = []
    for path in sorted(root.rglob("*.md")):
        rel = path.relative_to(root)
        if rel.parts and rel.parts[0] in ACTIVE_DIRS:
            pages.append(path)
    return pages


def build_slug_index(root: Path) -> dict[str, list[str]]:
    slugs: dict[str, list[str]] = {}
    for path in sorted(root.rglob("*.md")):
        slugs.setdefault(path.stem, []).append(relative(path, root))
    return slugs


def extract_links(text: str) -> list[str]:
    return LINK_RE.findall(strip_code(text))


def validate(root: Path) -> dict[str, list[Any]]:
    issues: dict[str, list[Any]] = {
        "zero_byte_active": [],
        "root_floating_nodes": [],
        "duplicate_slugs": [],
        "missing_frontmatter": [],
        "missing_fields": [],
        "type_dir_mismatch": [],
        "empty_tags": [],
        "invalid_tags": [],
        "empty_sources": [],
        "missing_source_files": [],
        "broken_links_active": [],
        "low_outlinks": [],
        "unindexed_active": [],
        "stale_index_entries": [],
        "duplicate_index_entries": [],
        "index_count_mismatch": [],
        "living_wikilinks": [],
    }

    pages = active_pages(root)
    active_slugs = {path.stem for path in pages}
    slug_index = build_slug_index(root)

    for path in pages:
        if path.stat().st_size == 0:
            issues["zero_byte_active"].append(relative(path, root))

    for path in sorted(root.glob("*.md")):
        if path.name not in META_FILES:
            issues["root_floating_nodes"].append(path.name)

    for slug, paths in sorted(slug_index.items()):
        active_paths = [path for path in paths if path.split("/")[0] in ACTIVE_DIRS]
        if len(active_paths) > 1:
            issues["duplicate_slugs"].append({slug: active_paths})

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

        tags = frontmatter.get("tags") if isinstance(frontmatter.get("tags"), list) else []
        if not tags:
            issues["empty_tags"].append(rel)
        invalid_tags = [tag for tag in tags if tag not in ALLOWED_TAGS]
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

        outlinks: list[str] = []
        for target in extract_links(text):
            if target.startswith("_living/"):
                continue
            slug = Path(target).name
            if slug not in slug_index:
                issues["broken_links_active"].append([rel, target])
            else:
                outlinks.append(slug)
        if len(outlinks) < 2:
            issues["low_outlinks"].append([rel, len(outlinks), outlinks])

    index_path = root / "index.md"
    if index_path.exists():
        index_text = index_path.read_text()
        index_links: list[str] = []
        for target in extract_links(index_text):
            slug = Path(target).name
            if slug in {"SCHEMA", "log"}:
                continue
            index_links.append(slug)

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

        match = TOTAL_PAGES_RE.search(index_text)
        if match and int(match.group(1)) != len(pages):
            issues["index_count_mismatch"].append({"declared": int(match.group(1)), "actual_active": len(pages)})
    else:
        issues["stale_index_entries"].append("index.md is missing")

    for path in sorted(root.glob("_living/**/*.md")):
        links = extract_links(path.read_text())
        if links:
            issues["living_wikilinks"].append([relative(path, root), links])

    return issues


def has_issues(issues: dict[str, list[Any]]) -> bool:
    return any(values for values in issues.values())


def print_text_report(issues: dict[str, list[Any]]) -> None:
    if not has_issues(issues):
        print("wiki_lint: OK")
        return

    print("wiki_lint: FAILED")
    for name, values in issues.items():
        if not values:
            continue
        print(f"\n{name}:")
        for value in values:
            print(f"  - {value}")


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
