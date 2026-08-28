#!/usr/bin/env python3
"""Render a constrained ChartRequest with Matplotlib and Seaborn.

The helper accepts JSON on stdin, performs no network access, and writes only
below ``HERMES_CHART_WORKSPACE``. Agent callers never supply Python code,
arbitrary plotting kwargs, paths, URLs, or backend configuration.
"""

from __future__ import annotations

import json
import math
import os
import tempfile
import textwrap
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from fontTools.ttLib import TTCollection
from matplotlib import font_manager
from matplotlib.axes import Axes
from matplotlib.figure import Figure
from matplotlib.ticker import FuncFormatter

MAX_REQUEST_BYTES = 512 * 1024
MAX_LABELS = 500
MAX_SERIES = 12
MAX_RECORDS = 2_000
MAX_RECORD_FIELDS = 20
MAX_MATRIX_SIDE = 120
MAX_POINTS = 5_000
MAX_TEXT_CHARS = 300
MIN_FIGURE_ASPECT = 0.5
MAX_FIGURE_ASPECT = 2.0
MIN_FIGURE_INCHES = 4.8
MAX_FIGURE_INCHES = 16.0

BUSINESS_TYPES = {
    "bar",
    "stacked_bar",
    "horizontal_bar",
    "area",
    "pie",
    "donut",
    "waterfall",
    "lollipop",
}
RELATIONAL_TYPES = {"line", "scatter"}
DISTRIBUTION_TYPES = {"hist", "kde", "ecdf", "rug"}
CATEGORICAL_TYPES = {"count", "point", "box", "violin", "boxen", "strip", "swarm"}
REGRESSION_TYPES = {"regression", "residual"}
MATRIX_TYPES = {"heatmap", "clustermap"}
COMPOSITE_TYPES = {"joint", "pair"}
CHART_TYPES = (
    {"auto"}
    | BUSINESS_TYPES
    | RELATIONAL_TYPES
    | DISTRIBUTION_TYPES
    | CATEGORICAL_TYPES
    | REGRESSION_TYPES
    | MATRIX_TYPES
    | COMPOSITE_TYPES
)

BUSINESS_PALETTE = [
    "#3B6FB6",
    "#7357B4",
    "#2A8C8C",
    "#5A9F68",
    "#D28B3C",
    "#C65A5A",
    "#B65F93",
    "#5D6CC0",
    "#8BA84A",
    "#C97045",
    "#4E8799",
    "#9270B4",
]
FINANCE_PALETTE = ["#2867A5", "#4D9B72", "#D6A33C", "#B85450", "#6F64A8", "#4D8796"]
HIGHLIGHT_COLOR = "#27A269"
SOURCE_HAN_SC_NAMES = ("SourceHanSans-Regular.ttc", "SourceHanSans-Normal.ttc")
FONT_FILES = (
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/System/Library/Fonts/PingFang.ttc",
    "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
)

STYLE_PRESETS: dict[str, dict[str, object]] = {
    # Matches the visual language of hidalgo/plotter.py: pale gray plotting
    # surface, white dotted grid, visible subtle spines, and restrained text.
    "hidalgo": {
        "theme": "business",
        "palette": "business",
        "context": "notebook",
        "grid": "auto",
        "legend": "auto",
        "quality": "high",
    },
    "finance": {
        "theme": "finance",
        "palette": "finance",
        "context": "notebook",
        "grid": "auto",
        "legend": "auto",
        "quality": "high",
    },
    "report": {
        "theme": "light",
        "palette": "muted",
        "context": "notebook",
        "grid": "auto",
        "legend": "auto",
        "quality": "high",
    },
    "presentation": {
        "theme": "presentation",
        "palette": "business",
        "context": "talk",
        "grid": "auto",
        "figure_size": "wide",
        "quality": "high",
    },
    "minimal": {
        "theme": "minimal",
        "palette": "colorblind",
        "context": "notebook",
        "grid": "none",
        "legend": "auto",
    },
    "statistical": {
        "theme": "whitegrid",
        "palette": "colorblind",
        "context": "notebook",
        "grid": "auto",
        "legend": "auto",
    },
}

PALETTE_PRESETS = {
    "auto": None,
    "business": "business",
    "finance": "finance",
    "muted": "muted",
    "pastel": "pastel",
    "colorblind": "colorblind",
    "blue": "blues",
    "green": "greens",
    "warm": "rocket",
    "cool": "mako",
    "diverging": "vlag",
}

LAYOUT_PRESETS = {
    "auto": "auto",
    "compact": "compact",
    "standard": "standard",
    "wide": "wide",
    "tall": "tall",
    "square": "square",
}

DETAIL_PRESETS: dict[str, dict[str, object]] = {
    "overview": {
        "bins": 12,
        "gridsize": 100,
        "levels": 7,
        "n_boot": 500,
        "marker_size": 4.0,
        "line_width": 1.5,
    },
    "balanced": {
        "bins": 24,
        "gridsize": 200,
        "levels": 10,
        "n_boot": 1_000,
        "marker_size": 5.0,
        "line_width": 2.0,
    },
    "detailed": {
        "bins": 40,
        "gridsize": 400,
        "levels": 16,
        "n_boot": 2_000,
        "marker_size": 6.0,
        "line_width": 2.4,
    },
    "smooth": {
        "bins": 30,
        "gridsize": 300,
        "levels": 12,
        "bw_adjust": 1.5,
        "kde_overlay": True,
        "n_boot": 1_000,
    },
}

AGGREGATION_PRESETS = {
    "mean": "mean",
    "median": "median",
    "sum": "sum",
    "min": "min",
    "max": "max",
    "count": "count",
}

UNCERTAINTY_PRESETS = {
    "none": "none",
    "sd": "sd",
    "se": "se",
    "ci90": "ci90",
    "ci95": "ci95",
    "pi90": "pi90",
    "pi95": "pi95",
}

DISTRIBUTION_PRESETS: dict[str, dict[str, object]] = {
    "count": {"stat": "count", "multiple": "layer", "common_norm": True},
    "density": {"stat": "density", "multiple": "layer", "common_norm": True},
    "probability": {"stat": "probability", "multiple": "layer", "common_norm": True},
    "percent": {"stat": "percent", "multiple": "layer", "common_norm": True},
    "comparison": {"stat": "density", "multiple": "dodge", "common_norm": False},
    "stacked": {"stat": "count", "multiple": "stack", "common_norm": True},
    "filled": {"stat": "proportion", "multiple": "fill", "common_norm": True},
    "cumulative": {"stat": "proportion", "cumulative": True},
    "discrete": {"stat": "count", "discrete": True, "shrink": 0.85},
}

REGRESSION_PRESETS: dict[str, dict[str, object]] = {
    "linear": {"regression_order": 1},
    "robust": {"regression_order": 1, "robust": True},
    "lowess": {"regression_order": 1, "lowess": True, "ci": 0},
    "quadratic": {"regression_order": 2},
    "cubic": {"regression_order": 3},
    "logistic": {"regression_order": 1, "logistic": True},
}

CATEGORICAL_PRESETS: dict[str, dict[str, object]] = {
    "summary": {"estimator": "mean", "errorbar": "ci95", "show_fliers": True},
    "median": {"estimator": "median", "errorbar": "none", "show_fliers": True},
    "raw": {"jitter": True, "alpha": 0.78, "marker_size": 5.0},
    "compact": {"show_fliers": False, "gap": 0.08, "marker_size": 4.0},
    "detailed": {"show_fliers": True, "inner": "quart", "gridsize": 300},
}

MATRIX_PRESETS: dict[str, dict[str, object]] = {
    "standard": {"cmap": "Blues", "annotate": False},
    "annotated": {"cmap": "Blues", "annotate": True},
    "diverging": {"cmap": "vlag", "center": 0, "annotate": True},
    "clustered": {"chart_type": "clustermap", "cmap": "mako"},
    "row_normalized": {"chart_type": "clustermap", "z_score": 0, "cmap": "vlag"},
    "column_normalized": {"chart_type": "clustermap", "z_score": 1, "cmap": "vlag"},
}


class ChartError(RuntimeError):
    """A bounded chart input or rendering failure."""


@dataclass
class ChartData:
    frame: pd.DataFrame
    wide: pd.DataFrame | None
    matrix: pd.DataFrame | None
    labels: list[str]
    series_names: list[str]
    x: str | None
    y: str | None
    hue: str | None
    style: str | None
    size: str | None
    weight: str | None


def _workspace() -> Path:
    raw = os.environ.get("HERMES_CHART_WORKSPACE", "").strip()
    if not raw:
        raise ChartError("chart workspace is not configured")
    workspace = Path(raw).resolve(strict=True)
    if not workspace.is_dir() or workspace.is_symlink():
        raise ChartError("chart workspace is unavailable")
    return workspace


def _text(value: object, *, limit: int = MAX_TEXT_CHARS) -> str:
    rendered = str(value or "").strip()
    rendered = "".join(char for char in rendered if char in "\n\t" or ord(char) >= 32)
    return rendered[:limit]


def _number(value: object) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        number = float(value)
        return number if math.isfinite(number) else None
    text = str(value).strip()
    if not text:
        return None
    negative = text.startswith("(") and text.endswith(")")
    text = text.strip("()").replace(",", "").lstrip("¥￥$€£").removesuffix("%")
    try:
        number = float(text)
    except ValueError:
        return None
    if negative:
        number = -number
    return number if math.isfinite(number) else None


def _bounded_float(value: object, default: float, minimum: float, maximum: float) -> float:
    number = _number(value)
    if number is None:
        return default
    return max(minimum, min(maximum, number))


def _bounded_int(value: object, default: int, minimum: int, maximum: int) -> int:
    number = _number(value)
    if number is None:
        return default
    return max(minimum, min(maximum, int(number)))


def _optional_number(value: object) -> float | None:
    return None if value is None or value == "" else _number(value)


def _field(request: dict[str, Any], name: str, frame: pd.DataFrame, *, required: bool = False) -> str | None:
    value = _text(request.get(name), limit=80)
    if not value:
        if required:
            raise ChartError(f"{name} is required for this chart type")
        return None
    if value not in frame.columns:
        raise ChartError(f"{name} does not name a field in records: {value}")
    return value


def _records_frame(raw: object) -> pd.DataFrame:
    if not isinstance(raw, list) or not raw:
        raise ChartError("records must be a non-empty list")
    if len(raw) > MAX_RECORDS:
        raise ChartError(f"records exceed the {MAX_RECORDS} row limit")
    cleaned: list[dict[str, object]] = []
    fields: set[str] = set()
    for row_number, item in enumerate(raw, start=1):
        if not isinstance(item, dict) or len(item) > MAX_RECORD_FIELDS:
            raise ChartError(f"record {row_number} must be an object with at most {MAX_RECORD_FIELDS} fields")
        row: dict[str, object] = {}
        for raw_key, raw_value in item.items():
            key = _text(raw_key, limit=80)
            if not key:
                raise ChartError(f"record {row_number} contains an empty field name")
            if isinstance(raw_value, (dict, list, tuple, set)):
                raise ChartError("record values must be scalar")
            fields.add(key)
            row[key] = raw_value
        cleaned.append(row)
    if len(fields) > MAX_RECORD_FIELDS:
        raise ChartError(f"records exceed the {MAX_RECORD_FIELDS} field limit")
    return pd.DataFrame(cleaned)


def _series_data(request: dict[str, Any], chart_type: str) -> ChartData:
    labels_raw = request.get("labels")
    series_raw = request.get("series")
    if chart_type == "count" and isinstance(labels_raw, list) and not series_raw:
        labels = [_text(value, limit=100) or str(index + 1) for index, value in enumerate(labels_raw)]
        if len(labels) > MAX_LABELS:
            raise ChartError(f"labels exceed the {MAX_LABELS} item limit")
        frame = pd.DataFrame({"category": labels})
        return ChartData(frame, None, None, labels, [], "category", None, None, None, None, None)
    if not isinstance(labels_raw, list) or not labels_raw:
        raise ChartError("labels must be a non-empty list when records are omitted")
    if len(labels_raw) > MAX_LABELS:
        raise ChartError(f"labels exceed the {MAX_LABELS} item limit")
    if not isinstance(series_raw, list) or not series_raw:
        raise ChartError("series must be a non-empty list when records are omitted")
    if len(series_raw) > MAX_SERIES:
        raise ChartError(f"series exceed the {MAX_SERIES} item limit")

    labels = [_text(value, limit=100) or str(index + 1) for index, value in enumerate(labels_raw)]
    x_values_raw = request.get("x_values")
    x_values: list[float] | None = None
    if x_values_raw is not None:
        if not isinstance(x_values_raw, list) or len(x_values_raw) != len(labels):
            raise ChartError("x_values must align one-to-one with labels")
        x_values = []
        for value in x_values_raw:
            number = _number(value)
            if number is None:
                raise ChartError("x_values must contain only finite numbers")
            x_values.append(number)

    rows: list[dict[str, object]] = []
    wide: dict[str, list[float | None]] = {}
    names: list[str] = []
    total_points = 0
    for series_index, item in enumerate(series_raw, start=1):
        if not isinstance(item, dict) or not isinstance(item.get("values"), list):
            raise ChartError("each series requires a name and values list")
        values_raw = item["values"]
        if len(values_raw) != len(labels):
            raise ChartError("every series must have the same number of values as labels")
        name = _text(item.get("name"), limit=100) or f"Series {series_index}"
        if name in names:
            name = f"{name} ({series_index})"
        names.append(name)
        numeric_values = [_number(value) for value in values_raw]
        if chart_type != "count" and not any(value is not None for value in numeric_values):
            raise ChartError(f"series {series_index} has no numeric values")
        wide[name] = numeric_values
        total_points += len(values_raw)
        if total_points > MAX_POINTS:
            raise ChartError(f"chart exceeds the {MAX_POINTS} point limit")
        for order, (label, raw_value, numeric) in enumerate(zip(labels, values_raw, numeric_values, strict=True)):
            rows.append(
                {
                    "category": label,
                    "series": name,
                    "value": numeric,
                    "raw_value": raw_value,
                    "order": order,
                    "x": x_values[order] if x_values is not None else order,
                    "series_order": series_index - 1,
                }
            )
    frame = pd.DataFrame(rows)
    wide_frame = pd.DataFrame(wide, index=labels)
    hue = "series" if len(names) > 1 else None
    if chart_type in DISTRIBUTION_TYPES:
        x, y = "value", None
    elif chart_type in {"box", "violin", "boxen", "strip", "swarm"}:
        x, y = "series", "value"
        hue = None
    elif chart_type in REGRESSION_TYPES | {"scatter"}:
        x, y = "x", "value"
    else:
        x, y = "category", "value"
    return ChartData(frame, wide_frame, None, labels, names, x, y, hue, None, None, None)


def _matrix_data(request: dict[str, Any]) -> pd.DataFrame:
    raw = request.get("matrix")
    if not isinstance(raw, list) or not raw:
        raise ChartError("matrix must be a non-empty 2D list")
    if len(raw) > MAX_MATRIX_SIDE:
        raise ChartError(f"matrix exceeds {MAX_MATRIX_SIDE} rows")
    width = None
    matrix: list[list[float]] = []
    for row in raw:
        if not isinstance(row, list) or not row:
            raise ChartError("every matrix row must be a non-empty list")
        if width is None:
            width = len(row)
        if len(row) != width or len(row) > MAX_MATRIX_SIDE:
            raise ChartError("matrix rows must have equal length within the size limit")
        converted: list[float] = []
        for value in row:
            number = _number(value)
            if number is None:
                raise ChartError("matrix values must be finite numbers")
            converted.append(number)
        matrix.append(converted)
    row_labels_raw = request.get("row_labels")
    col_labels_raw = request.get("column_labels")
    row_labels = (
        [_text(value, limit=80) for value in row_labels_raw]
        if isinstance(row_labels_raw, list) and len(row_labels_raw) == len(matrix)
        else [str(index + 1) for index in range(len(matrix))]
    )
    col_labels = (
        [_text(value, limit=80) for value in col_labels_raw]
        if isinstance(col_labels_raw, list) and len(col_labels_raw) == width
        else [str(index + 1) for index in range(width or 0)]
    )
    return pd.DataFrame(matrix, index=row_labels, columns=col_labels)


def _records_data(request: dict[str, Any], chart_type: str) -> ChartData:
    frame = _records_frame(request.get("records"))
    if chart_type in MATRIX_TYPES:
        x = _field(request, "x_field", frame, required=True)
        y = _field(request, "y_field", frame, required=True)
        value = _field(request, "value_field", frame, required=True)
        frame[value] = pd.to_numeric(frame[value], errors="coerce")
        matrix = frame.pivot_table(index=y, columns=x, values=value, aggfunc="mean")
        return ChartData(frame, None, matrix, [], [], None, None, None, None, None, None)

    x_required = chart_type not in DISTRIBUTION_TYPES | {"pair"}
    y_required = chart_type in RELATIONAL_TYPES | REGRESSION_TYPES | {"joint"}
    x = _field(request, "x_field", frame, required=x_required)
    y = _field(request, "y_field", frame, required=y_required)
    hue = _field(request, "hue_field", frame)
    style = _field(request, "style_field", frame)
    size = _field(request, "size_field", frame)
    weight = _field(request, "weight_field", frame)
    if chart_type in DISTRIBUTION_TYPES and not x:
        x = y or _field(request, "value_field", frame, required=True)
        y = None
    for field in {field for field in (y, size, weight) if field}:
        frame[field] = pd.to_numeric(frame[field], errors="coerce")
    if chart_type in RELATIONAL_TYPES | REGRESSION_TYPES | {"joint"} and x and request.get("x_numeric", True):
        converted = pd.to_numeric(frame[x], errors="coerce")
        if converted.notna().any():
            frame[x] = converted
    names = [str(value) for value in frame[hue].dropna().unique()] if hue else []
    labels = [str(value) for value in frame[x].dropna().unique()] if x else []
    return ChartData(frame, None, None, labels, names, x, y, hue, style, size, weight)


def _resolve_data(request: dict[str, Any], chart_type: str) -> ChartData:
    if chart_type in MATRIX_TYPES and request.get("matrix") is not None:
        matrix = _matrix_data(request)
        return ChartData(pd.DataFrame(), None, matrix, [], [], None, None, None, None, None, None)
    if request.get("records") is not None:
        return _records_data(request, chart_type)
    return _series_data(request, chart_type)


def _source_han_sc_font() -> str | None:
    workspace = _workspace()
    font_dir = workspace / ".fonts"
    target = font_dir / "SourceHanSansSC-Regular.otf"
    if not target.is_file():
        search_roots = (
            Path.home() / "Library" / "Fonts",
            Path("/Library/Fonts"),
            Path("/usr/share/fonts/opentype"),
            Path("/usr/share/fonts/truetype"),
        )
        candidates = [root / name for root in search_roots for name in SOURCE_HAN_SC_NAMES]
        for collection_path in candidates:
            if not collection_path.is_file():
                continue
            collection = TTCollection(str(collection_path), lazy=False)
            try:
                for font in collection.fonts:
                    families = {name.toUnicode() for name in font["name"].names if name.nameID == 1}
                    if "Source Han Sans SC" not in families:
                        continue
                    font_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
                    with tempfile.NamedTemporaryFile(
                        dir=font_dir,
                        prefix=".source-han-sc-",
                        suffix=".otf",
                        delete=False,
                    ) as handle:
                        staged = Path(handle.name)
                    try:
                        font.save(staged)
                        os.chmod(staged, 0o600)
                        os.replace(staged, target)
                    finally:
                        if staged.exists():
                            staged.unlink()
                    break
            finally:
                collection.close()
            if target.is_file():
                break
    if not target.is_file():
        return None
    try:
        font_manager.fontManager.addfont(str(target))
        return font_manager.FontProperties(fname=str(target)).get_name()
    except Exception:  # noqa: BLE001 - use the portable fallback chain
        return None


def _font_name() -> str:
    source_han = _source_han_sc_font()
    if source_han:
        return source_han
    for raw in FONT_FILES:
        path = Path(raw)
        if not path.is_file():
            continue
        try:
            font_manager.fontManager.addfont(str(path))
            return font_manager.FontProperties(fname=str(path)).get_name()
        except Exception:  # noqa: BLE001,S112 - try the next installed font
            continue
    return "DejaVu Sans"


def _palette(request: dict[str, Any], count: int) -> list[Any]:
    name = str(request.get("palette") or "business").strip().lower()
    if name == "business":
        values: list[Any] = BUSINESS_PALETTE
    elif name == "finance":
        values = FINANCE_PALETTE
    else:
        allowed = {
            "deep",
            "muted",
            "pastel",
            "bright",
            "dark",
            "colorblind",
            "blues",
            "greens",
            "viridis",
            "mako",
            "rocket",
            "flare",
            "crest",
        }
        values = list(sns.color_palette(name if name in allowed else "deep", n_colors=max(count, 1)))
    if len(values) >= count:
        return values[:count]
    return (values * math.ceil(count / len(values)))[:count]


def _setup_theme(request: dict[str, Any]) -> str:
    font = _font_name()
    theme = str(request.get("theme") or "business").strip().lower()
    context = str(request.get("context") or "notebook").strip().lower()
    if context not in {"paper", "notebook", "talk", "poster"}:
        context = "notebook"
    axes_face = "#E7EBEF"
    grid_color = "#FFFFFF"
    grid_style = ":"
    axes_edge = "#969696"
    label_color = "#646464"
    tick_color = "#646464"
    if theme == "finance":
        axes_face = "#EDF2F4"
    elif theme == "light":
        axes_face, grid_color = "#F7F9FB", "#DDE3EA"
    elif theme == "whitegrid":
        axes_face, grid_color, grid_style = "#FFFFFF", "#D9DEE5", "--"
    elif theme == "darkgrid":
        axes_face = "#EAEAF2"
    elif theme == "minimal":
        axes_face, grid_color = "#FFFFFF", "#E5E7EB"
    elif theme == "presentation":
        axes_face, context = "#EEF2F5", "talk"
    sns.set_theme(
        context=context,
        style="darkgrid" if theme not in {"minimal", "whitegrid"} else "whitegrid",
        font=font,
        rc={
            "figure.facecolor": "#FFFFFF",
            "figure.edgecolor": "#FFFFFF",
            "axes.facecolor": axes_face,
            "axes.edgecolor": axes_edge,
            "axes.spines.left": True,
            "axes.spines.bottom": True,
            "axes.spines.right": True,
            "axes.spines.top": True,
            "axes.labelcolor": label_color,
            "axes.labelweight": "bold",
            "axes.labelsize": 11,
            "axes.titleweight": "bold",
            "axes.titlesize": 13,
            "axes.unicode_minus": False,
            "grid.color": grid_color,
            "grid.linestyle": grid_style,
            "grid.linewidth": 1.15,
            "grid.alpha": 0.95,
            "xtick.color": tick_color,
            "ytick.color": tick_color,
            "xtick.labelsize": 10,
            "ytick.labelsize": 10,
            "xtick.direction": "out",
            "ytick.direction": "out",
            "xtick.major.width": 1.2,
            "ytick.major.width": 1.2,
            "xtick.major.size": 4,
            "ytick.major.size": 4,
            "text.color": "#243447",
            "legend.frameon": False,
            "savefig.bbox": None,
            "savefig.transparent": False,
            "savefig.facecolor": "#FFFFFF",
            "savefig.edgecolor": "#FFFFFF",
            "savefig.pad_inches": 0.18,
        },
    )
    return font


def _bounded_figure_size(width: float, height: float) -> tuple[float, float]:
    """Keep every rendered figure readable and within a 2:1–1:2 frame."""
    width, height = max(width, 1.0), max(height, 1.0)
    aspect = width / height
    if aspect > MAX_FIGURE_ASPECT:
        height = width / MAX_FIGURE_ASPECT
    elif aspect < MIN_FIGURE_ASPECT:
        width = height * MIN_FIGURE_ASPECT

    largest = max(width, height)
    if largest > MAX_FIGURE_INCHES:
        scale = MAX_FIGURE_INCHES / largest
        width, height = width * scale, height * scale
    smallest = min(width, height)
    if smallest < MIN_FIGURE_INCHES:
        scale = MIN_FIGURE_INCHES / smallest
        width, height = width * scale, height * scale
    return round(width, 2), round(height, 2)


def _size(
    request: dict[str, Any],
    chart_type: str,
    category_count: int,
    series_count: int = 1,
    secondary_count: int = 1,
) -> tuple[float, float]:
    """Estimate a data-aware canvas, then apply the selected layout bias."""
    categories = max(category_count, 1)
    series = max(series_count, 1)
    secondary = max(secondary_count, 1)

    if chart_type in {"horizontal_bar", "lollipop"}:
        width = 9.4 + min(2.0, (series - 1) * 0.35)
        height = 3.8 + categories * (0.48 + min(series - 1, 3) * 0.06)
    elif chart_type in {"bar", "stacked_bar", "waterfall", *CATEGORICAL_TYPES}:
        width = 8.2 + min(5.8, categories * 0.34 + (series - 1) * 0.42)
        height = 5.7 + min(1.5, (series - 1) * 0.22)
    elif chart_type in MATRIX_TYPES:
        width = 6.6 + min(7.0, secondary * 0.34)
        height = 5.4 + min(8.0, categories * 0.30)
    elif chart_type == "pair":
        side = 5.8 + min(7.0, categories * 1.10)
        width = height = side
    elif chart_type == "joint":
        width = height = 8.2
    elif chart_type in {"pie", "donut"}:
        width, height = 8.8 + min(1.2, categories * 0.08), 7.2
    elif chart_type in RELATIONAL_TYPES | DISTRIBUTION_TYPES | REGRESSION_TYPES | {"area"}:
        width = 9.4 + min(2.4, math.log2(categories + 1) * 0.32)
        height = 5.8 + min(1.2, (series - 1) * 0.18)
    else:
        width, height = 10.4, 6.2

    preset = str(request.get("figure_size") or "auto").strip().lower()
    if preset == "compact":
        width, height = width * 0.84, height * 0.84
    elif preset == "wide":
        width, height = width * 1.18, height * 0.92
    elif preset == "tall":
        width, height = width * 0.88, height * 1.20
    elif preset == "square":
        side = math.sqrt(width * height)
        width = height = side
    return _bounded_figure_size(width, height)


def _bound_figure_aspect(fig: Figure) -> None:
    """Normalize Seaborn figure-level plots that choose their own dimensions."""
    width, height = fig.get_size_inches()
    bounded = _bounded_figure_size(float(width), float(height))
    if not math.isclose(float(width), bounded[0]) or not math.isclose(float(height), bounded[1]):
        fig.set_size_inches(*bounded, forward=True)


def _estimator(request: dict[str, Any]) -> str | Callable[[np.ndarray], float]:
    value = str(request.get("estimator") or "mean").strip().lower()
    return {"mean": "mean", "median": "median", "sum": "sum", "min": "min", "max": "max", "count": len}.get(
        value, "mean"
    )


def _errorbar(request: dict[str, Any]) -> object:
    value = str(request.get("errorbar") or "none").strip().lower()
    if value in {"", "none", "off", "false"}:
        return None
    if value in {"sd", "se"}:
        return value
    return {"ci90": ("ci", 90), "ci95": ("ci", 95), "pi90": ("pi", 90), "pi95": ("pi", 95)}.get(value)


def _category_order(data: ChartData, request: dict[str, Any]) -> list[object] | None:
    order_raw = request.get("category_order")
    if isinstance(order_raw, list) and order_raw and data.x:
        available = set(data.frame[data.x].dropna())
        return [value for value in order_raw if value in available]
    if not data.x or not data.y:
        return None
    sort = str(request.get("sort") or "none").strip().lower()
    if sort not in {"ascending", "descending"}:
        return data.frame[data.x].dropna().drop_duplicates().tolist()
    grouped = data.frame.groupby(data.x, observed=True)[data.y].mean().sort_values(ascending=sort == "ascending")
    return grouped.index.tolist()


def _format_value(value: float, request: dict[str, Any], *, include_unit: bool = True) -> str:
    fmt = str(request.get("value_format") or "auto").strip().lower()
    decimals = _bounded_int(request.get("decimals"), 1, 0, 4)
    unit = _text(request.get("unit"), limit=40)
    factor = 100.0 if fmt == "percent" and str(request.get("percent_scale") or "ratio") == "ratio" else 1.0
    number = value * factor
    if fmt == "integer":
        rendered = f"{number:,.0f}"
    elif fmt == "decimal":
        rendered = f"{number:,.{decimals}f}"
    elif fmt == "percent":
        rendered = f"{number:,.{decimals}f}%"
    elif fmt == "currency_cny":
        rendered = f"¥{number:,.{decimals}f}"
    elif fmt == "currency_usd":
        rendered = f"${number:,.{decimals}f}"
    elif fmt == "currency_eur":
        rendered = f"€{number:,.{decimals}f}"
    elif fmt == "compact":
        magnitude = abs(number)
        if magnitude >= 1_000_000_000:
            rendered = f"{number / 1_000_000_000:.{decimals}f}B"
        elif magnitude >= 1_000_000:
            rendered = f"{number / 1_000_000:.{decimals}f}M"
        elif magnitude >= 1_000:
            rendered = f"{number / 1_000:.{decimals}f}K"
        else:
            rendered = f"{number:,.{decimals}f}"
    else:
        rendered = f"{number:,.{decimals}f}" if not float(number).is_integer() else f"{number:,.0f}"
    if "." in rendered and not rendered.endswith("%"):
        rendered = rendered.rstrip("0").rstrip(".")
    return f"{rendered}{unit}" if include_unit and unit and not rendered.endswith(unit) else rendered


def _formatter(request: dict[str, Any]) -> FuncFormatter:
    return FuncFormatter(lambda value, _position: _format_value(float(value), request, include_unit=False))


def _apply_limits_and_scale(
    ax: Axes,
    request: dict[str, Any],
    *,
    horizontal: bool = False,
    numeric_x: bool = False,
) -> None:
    x_scale = str(request.get("x_scale") or "linear").lower()
    y_scale = str(request.get("y_scale") or "linear").lower()
    x_min, x_max = _optional_number(request.get("x_min")), _optional_number(request.get("x_max"))
    y_min, y_max = _optional_number(request.get("y_min")), _optional_number(request.get("y_max"))
    if (horizontal or numeric_x) and x_scale in {"linear", "log", "symlog"}:
        ax.set_xscale(x_scale)
    if not horizontal and y_scale in {"linear", "log", "symlog"}:
        ax.set_yscale(y_scale)
    if (horizontal or numeric_x) and (x_min is not None or x_max is not None):
        current = ax.get_xlim()
        ax.set_xlim(x_min if x_min is not None else current[0], x_max if x_max is not None else current[1])
    if not horizontal and (y_min is not None or y_max is not None):
        current = ax.get_ylim()
        ax.set_ylim(y_min if y_min is not None else current[0], y_max if y_max is not None else current[1])
    (ax.xaxis if horizontal else ax.yaxis).set_major_formatter(_formatter(request))


def _apply_grid(ax: Axes, request: dict[str, Any], *, numeric_axis: str = "y") -> None:
    value = str(request.get("grid") or "auto").strip().lower()
    if value == "none":
        ax.grid(False)
    elif value == "both":
        ax.grid(True, axis="both")
    elif value in {"x", "y"}:
        ax.grid(True, axis=value)
        ax.grid(False, axis="y" if value == "x" else "x")
    else:
        ax.grid(True, axis=numeric_axis)
        ax.grid(False, axis="y" if numeric_axis == "x" else "x")


def _apply_legend(ax: Axes, request: dict[str, Any], series_count: int) -> None:
    mode = str(request.get("legend") or "auto").strip().lower()
    legend = ax.get_legend()
    show = mode == "show" or (mode == "auto" and series_count > 1)
    if not show:
        if legend is not None:
            legend.remove()
        return
    if legend is None:
        return
    position = str(request.get("legend_position") or "top").strip().lower()
    if position == "right":
        legend.set_bbox_to_anchor((1.02, 0.5))
        legend._loc = 6
    elif position == "bottom":
        legend.set_bbox_to_anchor((0.5, -0.13))
        legend._loc = 9
        legend.set_ncols(min(series_count, 4))
    elif position == "best":
        legend._loc = 0
    else:
        legend.set_bbox_to_anchor((0, 1.02))
        legend._loc = 3
        legend.set_ncols(min(series_count, 4))


def _reference_lines(ax: Axes, request: dict[str, Any]) -> None:
    raw = request.get("reference_lines")
    if not isinstance(raw, list):
        return
    for item in raw[:6]:
        if not isinstance(item, dict):
            continue
        value = _number(item.get("value"))
        if value is None:
            continue
        axis, style = str(item.get("axis") or "y").lower(), str(item.get("style") or "--")
        if style not in {"-", "--", ":", "-."}:
            style = "--"
        color, label = str(item.get("color") or "#B45309"), _text(item.get("label"), limit=80)
        line = (
            ax.axvline(value, color=color, linestyle=style, linewidth=1.5, alpha=0.9)
            if axis == "x"
            else ax.axhline(value, color=color, linestyle=style, linewidth=1.5, alpha=0.9)
        )
        if label:
            line.set_label(label)


def _titles(fig: Figure, ax: Axes | None, request: dict[str, Any]) -> tuple[float, float]:
    title = _text(request.get("title"), limit=160) or "Chart"
    subtitle, note = _text(request.get("subtitle"), limit=500), _text(request.get("note"), limit=500)
    fig.suptitle(title, x=0.04, y=0.965, ha="left", va="top", fontsize=17, fontweight="bold", color="#243447")
    top = 0.93
    if subtitle:
        wrapped = "\n".join(textwrap.wrap(subtitle, width=95)[:3])
        fig.text(0.04, 0.895, wrapped, ha="left", va="top", fontsize=10.5, color="#667085")
        top = 0.88 - wrapped.count("\n") * 0.025
    bottom = 0.08
    if note:
        wrapped_note = "\n".join(textwrap.wrap(note, width=115)[:3])
        fig.text(0.04, 0.025, f"注：{wrapped_note}", ha="left", va="bottom", fontsize=9.5, color="#737B86")
        bottom = 0.11 + wrapped_note.count("\n") * 0.02
    if ax is not None:
        ax.set_title("")
    return top, bottom


def _finish_axes(
    ax: Axes,
    request: dict[str, Any],
    series_count: int,
    *,
    horizontal: bool = False,
    numeric_x: bool = False,
) -> None:
    x_label = _text(request.get("x_label"), limit=100)
    y_label = _text(request.get("y_label"), limit=100)
    unit = _text(request.get("unit"), limit=40)
    if unit:
        if horizontal and x_label and unit not in x_label:
            x_label = f"{x_label}（{unit}）"
        elif not horizontal and y_label and unit not in y_label:
            y_label = f"{y_label}（{unit}）"
    ax.set_xlabel(x_label)
    ax.set_ylabel(y_label)
    rotation = _bounded_int(request.get("x_tick_rotation"), 0, -90, 90)
    if rotation:
        plt.setp(ax.get_xticklabels(), rotation=rotation, ha="right")
    _apply_limits_and_scale(ax, request, horizontal=horizontal, numeric_x=numeric_x)
    _apply_grid(ax, request, numeric_axis="x" if horizontal else "y")
    _apply_legend(ax, request, series_count)
    _reference_lines(ax, request)
    for spine in ax.spines.values():
        spine.set_visible(True)
        spine.set_color("#AAB2BC")
        spine.set_linewidth(0.8)


def _bar_labels(ax: Axes, request: dict[str, Any], *, horizontal: bool) -> None:
    if not bool(request.get("show_values", False)):
        return
    for container in ax.containers:
        if not hasattr(container, "datavalues"):
            continue
        labels = [
            "" if value is None or not math.isfinite(float(value)) else _format_value(float(value), request)
            for value in container.datavalues
        ]
        ax.bar_label(container, labels=labels, padding=5, fontsize=9.5, color="#344054")
    if horizontal:
        low, high = ax.get_xlim()
        ax.set_xlim(low, high + (high - low) * 0.12)
    else:
        low, high = ax.get_ylim()
        ax.set_ylim(low, high + (high - low) * 0.10)


def _highlight_bars(ax: Axes, request: dict[str, Any], order: list[object] | None) -> None:
    label = _text(request.get("highlight_label"), limit=100)
    if not label or not order:
        return
    try:
        index = [str(item) for item in order].index(label)
    except ValueError:
        return
    patches = [patch for patch in ax.patches if patch.get_width() or patch.get_height()]
    if index < len(patches):
        patches[index].set_facecolor(HIGHLIGHT_COLOR)
        patches[index].set_edgecolor("#1F7A52")
        patches[index].set_linewidth(1.2)


def _render_bar(data: ChartData, request: dict[str, Any], *, horizontal: bool = False) -> tuple[Figure, Axes]:
    if not data.x or not data.y:
        raise ChartError("bar charts require category and numeric fields")
    order = _category_order(data, request)
    fig, ax = plt.subplots(
        figsize=_size(
            request,
            "horizontal_bar" if horizontal else "bar",
            len(order or data.labels),
            len(data.series_names),
        )
    )
    palette = _palette(request, max(len(data.series_names), 1))
    kwargs: dict[str, Any] = {
        "data": data.frame,
        "hue": data.hue,
        "order": order,
        "estimator": _estimator(request),
        "errorbar": _errorbar(request),
        "n_boot": _bounded_int(request.get("n_boot"), 1000, 100, 10_000),
        "seed": _bounded_int(request.get("seed"), 0, 0, 2**31 - 1),
        "dodge": bool(request.get("dodge", True)),
        "gap": _bounded_float(request.get("gap"), 0.0, 0.0, 0.8),
        "width": _bounded_float(request.get("bar_width"), 0.8, 0.1, 1.0),
        "saturation": _bounded_float(request.get("saturation"), 0.92, 0.0, 1.0),
        "ax": ax,
    }
    if data.hue:
        kwargs["palette"] = palette
    else:
        kwargs["color"] = palette[0]
    if horizontal:
        kwargs.update(x=data.y, y=data.x)
    else:
        kwargs.update(x=data.x, y=data.y)
    sns.barplot(**kwargs)
    _highlight_bars(ax, request, order)
    _bar_labels(ax, request, horizontal=horizontal)
    _finish_axes(ax, request, len(data.series_names), horizontal=horizontal)
    return fig, ax


def _render_horizontal_bar(data: ChartData, request: dict[str, Any]) -> tuple[Figure, Axes]:
    if not data.x or not data.y:
        raise ChartError("horizontal_bar requires category and numeric fields")
    order = _category_order(data, request) or data.frame[data.x].dropna().drop_duplicates().tolist()
    grouped = data.frame.pivot_table(
        index=data.x,
        columns=data.hue if data.hue else None,
        values=data.y,
        aggfunc=_estimator(request),
    ).reindex(order)
    if isinstance(grouped, pd.Series):
        grouped = grouped.to_frame(data.series_names[0] if data.series_names else "Value")
    grouped = grouped.dropna(how="all")
    fig, ax = plt.subplots(figsize=_size(request, "horizontal_bar", len(grouped), len(grouped.columns)))
    y = np.arange(len(grouped))
    columns = list(grouped.columns)
    colors = _palette(request, max(len(columns), 1))
    total_height = _bounded_float(request.get("bar_width"), 0.72, 0.1, 0.95)
    bar_height = total_height / max(len(columns), 1)
    containers = []
    for series_index, column in enumerate(columns):
        offset = (series_index - (len(columns) - 1) / 2) * bar_height
        values = grouped[column].to_numpy(dtype=float)
        color = colors[series_index]
        bars = ax.barh(
            y + offset,
            values,
            height=bar_height * 0.88,
            color=color,
            edgecolor="#FFFFFF",
            linewidth=0.9,
            label=str(column),
        )
        containers.append(bars)
    ax.set_yticks(y, [str(value) for value in grouped.index])
    ax.invert_yaxis()
    highlight = _text(request.get("highlight_label"), limit=100)
    if highlight and highlight in {str(value) for value in grouped.index}:
        highlight_index = [str(value) for value in grouped.index].index(highlight)
        for bars in containers:
            bars[highlight_index].set_facecolor(HIGHLIGHT_COLOR)
            bars[highlight_index].set_edgecolor("#1F7A52")
            bars[highlight_index].set_linewidth(1.2)
    _bar_labels(ax, request, horizontal=True)
    _finish_axes(ax, request, len(columns), horizontal=True)
    return fig, ax


def _render_stacked(data: ChartData, request: dict[str, Any]) -> tuple[Figure, Axes]:
    if data.wide is None:
        if not data.x or not data.y:
            raise ChartError("stacked_bar requires category and numeric fields")
        pivot = data.frame.pivot_table(index=data.x, columns=data.hue, values=data.y, aggfunc=_estimator(request))
    else:
        pivot = data.wide
    sort = str(request.get("sort") or "none").lower()
    if sort in {"ascending", "descending"}:
        pivot = pivot.loc[pivot.sum(axis=1).sort_values(ascending=sort == "ascending").index]
    fig, ax = plt.subplots(figsize=_size(request, "stacked_bar", len(pivot), len(pivot.columns)))
    horizontal = bool(request.get("orientation") == "horizontal")
    pivot.plot(
        kind="barh" if horizontal else "bar",
        stacked=True,
        ax=ax,
        color=_palette(request, len(pivot.columns)),
        width=_bounded_float(request.get("bar_width"), 0.78, 0.1, 1.0),
        edgecolor="#FFFFFF",
        linewidth=0.8,
    )
    _bar_labels(ax, request, horizontal=horizontal)
    _finish_axes(ax, request, len(pivot.columns), horizontal=horizontal)
    return fig, ax


def _render_line_or_scatter(data: ChartData, request: dict[str, Any], chart_type: str) -> tuple[Figure, Axes]:
    if not data.x or not data.y:
        raise ChartError(f"{chart_type} requires x and y fields")
    fig, ax = plt.subplots(figsize=_size(request, chart_type, len(data.labels), len(data.series_names)))
    common = {
        "data": data.frame,
        "x": data.x,
        "y": data.y,
        "hue": data.hue,
        "style": data.style,
        "palette": _palette(request, max(len(data.series_names), 2)),
        "alpha": _bounded_float(request.get("alpha"), 0.9, 0.05, 1.0),
        "ax": ax,
    }
    if chart_type == "scatter":
        sns.scatterplot(
            **common,
            size=data.size,
            sizes=(
                _bounded_float(request.get("marker_size_min"), 35, 5, 500),
                _bounded_float(request.get("marker_size_max"), 180, 10, 1_000),
            ),
            marker=str(request.get("marker") or "o")[:3],
            linewidth=_bounded_float(request.get("line_width"), 0.8, 0, 5),
        )
    else:
        sns.lineplot(
            **common,
            estimator=_estimator(request),
            errorbar=_errorbar(request),
            n_boot=_bounded_int(request.get("n_boot"), 1000, 100, 10_000),
            seed=_bounded_int(request.get("seed"), 0, 0, 2**31 - 1),
            sort=bool(request.get("sort_values", True)),
            markers=bool(request.get("markers", True)),
            dashes=bool(request.get("dashes", True)),
            linewidth=_bounded_float(request.get("line_width"), 2.3, 0.3, 8),
        )
    numeric_x = pd.api.types.is_numeric_dtype(data.frame[data.x])
    _finish_axes(ax, request, max(len(data.series_names), 1), numeric_x=numeric_x)
    return fig, ax


def _render_distribution(data: ChartData, request: dict[str, Any], chart_type: str) -> tuple[Figure, Axes]:
    if not data.x:
        raise ChartError(f"{chart_type} requires a numeric x field")
    fig, ax = plt.subplots(figsize=_size(request, chart_type, len(data.frame), len(data.series_names)))
    common = {
        "data": data.frame,
        "x": data.x,
        "hue": data.hue,
        "weights": data.weight,
        "palette": _palette(request, max(len(data.series_names), 2)),
        "legend": str(request.get("legend") or "auto") != "hide",
        "ax": ax,
    }
    if chart_type == "hist":
        bins: str | int = request.get("bins", "auto")
        if bins != "auto":
            bins = _bounded_int(bins, 20, 1, 200)
        binrange = request.get("bin_range")
        binrange_value = None
        if isinstance(binrange, list) and len(binrange) == 2:
            low, high = _number(binrange[0]), _number(binrange[1])
            if low is not None and high is not None and low < high:
                binrange_value = (low, high)
        sns.histplot(
            **common,
            stat=str(request.get("stat") or "count"),
            bins=bins,
            binwidth=_optional_number(request.get("bin_width")),
            binrange=binrange_value,
            discrete=request.get("discrete"),
            cumulative=bool(request.get("cumulative", False)),
            common_bins=bool(request.get("common_bins", True)),
            common_norm=bool(request.get("common_norm", True)),
            multiple=str(request.get("multiple") or "layer"),
            element=str(request.get("element") or "bars"),
            fill=bool(request.get("fill", True)),
            shrink=_bounded_float(request.get("shrink"), 1.0, 0.05, 1.0),
            kde=bool(request.get("kde_overlay", False)),
            line_kws={"linewidth": _bounded_float(request.get("line_width"), 1.5, 0.2, 6)},
        )
    elif chart_type == "kde":
        clip = request.get("clip")
        clip_value = None
        if isinstance(clip, list) and len(clip) == 2:
            clip_value = (_optional_number(clip[0]), _optional_number(clip[1]))
        sns.kdeplot(
            **common,
            fill=bool(request.get("fill", True)),
            multiple=str(request.get("multiple") or "layer"),
            common_norm=bool(request.get("common_norm", True)),
            common_grid=bool(request.get("common_grid", False)),
            cumulative=bool(request.get("cumulative", False)),
            bw_adjust=_bounded_float(request.get("bw_adjust"), 1.0, 0.05, 20),
            cut=_bounded_float(request.get("cut"), 3.0, 0, 20),
            clip=clip_value,
            gridsize=_bounded_int(request.get("gridsize"), 200, 50, 1_000),
            thresh=_bounded_float(request.get("threshold"), 0.05, 0, 1),
            levels=_bounded_int(request.get("levels"), 10, 2, 50),
            warn_singular=False,
            linewidth=_bounded_float(request.get("line_width"), 1.8, 0.2, 8),
        )
    elif chart_type == "ecdf":
        sns.ecdfplot(
            **common,
            stat=str(request.get("stat") or "proportion"),
            complementary=bool(request.get("complementary", False)),
            linewidth=_bounded_float(request.get("line_width"), 2.0, 0.2, 8),
        )
    else:
        common.pop("weights", None)
        sns.rugplot(
            **common,
            height=_bounded_float(request.get("rug_height"), 0.035, 0.005, 0.2),
            expand_margins=bool(request.get("expand_margins", True)),
            linewidth=_bounded_float(request.get("line_width"), 1.0, 0.2, 5),
        )
    _finish_axes(ax, request, max(len(data.series_names), 1), horizontal=True)
    return fig, ax


def _render_categorical(data: ChartData, request: dict[str, Any], chart_type: str) -> tuple[Figure, Axes]:
    if not data.x:
        raise ChartError(f"{chart_type} requires an x/category field")
    fig, ax = plt.subplots(figsize=_size(request, chart_type, len(data.labels), len(data.series_names)))
    order = _category_order(data, request)
    plot_hue = data.hue or data.x
    hue_count = data.frame[plot_hue].nunique(dropna=True) if plot_hue else max(len(data.series_names), 1)
    common: dict[str, Any] = {
        "data": data.frame,
        "x": data.x,
        "hue": plot_hue,
        "order": order,
        "palette": _palette(request, max(int(hue_count), 1)),
        "legend": (str(request.get("legend") or "auto") != "hide") if data.hue else False,
        "ax": ax,
    }
    if chart_type != "count":
        if not data.y:
            raise ChartError(f"{chart_type} requires a numeric y field")
        common["y"] = data.y
    dodge = bool(request.get("dodge", True)) if data.hue else False
    if chart_type == "count":
        sns.countplot(
            **common,
            dodge=dodge,
            stat=str(request.get("stat") or "count"),
            width=_bounded_float(request.get("bar_width"), 0.8, 0.1, 1.0),
            gap=_bounded_float(request.get("gap"), 0.0, 0, 0.8),
            fill=bool(request.get("fill", True)),
        )
    elif chart_type == "point":
        sns.pointplot(
            **common,
            estimator=_estimator(request),
            errorbar=_errorbar(request),
            n_boot=_bounded_int(request.get("n_boot"), 1000, 100, 10_000),
            seed=_bounded_int(request.get("seed"), 0, 0, 2**31 - 1),
            markers=str(request.get("marker") or "o")[:3],
            linestyles=str(request.get("line_style") or "-")[:3],
            capsize=_bounded_float(request.get("capsize"), 0.0, 0, 1.0),
            dodge=_bounded_float(request.get("point_dodge"), 0.0, 0, 1.0),
        )
    elif chart_type == "box":
        box_common = {**common, "hue": data.hue, "legend": bool(data.hue)}
        box_common.pop("palette", None)
        if data.hue:
            box_common["palette"] = _palette(request, max(len(data.series_names), 2))
        else:
            box_common["color"] = _palette(request, 1)[0]
        sns.boxplot(
            **box_common,
            dodge=dodge,
            width=_bounded_float(request.get("width"), 0.8, 0.1, 1.0),
            gap=_bounded_float(request.get("gap"), 0.0, 0, 0.8),
            fill=bool(request.get("fill", True)),
            whis=_bounded_float(request.get("whis"), 1.5, 0.1, 10),
            showfliers=bool(request.get("show_fliers", True)),
            fliersize=_bounded_float(request.get("marker_size"), 4.0, 1, 20),
            linewidth=_bounded_float(request.get("line_width"), 1.0, 0.2, 6),
        )
    elif chart_type == "violin":
        sns.violinplot(
            **common,
            dodge=dodge,
            inner=str(request.get("inner") or "box"),
            split=bool(request.get("split", False)),
            density_norm=str(request.get("density_norm") or "area"),
            common_norm=bool(request.get("common_norm", False)),
            bw_adjust=_bounded_float(request.get("bw_adjust"), 1.0, 0.05, 20),
            cut=_bounded_float(request.get("cut"), 2.0, 0, 20),
            gridsize=_bounded_int(request.get("gridsize"), 100, 50, 1_000),
            width=_bounded_float(request.get("width"), 0.8, 0.1, 1.0),
            gap=_bounded_float(request.get("gap"), 0.0, 0, 0.8),
            fill=bool(request.get("fill", True)),
            linewidth=_bounded_float(request.get("line_width"), 1.0, 0.2, 6),
        )
    elif chart_type == "boxen":
        sns.boxenplot(
            **common,
            dodge=dodge,
            width_method=str(request.get("width_method") or "exponential"),
            k_depth=str(request.get("k_depth") or "tukey"),
            outlier_prop=_bounded_float(request.get("outlier_prop"), 0.007, 0, 0.5),
            trust_alpha=_bounded_float(request.get("trust_alpha"), 0.05, 0.001, 0.5),
            showfliers=bool(request.get("show_fliers", True)),
            width=_bounded_float(request.get("width"), 0.8, 0.1, 1.0),
            gap=_bounded_float(request.get("gap"), 0.0, 0, 0.8),
            fill=bool(request.get("fill", True)),
            linewidth=_bounded_float(request.get("line_width"), 1.0, 0.2, 6),
        )
    elif chart_type == "strip":
        sns.stripplot(
            **common,
            dodge=dodge,
            jitter=request.get("jitter", True),
            size=_bounded_float(request.get("marker_size"), 5.0, 1, 30),
            marker=str(request.get("marker") or "o")[:3],
            linewidth=_bounded_float(request.get("line_width"), 0.3, 0, 5),
            edgecolor=str(request.get("edge_color") or "auto"),
            alpha=_bounded_float(request.get("alpha"), 0.8, 0.05, 1.0),
        )
    else:
        sns.swarmplot(
            **common,
            dodge=dodge,
            size=_bounded_float(request.get("marker_size"), 5.0, 1, 30),
            marker=str(request.get("marker") or "o")[:3],
            linewidth=_bounded_float(request.get("line_width"), 0.3, 0, 5),
            edgecolor=str(request.get("edge_color") or "auto"),
            warn_thresh=_bounded_float(request.get("warn_thresh"), 0.05, 0, 1),
            alpha=_bounded_float(request.get("alpha"), 0.8, 0.05, 1.0),
        )
    _finish_axes(ax, request, max(len(data.series_names), 1))
    if chart_type in {"count", "point"}:
        _bar_labels(ax, request, horizontal=False)
    return fig, ax


def _render_regression(data: ChartData, request: dict[str, Any], chart_type: str) -> tuple[Figure, Axes]:
    if not data.x or not data.y:
        raise ChartError(f"{chart_type} requires numeric x and y fields")
    fig, ax = plt.subplots(figsize=_size(request, chart_type, len(data.frame), len(data.series_names)))
    groups = [(None, data.frame)] if not data.hue else list(data.frame.groupby(data.hue, observed=True))
    colors = _palette(request, len(groups))
    for index, (name, frame) in enumerate(groups):
        common = {
            "data": frame,
            "x": data.x,
            "y": data.y,
            "color": colors[index],
            "label": str(name) if name is not None else None,
            "ax": ax,
            "order": _bounded_int(request.get("regression_order"), 1, 1, 5),
            "robust": bool(request.get("robust", False)),
            "lowess": bool(request.get("lowess", False)),
            "dropna": True,
            "scatter_kws": {
                "alpha": _bounded_float(request.get("alpha"), 0.72, 0.05, 1.0),
                "s": _bounded_float(request.get("marker_size"), 45, 5, 500),
            },
            "line_kws": {"linewidth": _bounded_float(request.get("line_width"), 2.2, 0.2, 8)},
        }
        if chart_type == "regression":
            sns.regplot(
                **common,
                truncate=bool(request.get("truncate", False)),
                logistic=bool(request.get("logistic", False)),
                logx=bool(request.get("log_x", False)),
                ci=_bounded_int(request.get("ci"), 95, 0, 100) or None,
                n_boot=_bounded_int(request.get("n_boot"), 1000, 100, 10_000),
                seed=_bounded_int(request.get("seed"), 0, 0, 2**31 - 1),
                x_jitter=_optional_number(request.get("x_jitter")),
                y_jitter=_optional_number(request.get("y_jitter")),
                scatter=bool(request.get("scatter", True)),
                fit_reg=bool(request.get("fit_reg", True)),
            )
        else:
            common.pop("label", None)
            sns.residplot(**common)
    _finish_axes(ax, request, len(groups), numeric_x=True)
    return fig, ax


def _matrix_from_data(data: ChartData) -> pd.DataFrame:
    if data.matrix is not None:
        return data.matrix
    if data.wide is not None:
        return data.wide
    raise ChartError("matrix charts require matrix data or numeric series")


def _render_matrix(data: ChartData, request: dict[str, Any], chart_type: str) -> tuple[Figure, Axes | None]:
    matrix = _matrix_from_data(data)
    cmap = str(request.get("cmap") or "Blues")
    allowed = {"Blues", "Greens", "viridis", "mako", "rocket", "flare", "crest", "vlag", "coolwarm", "RdYlGn"}
    if cmap not in allowed:
        cmap = "Blues"
    common = {
        "cmap": cmap,
        "center": _optional_number(request.get("center")),
        "robust": bool(request.get("robust", False)),
        "vmin": _optional_number(request.get("vmin")),
        "vmax": _optional_number(request.get("vmax")),
    }
    if chart_type == "clustermap":
        grid = sns.clustermap(
            matrix,
            **common,
            method=str(request.get("cluster_method") or "average"),
            metric=str(request.get("cluster_metric") or "euclidean"),
            row_cluster=bool(request.get("row_cluster", True)),
            col_cluster=bool(request.get("col_cluster", True)),
            z_score=request.get("z_score"),
            standard_scale=request.get("standard_scale"),
            linewidths=_bounded_float(request.get("linewidths"), 0.3, 0, 5),
            linecolor=str(request.get("line_color") or "#FFFFFF"),
            figsize=_size(request, chart_type, len(matrix.index), 1, len(matrix.columns)),
            cbar_pos=(0.02, 0.8, 0.03, 0.16) if bool(request.get("colorbar", True)) else None,
        )
        return grid.figure, None
    fig, ax = plt.subplots(figsize=_size(request, chart_type, len(matrix.index), 1, len(matrix.columns)))
    sns.heatmap(
        matrix,
        **common,
        annot=bool(request.get("annotate", False)),
        fmt=str(request.get("annotation_format") or ".2g")[:8],
        square=bool(request.get("square", False)),
        linewidths=_bounded_float(request.get("linewidths"), 0.5, 0, 5),
        linecolor=str(request.get("line_color") or "#FFFFFF"),
        cbar=bool(request.get("colorbar", True)),
        ax=ax,
    )
    return fig, ax


def _render_pie(data: ChartData, request: dict[str, Any], *, donut: bool) -> tuple[Figure, Axes]:
    if data.wide is None or data.wide.empty:
        raise ChartError("pie charts require labels and at least one numeric series")
    values = data.wide.iloc[:, 0].fillna(0).astype(float)
    if (values < 0).any() or values.sum() <= 0:
        raise ChartError("pie charts require positive values")
    fig, ax = plt.subplots(figsize=_size(request, "pie", len(values)))
    wedges, _, _ = ax.pie(
        values,
        labels=None,
        colors=_palette(request, len(values)),
        startangle=_bounded_float(request.get("start_angle"), 90, -360, 360),
        counterclock=bool(request.get("counterclock", False)),
        autopct="%1.1f%%" if bool(request.get("show_values", True)) else None,
        pctdistance=0.75,
        wedgeprops={"width": 0.45 if donut else 1.0, "edgecolor": "white", "linewidth": 1.5},
        textprops={"color": "#344054", "fontsize": 10},
    )
    if str(request.get("legend") or "auto") != "hide":
        ax.legend(
            wedges,
            [
                f"{label}  {_format_value(float(value), request)}"
                for label, value in zip(values.index, values, strict=True)
            ],
            loc="center left",
            bbox_to_anchor=(1.0, 0.5),
            frameon=False,
        )
    ax.set_aspect("equal")
    ax.grid(False)
    return fig, ax


def _render_area(data: ChartData, request: dict[str, Any]) -> tuple[Figure, Axes]:
    if data.wide is None:
        raise ChartError("area charts require labels and numeric series")
    fig, ax = plt.subplots(figsize=_size(request, "area", len(data.wide), len(data.wide.columns)))
    values = [data.wide[column].fillna(0).to_numpy(dtype=float) for column in data.wide.columns]
    x, colors = np.arange(len(data.wide)), _palette(request, len(values))
    if bool(request.get("stack", len(values) > 1)):
        ax.stackplot(
            x,
            values,
            labels=data.wide.columns,
            colors=colors,
            alpha=_bounded_float(request.get("alpha"), 0.62, 0.05, 1.0),
        )
    else:
        for index, (column, series) in enumerate(zip(data.wide.columns, values, strict=True)):
            ax.fill_between(x, series, alpha=_bounded_float(request.get("alpha"), 0.28, 0.05, 1.0), color=colors[index])
            ax.plot(
                x,
                series,
                label=column,
                color=colors[index],
                linewidth=_bounded_float(request.get("line_width"), 2.2, 0.2, 8),
            )
    ax.set_xticks(x, data.wide.index)
    _finish_axes(ax, request, len(values))
    return fig, ax


def _render_waterfall(data: ChartData, request: dict[str, Any]) -> tuple[Figure, Axes]:
    if data.wide is None or data.wide.empty:
        raise ChartError("waterfall requires labels and one numeric series")
    increments = data.wide.iloc[:, 0].fillna(0).to_numpy(dtype=float)
    labels = list(data.wide.index)
    starts = np.concatenate(([0.0], np.cumsum(increments[:-1])))
    colors = ["#3B6FB6" if value >= 0 else "#C65A5A" for value in increments]
    fig, ax = plt.subplots(figsize=_size(request, "waterfall", len(labels)))
    bars = ax.bar(labels, increments, bottom=starts, color=colors, edgecolor="#FFFFFF", linewidth=0.8)
    if bool(request.get("show_values", True)):
        for bar, value in zip(bars, increments, strict=True):
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                bar.get_y() + bar.get_height(),
                _format_value(value, request),
                ha="center",
                va="bottom" if value >= 0 else "top",
                fontsize=9.5,
            )
    _finish_axes(ax, request, 1)
    return fig, ax


def _render_lollipop(data: ChartData, request: dict[str, Any]) -> tuple[Figure, Axes]:
    if data.wide is None or data.wide.empty:
        raise ChartError("lollipop requires labels and one numeric series")
    values = data.wide.iloc[:, 0].fillna(0).to_numpy(dtype=float)
    labels = list(data.wide.index)
    sort = str(request.get("sort") or "none")
    order = (
        np.argsort(values)
        if sort == "ascending"
        else np.argsort(-values)
        if sort == "descending"
        else np.arange(len(values))
    )
    values, labels = values[order], [labels[index] for index in order]
    fig, ax = plt.subplots(figsize=_size(request, "lollipop", len(labels)))
    y = np.arange(len(labels))
    color = _palette(request, 1)[0]
    ax.hlines(y, 0, values, color="#AAB7C4", linewidth=2)
    ax.scatter(values, y, color=color, s=_bounded_float(request.get("marker_size"), 80, 10, 500), zorder=3)
    ax.set_yticks(y, labels)
    if bool(request.get("show_values", True)):
        for x, y_value in zip(values, y, strict=True):
            ax.annotate(
                _format_value(float(x), request),
                (x, y_value),
                xytext=(7, 0),
                textcoords="offset points",
                va="center",
                fontsize=9.5,
            )
    _finish_axes(ax, request, 1, horizontal=True)
    return fig, ax


def _render_faceted(data: ChartData, request: dict[str, Any], chart_type: str) -> tuple[Figure, None] | None:
    row, col = _field(request, "facet_row", data.frame), _field(request, "facet_col", data.frame)
    if not row and not col:
        return None
    common = {
        "data": data.frame,
        "row": row,
        "col": col,
        "col_wrap": (_bounded_int(request.get("col_wrap"), 0, 0, 8) or None) if col and not row else None,
        "height": _bounded_float(request.get("facet_height"), 3.6, 2, 8),
        "aspect": _bounded_float(request.get("facet_aspect"), 1.25, 0.5, 3),
        "facet_kws": {"sharex": bool(request.get("share_x", True)), "sharey": bool(request.get("share_y", True))},
    }
    if chart_type in RELATIONAL_TYPES:
        grid = sns.relplot(
            **common,
            kind=chart_type,
            x=data.x,
            y=data.y,
            hue=data.hue,
            style=data.style,
            size=data.size,
            palette=_palette(request, max(len(data.series_names), 2)),
        )
    elif chart_type in DISTRIBUTION_TYPES - {"rug"}:
        grid = sns.displot(
            **common, kind=chart_type, x=data.x, hue=data.hue, palette=_palette(request, max(len(data.series_names), 2))
        )
    elif chart_type in CATEGORICAL_TYPES | {"bar"}:
        grid = sns.catplot(
            **common,
            kind=chart_type,
            x=data.x,
            y=data.y,
            hue=data.hue,
            palette=_palette(request, max(len(data.series_names), 2)),
        )
    elif chart_type == "regression":
        grid = sns.lmplot(
            **common,
            x=data.x,
            y=data.y,
            hue=data.hue,
            palette=_palette(request, max(len(data.series_names), 2)),
            order=_bounded_int(request.get("regression_order"), 1, 1, 5),
            robust=bool(request.get("robust", False)),
            lowess=bool(request.get("lowess", False)),
            logistic=bool(request.get("logistic", False)),
            ci=_bounded_int(request.get("ci"), 95, 0, 100) or None,
            n_boot=_bounded_int(request.get("n_boot"), 1000, 100, 10_000),
            seed=_bounded_int(request.get("seed"), 0, 0, 2**31 - 1),
            x_jitter=_optional_number(request.get("x_jitter")),
            y_jitter=_optional_number(request.get("y_jitter")),
            truncate=bool(request.get("truncate", False)),
            scatter=bool(request.get("scatter", True)),
            fit_reg=bool(request.get("fit_reg", True)),
        )
    else:
        raise ChartError(f"faceting is not supported for {chart_type}")
    return grid.figure, None


def _render_joint(data: ChartData, request: dict[str, Any]) -> tuple[Figure, None]:
    if not data.x or not data.y:
        raise ChartError("joint requires x and y fields")
    kind = str(request.get("joint_kind") or "scatter").lower()
    if kind not in {"scatter", "kde", "hist", "hex", "reg", "resid"}:
        kind = "scatter"
    grid = sns.jointplot(
        data=data.frame,
        x=data.x,
        y=data.y,
        hue=data.hue if kind not in {"hex", "reg", "resid"} else None,
        kind=kind,
        palette=_palette(request, max(len(data.series_names), 2)),
        height=_bounded_float(request.get("joint_height"), 7.5, 4, 14),
        ratio=_bounded_int(request.get("joint_ratio"), 5, 1, 12),
        space=_bounded_float(request.get("joint_space"), 0.2, 0, 1),
        marginal_ticks=bool(request.get("marginal_ticks", False)),
    )
    return grid.figure, None


def _render_pair(data: ChartData, request: dict[str, Any]) -> tuple[Figure, None]:
    variables_raw = request.get("variables")
    variables = [str(value) for value in variables_raw] if isinstance(variables_raw, list) else []
    if not variables:
        variables = data.frame.select_dtypes(include=[np.number]).columns.tolist()[:8]
    variables = [value for value in variables if value in data.frame.columns][:8]
    if len(variables) < 2:
        raise ChartError("pair requires at least two numeric variables")
    kind = str(request.get("pair_kind") or "scatter").lower()
    diag_kind = str(request.get("diag_kind") or "auto").lower()
    if kind not in {"scatter", "kde", "hist", "reg"}:
        kind = "scatter"
    if diag_kind not in {"auto", "hist", "kde"}:
        diag_kind = "auto"
    grid = sns.pairplot(
        data=data.frame,
        vars=variables,
        hue=data.hue,
        kind=kind,
        diag_kind=diag_kind,
        corner=bool(request.get("corner", False)),
        dropna=True,
        palette=_palette(request, max(len(data.series_names), 2)),
        height=_bounded_float(request.get("facet_height"), 2.8, 1.8, 6),
        aspect=_bounded_float(request.get("facet_aspect"), 1.0, 0.5, 2),
    )
    return grid.figure, None


def _apply_presets(request: dict[str, Any]) -> dict[str, Any]:
    """Compile the small business-facing interface into plotting parameters."""
    resolved = dict(request)

    style_name = str(request.get("style_preset") or "hidalgo").strip().lower()
    for key, value in STYLE_PRESETS.get(style_name, STYLE_PRESETS["hidalgo"]).items():
        resolved.setdefault(key, value)

    palette_name = str(request.get("palette_preset") or "auto").strip().lower()
    palette = PALETTE_PRESETS.get(palette_name)
    if palette:
        resolved["palette"] = palette

    layout_name = str(request.get("layout_preset") or "auto").strip().lower()
    resolved.setdefault("figure_size", LAYOUT_PRESETS.get(layout_name, "auto"))

    detail_name = str(request.get("detail_preset") or "balanced").strip().lower()
    for key, value in DETAIL_PRESETS.get(detail_name, DETAIL_PRESETS["balanced"]).items():
        resolved.setdefault(key, value)

    aggregation_name = str(request.get("aggregation_preset") or "mean").strip().lower()
    resolved.setdefault("estimator", AGGREGATION_PRESETS.get(aggregation_name, "mean"))

    uncertainty_name = str(request.get("uncertainty_preset") or "none").strip().lower()
    resolved.setdefault("errorbar", UNCERTAINTY_PRESETS.get(uncertainty_name, "none"))

    distribution_name = str(request.get("distribution_preset") or "count").strip().lower()
    for key, value in DISTRIBUTION_PRESETS.get(distribution_name, DISTRIBUTION_PRESETS["count"]).items():
        resolved.setdefault(key, value)

    regression_name = str(request.get("regression_preset") or "linear").strip().lower()
    for key, value in REGRESSION_PRESETS.get(regression_name, REGRESSION_PRESETS["linear"]).items():
        resolved.setdefault(key, value)

    categorical_name = str(request.get("categorical_preset") or "summary").strip().lower()
    for key, value in CATEGORICAL_PRESETS.get(categorical_name, CATEGORICAL_PRESETS["summary"]).items():
        resolved.setdefault(key, value)

    matrix_name = str(request.get("matrix_preset") or "standard").strip().lower()
    matrix_values = MATRIX_PRESETS.get(matrix_name, MATRIX_PRESETS["standard"])
    for key, value in matrix_values.items():
        resolved.setdefault(key, value)
    if matrix_name in {"clustered", "row_normalized", "column_normalized"} and str(
        request.get("chart_type") or "auto"
    ).lower() in {"auto", "heatmap"}:
        resolved["chart_type"] = "clustermap"

    annotation = str(request.get("annotation_preset") or "auto").strip().lower()
    if annotation == "none":
        resolved["show_values"] = False
    elif annotation == "values":
        resolved["show_values"] = True
    elif annotation == "percent":
        resolved["show_values"] = True
        resolved.setdefault("value_format", "percent")
    elif annotation == "compact":
        resolved["show_values"] = True
        resolved.setdefault("value_format", "compact")

    return resolved


def _render(request: dict[str, Any]) -> tuple[Figure, Axes | None, str, int, int]:
    request = _apply_presets(request)
    chart_type = str(request.get("chart_type") or "auto").strip().lower()
    if chart_type not in CHART_TYPES:
        raise ChartError(f"unsupported chart type: {chart_type}")
    if chart_type == "auto":
        chart_type = "line" if isinstance(request.get("labels"), list) and len(request["labels"]) > 12 else "bar"
    _setup_theme(request)
    data = _resolve_data(request, chart_type)
    faceted = _render_faceted(data, request, chart_type)
    if faceted is not None:
        fig, ax = faceted
    elif chart_type == "bar":
        fig, ax = _render_bar(data, request)
    elif chart_type == "horizontal_bar":
        fig, ax = _render_horizontal_bar(data, request)
    elif chart_type == "stacked_bar":
        fig, ax = _render_stacked(data, request)
    elif chart_type in RELATIONAL_TYPES:
        fig, ax = _render_line_or_scatter(data, request, chart_type)
    elif chart_type in DISTRIBUTION_TYPES:
        fig, ax = _render_distribution(data, request, chart_type)
    elif chart_type in CATEGORICAL_TYPES:
        fig, ax = _render_categorical(data, request, chart_type)
    elif chart_type in REGRESSION_TYPES:
        fig, ax = _render_regression(data, request, chart_type)
    elif chart_type in MATRIX_TYPES:
        fig, ax = _render_matrix(data, request, chart_type)
    elif chart_type == "area":
        fig, ax = _render_area(data, request)
    elif chart_type in {"pie", "donut"}:
        fig, ax = _render_pie(data, request, donut=chart_type == "donut")
    elif chart_type == "waterfall":
        fig, ax = _render_waterfall(data, request)
    elif chart_type == "lollipop":
        fig, ax = _render_lollipop(data, request)
    elif chart_type == "joint":
        fig, ax = _render_joint(data, request)
    elif chart_type == "pair":
        fig, ax = _render_pair(data, request)
    else:
        raise ChartError(f"unsupported chart type: {chart_type}")
    _bound_figure_aspect(fig)
    return fig, ax, chart_type, len(data.labels), len(data.series_names)


def render(request: dict[str, Any]) -> dict[str, Any]:
    workspace = _workspace()
    fig: Figure | None = None
    try:
        fig, ax, chart_type, label_count, series_count = _render(request)
        top, bottom = _titles(fig, ax, request)
        try:
            fig.tight_layout(rect=(0.025, bottom, 0.98, top))
        except (RuntimeError, ValueError):
            pass
        day = time.strftime("%Y-%m-%d", time.gmtime())
        output_dir = (workspace / "charts" / day).resolve(strict=False)
        if not output_dir.is_relative_to(workspace):
            raise ChartError("invalid chart output directory")
        output_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
        target = output_dir / f"chart-{stamp}-{uuid.uuid4().hex[:8]}.png"
        dpi = {"standard": 160, "high": 220, "print": 300}.get(str(request.get("quality") or "standard").lower(), 160)
        with tempfile.NamedTemporaryFile("wb", dir=output_dir, prefix=".chart-", delete=False) as handle:
            staged = Path(handle.name)
        try:
            fig.savefig(
                staged,
                format="png",
                dpi=dpi,
                facecolor=fig.get_facecolor(),
                edgecolor="none",
                bbox_inches=None,
            )
            if staged.stat().st_size > 10_000_000:
                raise ChartError("rendered chart exceeds the 10 MB delivery limit")
            with staged.open("rb") as handle:
                if handle.read(8) != b"\x89PNG\r\n\x1a\n":
                    raise ChartError("chart renderer did not return PNG data")
            os.chmod(staged, 0o600)
            os.replace(staged, target)
        finally:
            if staged.exists():
                staged.unlink()
        return {
            "success": True,
            "chart": str(target.relative_to(workspace)),
            "chart_type": chart_type,
            "labels": label_count,
            "series": series_count,
            "size_bytes": target.stat().st_size,
        }
    finally:
        if fig is not None:
            plt.close(fig)
        plt.close("all")


def main() -> int:
    try:
        raw = os.read(0, MAX_REQUEST_BYTES + 1)
        if len(raw) > MAX_REQUEST_BYTES:
            raise ChartError("chart request exceeds the size limit")
        request = json.loads(raw.decode("utf-8"))
        if not isinstance(request, dict):
            raise ChartError("chart request must be a JSON object")
        print(json.dumps(render(request), ensure_ascii=False))
        return 0
    except Exception as exc:  # noqa: BLE001
        print(
            json.dumps(
                {"success": False, "error": str(exc)[:1000], "error_type": type(exc).__name__}, ensure_ascii=False
            )
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
