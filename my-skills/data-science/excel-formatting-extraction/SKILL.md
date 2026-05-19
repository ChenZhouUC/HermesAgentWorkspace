---
name: excel-formatting-extraction
description: Extract hidden semantic formatting (strikethroughs, font colors, background fills) from .xlsx files using native zipfile/xml parsing when pandas cannot.
category: data-science
---

# Advanced Excel Formatting Extraction

When users provide `.xlsx` files representing "diffs", "reviews", or "downgrades", they often use rich formatting (strikethroughs for deletions, red text for warnings, background colors for highlights) to convey semantic meaning. Standard libraries like `pandas` completely drop this formatting.

To extract this data, read the `.xlsx` as a ZIP archive and parse the underlying OpenXML structure using standard library `zipfile` and `xml.etree.ElementTree`.

## Key Files in .xlsx Zip

1. `xl/sharedStrings.xml`: Contains the actual text. If a cell contains rich formatting (part of the text is struck through), the `<si>` node will contain multiple `<r>` (run) nodes, each with its own `<rPr>` (run properties) and `<t>` (text).
2. `xl/styles.xml`: Contains `cellXfs` (cell formats), `fonts`, and `fills`.
3. `xl/worksheets/sheet1.xml`: The actual sheet data. `<c>` (cell) elements reference styles via the `s="idx"` attribute and strings via `<v>idx</v>` when `t="s"`.

## Pitfalls

- **Cell-level vs. Run-level formatting**: A cell might have a global strikethrough applied via `styles.xml` (the `s` attribute on the `<c>` element points to a `cellXf` which points to a `fontId`), OR it might have partial rich-text formatting inside `sharedStrings.xml` (the `<r>` nodes have `<strike>` tags). You must check **both** to guarantee you don't miss a deletion.
- **Namespace handling**: OpenXML uses namespaces heavily. Always use `ns = {'ns': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}` in `findall`.

## Scripts

- `scripts/extract_xlsx_formatting.py`: A reusable script that parses rows and outputs text with `[STRIKETHROUGH: text]` or `[COLOR:...]` markers.
