---
name: chart-generation
description: Turn extracted values into accurate shareable charts.
---

# Chart Generation Skill

Create deterministic PNG charts from data already present in the current
conversation. Hermes normally extracts XLSX/CSV content before this skill is
loaded, so charting starts from those extracted values rather than reopening
the original spreadsheet. The renderer uses Matplotlib for business templates
and Seaborn for relational, distribution, categorical, regression, matrix, and
multi-panel statistical charts.

## When to Use

Use for comparisons, trends, proportions, rankings, and relationships described
in text or visible in an extracted spreadsheet table.

Do not use a generative-image model for charts: labels, ordering, and numeric
values must remain faithful to the source. Decorative illustrations belong to
the separate `image-generation` skill.

## Tool Routing

- In an enabled Feishu group, call `group_chart_generate`.
- In the owner/main conversation, call `secure_chart_generate`.
- Never invoke plotting through `terminal`, `execute_code`, or ad-hoc scripts.

## Prepare the Data

For ordinary business charts, convert the relevant source rows into:

- `labels`: ordered category or time labels.
- `series`: one or more `{name, values}` objects aligned one-to-one with the
  labels.
- `x_values`: optional numeric X coordinates for a scatter plot.

For advanced Seaborn charts, use inline long-form `records` and identify fields
with `x_field`, `y_field`, `hue_field`, `style_field`, `size_field`, or
`weight_field`. Heatmaps may instead use `matrix`, `row_labels`, and
`column_labels`. Records and matrices must come from conversation-visible data;
never add file paths or URLs.

Do not invent missing values. Preserve source order unless the user requests a
ranking. If the selected columns or units are ambiguous, ask one concise
clarifying question.

For large extracted tables, chart only the rows and series needed to answer the
request. State any aggregation—sum, average, count, percentage, top-N—rather
than silently transforming the data.

## Choose a Chart

- `line`: ordered time series and trends.
- `bar`: category comparisons and multiple grouped series.
- `stacked_bar`: composition across categories.
- `horizontal_bar`: rankings or long category names.
- `area`: magnitude over an ordered sequence.
- `pie`: one positive series with preferably no more than eight categories.
- `scatter`: relationships; pass numeric `x_values` when available.
- `auto`: line for longer sequences, otherwise bar.
- `hist`, `kde`, `ecdf`, `rug`: distributions.
- `count`, `point`, `box`, `violin`, `boxen`, `strip`, `swarm`: categorical
  and sample-distribution views.
- `regression`, `residual`: fitted relationships and residual diagnostics.
- `heatmap`, `clustermap`: numeric matrices and correlation-style views.
- `joint`, `pair`: multi-variable exploratory views.
- `donut`, `waterfall`, `lollipop`: common business presentation templates.

Avoid pie charts for negative values, many categories, or close comparisons.
For the full chart/parameter routing table, read
[`references/options.md`](references/options.md).

Canvas dimensions are selected automatically from the chart family and data
shape. Layout presets only bias the result; all exported PNGs stay between a
`2:1` landscape ratio and a `1:2` portrait ratio.

## Procedure

1. Identify the intended comparison and unit.
2. Extract only the required labels and numeric values from the conversation.
3. Select the simplest truthful chart type.
4. Supply a concise title, axis labels, and optional subtitle for scope or unit.
5. Call the appropriate chart tool once.
6. If the user explicitly requested a referenced Feishu document destination,
   follow the `feishu-docs` placement rules. In a Feishu group, call
   `feishu_doc_manage` with `action="insert_image"` or `action="set_cover"`,
   passing the returned relative `workspace_path` as `image_path`. In the
   owner/main conversation, use the fixed `manage_doc_image.py` script with the
   generated file path from the tool result; do not expose that host path.
7. Otherwise, or when a chat copy was also requested, copy the returned
   `media_directive` verbatim onto its own line so the Gateway sends the PNG as
   a native Feishu image.

## Accuracy and Safety

- The tools accept only constrained business/statistical fields, never arbitrary
  Matplotlib/Seaborn kwargs, plotting specifications, Python code, URLs, or
  output paths.
- All chart data is embedded inline; the renderer runs without network access.
- Generated files stay in the current conversation's isolated workspace.
- Keep visible prose short and do not expose the local file path separately.
- If cell formatting such as strikethrough or fill changes the business meaning,
  load `excel-processing` before selecting the rows. The normal XLSX extraction
  primarily represents cell values.
- If the extracted spreadsheet data is truncated or lacks the required sheet,
  ask for a smaller export or the relevant rows instead of bypassing the
  sandbox to reopen the workbook.

## Verification

A successful result contains `success: true`, `chart_type`, `workspace_path`,
and `media_directive`. Check that the returned label and series counts match the
intended selection before claiming completion. For document-only requests, use
`workspace_path` with the document tool and omit the chat `media_directive`.
