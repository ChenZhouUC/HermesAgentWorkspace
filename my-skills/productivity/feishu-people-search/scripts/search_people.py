#!/usr/bin/env python3
"""
Search ~/.hermes/people.yaml by name or keyword.
Returns Name, Address (称谓), Role, Department — and only these four.
Searches across name, aliases, address, role, and department for best match.
"""

import sys
import os
import difflib
import re

YAML_PATH = os.path.expanduser("~/.hermes/people.yaml")

try:
    import yaml
except ImportError:
    print("Error: pyyaml is required. Install with: pip install pyyaml")
    sys.exit(1)


def load_people(path):
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data.get("people", []) if data else []


def search_score(people_entry, query):
    """Return a relevance score. Higher = better match."""
    query = query.lower().strip()
    query_words = set(re.split(r"\s+", query))

    name = (people_entry.get("name") or "").lower()
    aliases = [a.lower() for a in people_entry.get("aliases", [])]
    address = (people_entry.get("address") or "").lower() if people_entry.get("address") else ""
    dept = (people_entry.get("department") or "").lower()
    role = (people_entry.get("role") or "").lower()

    # Build word sets for boundary matching
    name_words = set(re.split(r"[\s()]+", name))
    alias_words = set()
    for a in aliases:
        alias_words.update(re.split(r"[\s()]+", a))
    # 称呼常用 | 、 , 分隔多个（如 "华哥|张总|校长"），拆成独立可匹配的词
    address_words = set(re.split(r"[\s()|、,，]+", address)) if address else set()
    dept_words = set(re.split(r"[\s()&/]+", dept))
    role_words = set(re.split(r"[\s()&/]+", role))

    # Exact match on name or alias = highest score
    if query == name or query in aliases:
        return 100
    # Exact match on address
    if query == address:
        return 95
    # Query matches a full word in name or aliases
    if query_words & name_words or query in name_words:
        return 90
    if query_words & alias_words or query in alias_words:
        return 85
    # Word-boundary match on an address token (称呼，常以 | 分隔多个)
    if query_words & address_words or query in address_words:
        return 84
    # Word-boundary match on role or department (e.g. "CTO" matches "CTO" but not "director")
    if query_words & role_words or query in role_words:
        return 82
    if query_words & dept_words or query in dept_words:
        return 78
    # Substring match: name
    if query in name:
        return 70
    # Substring match: alias
    if any(query in a for a in aliases):
        return 67
    # Substring match: address
    if query in address:
        return 63
    # Substring match: role or department
    if query in role or query in dept:
        return 55
    # Fuzzy match via difflib
    all_text = " ".join([name] + aliases + ([address] if address else []))
    ratio = difflib.SequenceMatcher(None, query, all_text).ratio()
    if ratio > 0.4:
        return int(ratio * 50)

    return 0


def main():
    if len(sys.argv) < 2:
        print("Usage: python search_people.py 'keyword'")
        sys.exit(1)

    query = " ".join(sys.argv[1:])

    if not os.path.exists(YAML_PATH):
        print(f"Error: {YAML_PATH} not found")
        sys.exit(1)

    people = load_people(YAML_PATH)

    scored = []
    for p in people:
        score = search_score(p, query)
        if score > 0:
            scored.append((score, p))

    if not scored:
        print(f"No matches found for query: '{query}'")
        return

    # Sort by score descending
    scored.sort(key=lambda x: x[0], reverse=True)
    best_score = scored[0][0]

    # Group: only show entries within 8 points of the best score
    threshold = best_score - 8
    top_matches = [(s, p) for s, p in scored if s >= threshold]

    # If still too many, cap at 5
    if len(top_matches) > 5:
        top_matches = top_matches[:5]

    if len(top_matches) == 1:
        print("✅ 找到最匹配的结果：\n")
    else:
        print(f"找到 {len(top_matches)} 个可能的匹配（按相关度排序）：\n")

    for score, p in top_matches:
        name = p.get("name", "N/A")
        role = p.get("role", "N/A")
        dept = p.get("department", "N/A")
        address = p.get("address") or "(未设置)"
        print(f"- {name}")
        print(f"  - 称谓: {address}")
        print(f"  - 岗位: {role}")
        print(f"  - 团队: {dept}")
        if len(top_matches) > 1:
            print(f"  [相关度: {score}]")
        print()


if __name__ == "__main__":
    main()
