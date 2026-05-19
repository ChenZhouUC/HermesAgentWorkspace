---
name: excel-processing
description: "Techniques for parsing Excel (.xlsx) files, extracting values and semantic formatting (strikethroughs, colors) without heavy dependencies like pandas."
category: productivity
---

# Excel Data & Formatting Extraction

When extracting data from `.xlsx` files in an agentic workflow, `pandas` is the standard tool but has two major drawbacks:

1. **Installation Overhead**: `uv run --with pandas` can time out on slow network connections due to the size of the dependency tree.
2. **Loss of Semantics (CRITICAL)**: `pandas` only extracts raw textual values. Business users heavily rely on visual formatting (like **strikethroughs** to mark "deleted" rows or **background colors** for highlights) to convey structural data. `pandas` drops this metadata entirely, which can lead to catastrophic misinterpretation of things like diffs or resource reduction lists.

## Lightweight XML Parsing Technique

An `.xlsx` file is a ZIP archive containing structured XML. You can parse it flawlessly using only the Python standard library (`zipfile` and `xml.etree.ElementTree`).

1. **Shared Strings**: Read `xl/sharedStrings.xml` to map string indices to actual text.
2. **Styles**: Read `xl/styles.xml` (`cellXfs`, `fonts`, `fills`) to map style indices (the `s` attribute on `<c>` elements) to specific formattings (e.g., `<strike>` or `<color rgb="...">`).
3. **Worksheets**: Read `xl/worksheets/sheet1.xml` to iterate over `<row>` and `<c>` elements, joining the extracted text with its formatting metadata to reconstruct the full semantic meaning of the cell.

## Reference Script

A robust standard-library implementation is available in this skill's linked files. Use this script to extract text alongside its formatting (e.g., yielding `[STRIKETHROUGH: text]`), which is incredibly useful for generating diffs.

- **`scripts/xlsx_xml_parser.py`**
