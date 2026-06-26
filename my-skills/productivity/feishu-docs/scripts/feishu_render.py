"""Tiny stdlib-only render helpers shared by the Feishu read scripts.

Kept dependency-free (no tabulate) so the scripts run under any interpreter the
group sandbox hands them. ``md_table`` renders a GitHub-flavoured markdown table;
``flatten_cell`` / ``flatten_field`` collapse Feishu's rich-value shapes (lists of
segment dicts, link/mention objects) into plain text.
"""

import json


def _esc(text):
    return str("" if text is None else text).replace("\n", " ").replace("\r", " ").replace("|", "\\|").strip()


def md_table(headers, rows):
    """Render a markdown table. ``headers`` is a list; ``rows`` a list of lists.

    Rows are padded/truncated to the header width so the table stays well-formed.
    """
    headers = [_esc(h) for h in (headers or [])]
    width = len(headers) or 1
    if not headers:
        headers = [""]
    out = ["| " + " | ".join(headers) + " |", "| " + " | ".join(["---"] * width) + " |"]
    for row in rows or []:
        cells = [_esc(c) for c in row]
        cells = (cells + [""] * width)[:width]
        out.append("| " + " | ".join(cells) + " |")
    return "\n".join(out)


def flatten_cell(value):
    """Flatten a Feishu Sheets v2 cell value (str/number/None or rich-segment list)."""
    if value is None:
        return ""
    if isinstance(value, (str, int, float, bool)):
        return str(value)
    if isinstance(value, list):
        parts = []
        for seg in value:
            if isinstance(seg, dict):
                parts.append(seg.get("text") or seg.get("link") or seg.get("mention") or "")
            else:
                parts.append(str(seg))
        return "".join(p for p in parts if p)
    if isinstance(value, dict):
        return value.get("text") or value.get("link") or json.dumps(value, ensure_ascii=False)
    return str(value)


def flatten_field(value):
    """Flatten a Feishu Bitable field value (text/number/person/link/... shapes)."""
    if value is None:
        return ""
    if isinstance(value, (str, int, float, bool)):
        return str(value)
    if isinstance(value, list):
        parts = []
        for seg in value:
            if isinstance(seg, dict):
                parts.append(
                    seg.get("text")
                    or seg.get("name")
                    or seg.get("en_name")
                    or seg.get("link")
                    or json.dumps(seg, ensure_ascii=False)
                )
            else:
                parts.append(str(seg))
        return ", ".join(p for p in parts if p)
    if isinstance(value, dict):
        return value.get("text") or value.get("name") or value.get("link") or json.dumps(value, ensure_ascii=False)
    return str(value)
