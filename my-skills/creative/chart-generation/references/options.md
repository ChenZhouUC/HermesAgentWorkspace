# Chart Generation Presets

The Agent selects business intent and presets. The adapter owns Seaborn and
Matplotlib implementation parameters such as exact colors, background shades,
grid lines, spine widths, font sizes, histogram bins, KDE bandwidth, bootstrap
counts, and marker geometry.

## Data Shapes

### Labels and series

Use for ordinary business charts and simple statistical samples:

```json
{
  "labels": ["Q1", "Q2", "Q3"],
  "series": [{ "name": "Revenue", "values": [120, 160, 210] }]
}
```

Distribution and categorical charts can treat each series as a sample.

### Long-form records

Use for hue/style/size mappings, faceting, counts, regression, joint plots, and
pair plots:

```json
{
  "records": [
    { "month": "Jan", "revenue": 120, "region": "East" },
    { "month": "Jan", "revenue": 95, "region": "North" }
  ],
  "x_field": "month",
  "y_field": "revenue",
  "hue_field": "region"
}
```

At most 2,000 records and 20 scalar fields are accepted.

### Matrix

Use for heatmaps and cluster maps:

```json
{
  "matrix": [
    [1, 0.7],
    [0.7, 1]
  ],
  "row_labels": ["Revenue", "Traffic"],
  "column_labels": ["Revenue", "Traffic"]
}
```

## Supported Chart Types

| Family       | Types                                                                                   |
| ------------ | --------------------------------------------------------------------------------------- |
| Business     | `bar`, `stacked_bar`, `horizontal_bar`, `area`, `pie`, `donut`, `waterfall`, `lollipop` |
| Relational   | `line`, `scatter`                                                                       |
| Distribution | `hist`, `kde`, `ecdf`, `rug`                                                            |
| Categorical  | `count`, `point`, `box`, `violin`, `boxen`, `strip`, `swarm`                            |
| Regression   | `regression`, `residual`                                                                |
| Matrix       | `heatmap`, `clustermap`                                                                 |
| Composite    | `joint`, `pair`                                                                         |

`auto` chooses a line chart for longer sequences and a bar chart otherwise.

## Visual Presets

### `style_preset`

- `hidalgo` — default; inspired by `hidalgo/plotter.py`: pale gray plotting
  surface, white dotted grid, subtle gray spines, restrained labels, and a
  white outer canvas.
- `finance` — finance-oriented blue/green/amber palette and report contrast.
- `report` — lighter neutral canvas for documents.
- `presentation` — larger text and wide layout.
- `minimal` — white background and minimal grid.
- `statistical` — conventional Seaborn white-grid styling and colorblind-safe
  defaults.

### `palette_preset`

`auto`, `business`, `finance`, `muted`, `pastel`, `colorblind`, `blue`,
`green`, `warm`, `cool`, or `diverging`.

### `layout_preset`

`auto`, `compact`, `standard`, `wide`, `tall`, or `square`. Every layout starts
from a data-aware size estimate: rankings grow with their category count,
multi-series charts reserve more space for groups and legends, matrices follow
their row/column shape, and figure-level plots follow their panel grid. The
selected preset then biases that estimate rather than forcing fixed pixels.
Final output is always constrained to an aspect ratio between `2:1` and `1:2`.

### `detail_preset`

- `overview` — fewer bins/contours and faster bootstrapping.
- `balanced` — default.
- `detailed` — more bins/contours and higher statistical resolution.
- `smooth` — stronger smoothing and KDE emphasis.

## Statistical Presets

- `aggregation_preset`: `mean`, `median`, `sum`, `min`, `max`, or `count`.
- `uncertainty_preset`: `none`, `sd`, `se`, `ci90`, `ci95`, `pi90`, or `pi95`.
- `distribution_preset`: `count`, `density`, `probability`, `percent`,
  `comparison`, `stacked`, `filled`, `cumulative`, or `discrete`.
- `categorical_preset`: `summary`, `median`, `raw`, `compact`, or `detailed`.
- `regression_preset`: `linear`, `robust`, `lowess`, `quadratic`, `cubic`, or
  `logistic`.
- `matrix_preset`: `standard`, `annotated`, `diverging`, `clustered`,
  `row_normalized`, or `column_normalized`.

## Business Controls

- `title`, `subtitle`, `note`
- `x_label`, `y_label`, `unit`
- `value_format`: `auto`, `integer`, `decimal`, `compact`, `percent`, or a
  supported currency
- `decimals` and `percent_scale`
- `sort`: `none`, `ascending`, or `descending`
- `category_order`
- `highlight_label`
- `annotation_preset`: `auto`, `none`, `values`, `percent`, or `compact`
- `legend`: `auto`, `show`, or `hide`
- `legend_position`: `auto`, `top`, `right`, `bottom`, or `best`. `auto`
  prefers a right-side legend for up to four short series on a landscape
  canvas, preserving vertical plot area; larger legends move above the plot.
- `orientation` for stacked bars
- `x_scale` / `y_scale`: `linear`, `log`, or `symlog`
- axis bounds and up to six `reference_lines`
- `quality`: `standard`, `high`, or `print`

Static PNG files do not have interactive tooltips. Use value labels, legends,
notes, and reference lines for information that must remain visible in Feishu.

## Faceting and Composite Views

Long-form records may use `facet_row`, `facet_col`, and `col_wrap`. The adapter
uses Seaborn `relplot`, `displot`, `catplot`, or `lmplot` according to the chart
family. `joint_kind`, `pair_kind`, `diag_kind`, and `corner` control composite
views. Faceting should be used only when one clear chart cannot communicate the
result.

## Recommended Business Defaults

- Use `horizontal_bar` for rankings and long names.
- Sort costs/durations ascending; sort revenue/performance descending.
- Use `highlight_label` only when the user or data establishes the emphasis.
- Put dense methodology assumptions in `note`, not the subtitle.
- Single-series legends are hidden automatically.
- Set `value_format` and `unit` so labels remain self-contained.
