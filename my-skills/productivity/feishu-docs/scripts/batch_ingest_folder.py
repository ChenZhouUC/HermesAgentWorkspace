#!/usr/bin/env python3
"""Atomically extract a Feishu folder into the Wiki's _living source layer."""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path

from feishu_common import do_req, get_tenant_token


SCRIPT_DIR = Path(__file__).resolve().parent
EXTRACT_SCRIPT = SCRIPT_DIR / "extract_docx_to_markdown.py"


def wiki_root() -> Path:
    configured = os.getenv("WIKI_PATH", "").strip()
    if configured:
        return Path(configured).expanduser().resolve()
    home = Path(os.getenv("HERMES_HOME", Path.home() / ".hermes")).expanduser()
    return (home / "wiki").resolve()


def clean_feishu_markdown(content: str) -> str:
    """Remove Feishu presentation artifacts without adding Wiki semantics."""
    table_pattern = re.compile(r"^\| Col 0.*?\n(?:\|.*?\n)+", re.MULTILINE)
    content = table_pattern.sub("", content, count=1)
    mention_pattern = re.compile(r"\[@ou_[a-zA-Z0-9]+\]|@ou_[a-zA-Z0-9]+")
    content = mention_pattern.sub("", content)
    return re.sub(r"\n{3,}", "\n\n", content).strip()


def safe_filename(title: str) -> str:
    stem = re.sub(r"[\\/:*?\"<>|]+", "-", title.strip())
    stem = re.sub(r"[\s、，]+", "-", stem).strip("-. ")
    stem = stem or "untitled-source"
    return stem if stem.lower().endswith(".md") else stem + ".md"


def render_living_source(title: str, content: str) -> str:
    """Render a living source with no Layer 2 semantic frontmatter."""
    if re.match(r"^#\s+", content):
        return content.rstrip() + "\n"
    return f"# {title}\n\n{content.rstrip()}\n"


def _assert_living_destination(category_path: Path, root: Path) -> Path:
    living = (root / "_living").resolve()
    destination = category_path.expanduser().resolve()
    try:
        destination.relative_to(living)
    except ValueError as exc:
        raise ValueError(f"Destination must stay under {living}: {destination}") from exc
    if destination == living:
        raise ValueError("Choose a SCHEMA-compliant _living topic directory, not _living itself")
    return destination


def _daily_log_text(
    existing: str,
    saved: list[Path],
    root: Path,
    *,
    today: str | None = None,
) -> str:
    today = today or datetime.now().strftime("%Y-%m-%d")
    heading_pattern = re.compile(rf"^## \[{re.escape(today)}\] daily \|.*$", re.MULTILINE)
    rel_paths = [path.relative_to(root).as_posix() for path in saved]
    block = [
        "### ingest | Feishu folder source extraction",
        "",
        f"- Actions: extracted {len(rel_paths)} document(s) into the `_living` source layer",
        "- Files:",
        *[f"  - `{path}`" for path in rel_paths],
        "- Boundary: layout conversion only; Layer 2 synthesis and semantic review remain separate",
        "- Verification: run `python3 scripts/wiki_lint.py` after semantic review",
        "",
    ]
    addition = "\n".join(block)

    match = heading_pattern.search(existing)
    if not match:
        prefix = existing.rstrip()
        if prefix:
            prefix += "\n\n"
        return prefix + f"## [{today}] daily | Wiki maintenance\n\n" + addition

    next_heading = re.search(r"^## \[[0-9]{4}-[0-9]{2}-[0-9]{2}\] ", existing[match.end() :], re.MULTILINE)
    insert_at = match.end() + (next_heading.start() if next_heading else len(existing[match.end() :]))
    before = existing[:insert_at].rstrip()
    after = existing[insert_at:].lstrip("\n")
    combined = before + "\n\n" + addition
    if after:
        combined += "\n" + after
    return combined


def _atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as tmp:
        tmp.write(content)
        tmp_path = Path(tmp.name)
    os.replace(tmp_path, path)


def ingest_folder(
    folder_token: str,
    category_path: Path,
    *,
    dry_run: bool = False,
    today: str | None = None,
) -> list[Path]:
    root = wiki_root()
    destination = _assert_living_destination(category_path, root)
    token = get_tenant_token()
    response = do_req(
        token,
        f"https://open.feishu.cn/open-apis/drive/v1/files?folder_token={folder_token}",
    )
    files = response.get("data", {}).get("files", [])
    staged: list[tuple[Path, str]] = []

    for item in files:
        title = str(item.get("name") or "untitled-source")
        file_token = str(item.get("token") or "")
        if not file_token:
            raise RuntimeError(f"Feishu folder entry has no token: {title}")
        command = [sys.executable, str(EXTRACT_SCRIPT), file_token]
        try:
            extracted = subprocess.check_output(command, stderr=subprocess.STDOUT, text=True)
        except subprocess.CalledProcessError as exc:
            raise RuntimeError(f"Failed to extract {title}: {exc.output}") from exc
        target = destination / safe_filename(title)
        if target.exists():
            raise FileExistsError(f"Refusing to overwrite existing living source: {target}")
        staged.append((target, render_living_source(title, clean_feishu_markdown(extracted))))

    if not staged:
        print("No extractable documents found in the Feishu folder")
        return []

    if dry_run:
        for target, _ in staged:
            print(f"would write: {target}")
        return [target for target, _ in staged]

    destination.mkdir(parents=True, exist_ok=True)
    log_path = root / "log.md"
    if not log_path.exists():
        raise FileNotFoundError(f"Wiki log is missing: {log_path}")

    written: list[Path] = []
    try:
        for target, content in staged:
            _atomic_write(target, content)
            written.append(target)
        new_log = _daily_log_text(log_path.read_text(encoding="utf-8"), written, root, today=today)
        _atomic_write(log_path, new_log)
    except Exception:
        for path in written:
            path.unlink(missing_ok=True)
        raise

    for path in written:
        print(f"saved: {path}")
    print("Next: review reusable content, derive Layer 2 with wiki-content-extraction, then run wiki_lint.py")
    return written


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("folder_token")
    parser.add_argument("category_path", type=Path)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    ingest_folder(args.folder_token, args.category_path, dry_run=args.dry_run)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
