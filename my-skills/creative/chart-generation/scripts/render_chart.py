#!/usr/bin/env python3
"""Render a constrained ChartRequest to PNG with Vega-Lite.

The helper accepts JSON on stdin, embeds all data inline, performs no network
access, and writes only below ``HERMES_CHART_WORKSPACE``.
"""

from __future__ import annotations

import json
import math
import os
import tempfile
import time
import uuid
from pathlib import Path
from typing import Any

import vl_convert as vlc

MAX_REQUEST_BYTES = 256 * 1024
MAX_LABELS = 240
MAX_SERIES = 10
MAX_POINTS = 2_000
MAX_TEXT_CHARS = 240
CHART_TYPES = {
    "auto",
    "line",
    "bar",
    "stacked_bar",
    "horizontal_bar",
    "pie",
    "area",
    "scatter",
}
PALETTE = [
    "#2563EB",
    "#7C3AED",
    "#0891B2",
    "#059669",
    "#D97706",
    "#DC2626",
    "#DB2777",
    "#4F46E5",
    "#65A30D",
    "#EA580C",
]
FONT = "Arial Unicode MS"


class ChartError(RuntimeError):
    """A bounded chart input or rendering failure."""


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
    text = text.strip("()").replace(",", "")
    text = text.lstrip("¥￥$€£")
    text = text.removesuffix("%")
    try:
        number = float(text)
    except ValueError:
        return None
    if negative:
        number = -number
    return number if math.isfinite(number) else None


def _normalize(request: dict[str, Any]) -> tuple[list[str], list[dict[str, Any]], list[float] | None]:
    labels_raw = request.get("labels")
    series_raw = request.get("series")
    if not isinstance(labels_raw, list) or not labels_raw:
        raise ChartError("labels must be a non-empty list")
    if len(labels_raw) > MAX_LABELS:
        raise ChartError(f"labels exceed the {MAX_LABELS} item limit")
    if not isinstance(series_raw, list) or not series_raw:
        raise ChartError("series must be a non-empty list")
    if len(series_raw) > MAX_SERIES:
        raise ChartError(f"series exceed the {MAX_SERIES} item limit")

    labels = [_text(value, limit=100) or str(index + 1) for index, value in enumerate(labels_raw)]
    series: list[dict[str, Any]] = []
    total_points = 0
    for index, item in enumerate(series_raw, start=1):
        if not isinstance(item, dict) or not isinstance(item.get("values"), list):
            raise ChartError("each series requires a name and values list")
        if len(item["values"]) != len(labels):
            raise ChartError("every series must have the same number of values as labels")
        values = [_number(value) for value in item["values"]]
        if not any(value is not None for value in values):
            raise ChartError(f"series {index} has no numeric values")
        total_points += len(values)
        if total_points > MAX_POINTS:
            raise ChartError(f"chart exceeds the {MAX_POINTS} point limit")
        series.append(
            {
                "name": _text(item.get("name"), limit=100) or f"Series {index}",
                "values": values,
            }
        )

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
    return labels, series, x_values


def _values(labels: list[str], series: list[dict[str, Any]], x_values: list[float] | None) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for series_index, item in enumerate(series):
        for order, (label, value) in enumerate(zip(labels, item["values"], strict=True)):
            if value is None:
                continue
            row = {
                "category": label,
                "series": item["name"],
                "value": value,
                "order": order,
                "series_order": series_index,
            }
            if x_values is not None:
                row["x"] = x_values[order]
            rows.append(row)
    return rows


def _base_config() -> dict[str, Any]:
    return {
        "background": "#FFFFFF",
        "font": FONT,
        "view": {"stroke": None},
        "axis": {
            "labelFont": FONT,
            "titleFont": FONT,
            "labelColor": "#475569",
            "titleColor": "#334155",
            "gridColor": "#E2E8F0",
            "domainColor": "#94A3B8",
            "tickColor": "#CBD5E1",
            "labelFontSize": 13,
            "titleFontSize": 15,
        },
        "legend": {
            "labelFont": FONT,
            "titleFont": FONT,
            "labelFontSize": 13,
            "titleFontSize": 14,
            "orient": "top",
        },
        "title": {
            "font": FONT,
            "subtitleFont": FONT,
            "fontSize": 24,
            "subtitleFontSize": 14,
            "color": "#0F172A",
            "subtitleColor": "#64748B",
            "anchor": "start",
            "offset": 24,
        },
        "range": {"category": PALETTE},
    }


def _encoding(
    labels: list[str],
    chart_type: str,
    x_label: str,
    y_label: str,
) -> dict[str, Any]:
    category = {
        "field": "category",
        "type": "ordinal",
        "sort": labels,
        "title": x_label or None,
        "axis": {"labelAngle": -25 if len(labels) > 8 else 0, "labelLimit": 140},
    }
    value = {
        "field": "value",
        "type": "quantitative",
        "title": y_label or None,
        "scale": {"zero": chart_type not in {"line", "scatter"}},
    }
    color = {
        "field": "series",
        "type": "nominal",
        "title": None,
        "sort": {"field": "series_order", "op": "min"},
        "scale": {"range": PALETTE},
    }
    tooltip = [
        {"field": "category", "type": "nominal", "title": x_label or "Category"},
        {"field": "series", "type": "nominal", "title": "Series"},
        {"field": "value", "type": "quantitative", "title": y_label or "Value", "format": ",.4~g"},
    ]
    if chart_type == "horizontal_bar":
        return {
            "y": {**category, "title": x_label or None, "axis": {"labelLimit": 180}},
            "x": {**value, "title": y_label or None},
            "color": color,
            "yOffset": {"field": "series"},
            "tooltip": tooltip,
        }
    return {
        "x": category,
        "y": value,
        "color": color,
        "tooltip": tooltip,
    }


def _spec(request: dict[str, Any]) -> tuple[dict[str, Any], str, int, int]:
    labels, series, x_values = _normalize(request)
    chart_type = str(request.get("chart_type") or "auto").strip().lower()
    if chart_type not in CHART_TYPES:
        raise ChartError(f"unsupported chart type: {chart_type}")
    if chart_type == "auto":
        chart_type = "line" if len(labels) > 12 else "bar"
    if chart_type == "pie":
        series = series[:1]
    if chart_type == "horizontal_bar" and len(series) > 4:
        raise ChartError("horizontal_bar supports at most four series")

    rows = _values(labels, series, x_values)
    if not rows:
        raise ChartError("chart contains no numeric points")
    title = _text(request.get("title"), limit=160) or "Chart"
    subtitle = _text(request.get("subtitle"), limit=240)
    x_label = _text(request.get("x_label"), limit=100)
    y_label = _text(request.get("y_label"), limit=100)
    show_values = bool(request.get("show_values", False))

    spec: dict[str, Any] = {
        "$schema": "https://vega.github.io/schema/vega-lite/v6.json",
        "width": 1100,
        "height": 620,
        "padding": {"left": 16, "right": 24, "top": 12, "bottom": 20},
        "title": {"text": title, **({"subtitle": subtitle} if subtitle else {})},
        "data": {"values": rows},
        "config": _base_config(),
    }

    if chart_type == "pie":
        spec.update(
            {
                "mark": {"type": "arc", "innerRadius": 70, "outerRadius": 230, "stroke": "#FFFFFF", "strokeWidth": 2},
                "encoding": {
                    "theta": {"field": "value", "type": "quantitative", "stack": True},
                    "color": {
                        "field": "category",
                        "type": "nominal",
                        "title": None,
                        "sort": labels,
                        "scale": {"range": PALETTE},
                    },
                    "tooltip": [
                        {"field": "category", "type": "nominal", "title": x_label or "Category"},
                        {"field": "value", "type": "quantitative", "title": y_label or "Value", "format": ",.4~g"},
                    ],
                },
            }
        )
    elif chart_type == "scatter":
        x_encoding: dict[str, Any]
        if x_values is not None:
            x_encoding = {"field": "x", "type": "quantitative", "title": x_label or None}
        else:
            x_encoding = {
                "field": "order",
                "type": "quantitative",
                "title": x_label or None,
                "axis": {"labelExpr": "datum.value + 1"},
            }
        spec.update(
            {
                "mark": {"type": "point", "filled": True, "size": 110, "opacity": 0.82},
                "encoding": {
                    "x": x_encoding,
                    "y": {"field": "value", "type": "quantitative", "title": y_label or None, "scale": {"zero": False}},
                    "color": {"field": "series", "type": "nominal", "title": None, "scale": {"range": PALETTE}},
                    "tooltip": [
                        {"field": "category", "type": "nominal", "title": "Label"},
                        {"field": "series", "type": "nominal", "title": "Series"},
                        {"field": "value", "type": "quantitative", "title": y_label or "Value", "format": ",.4~g"},
                    ],
                },
            }
        )
    else:
        encoding = _encoding(labels, chart_type, x_label, y_label)
        if chart_type == "bar":
            encoding["xOffset"] = {"field": "series"}
            mark: dict[str, Any] = {"type": "bar", "cornerRadiusTopLeft": 3, "cornerRadiusTopRight": 3}
        elif chart_type == "stacked_bar":
            encoding["y"]["stack"] = "zero"
            mark = {"type": "bar"}
        elif chart_type == "horizontal_bar":
            mark = {"type": "bar", "cornerRadiusEnd": 3}
        elif chart_type == "area":
            mark = {"type": "area", "opacity": 0.52, "line": True, "point": True}
        else:
            mark = {"type": "line", "point": {"filled": True, "size": 70}, "strokeWidth": 3}
        if show_values and chart_type in {"bar", "stacked_bar", "horizontal_bar"}:
            text_encoding = {**encoding, "text": {"field": "value", "type": "quantitative", "format": ",.4~g"}}
            spec["layer"] = [
                {"mark": mark, "encoding": encoding},
                {
                    "mark": {
                        "type": "text",
                        "dy": -8 if chart_type != "horizontal_bar" else 0,
                        "dx": 6,
                        "font": FONT,
                        "fontSize": 12,
                    },
                    "encoding": text_encoding,
                },
            ]
        else:
            spec["mark"] = mark
            spec["encoding"] = encoding
    return spec, chart_type, len(labels), len(series)


def render(request: dict[str, Any]) -> dict[str, Any]:
    workspace = _workspace()
    spec, chart_type, label_count, series_count = _spec(request)
    try:
        png = vlc.vegalite_to_png(vl_spec=spec, scale=1.5)
    except Exception as exc:  # noqa: BLE001 - normalize renderer errors
        raise ChartError(f"chart renderer failed: {exc}") from None
    if not isinstance(png, bytes) or not png.startswith(b"\x89PNG\r\n\x1a\n"):
        raise ChartError("chart renderer did not return PNG data")
    if len(png) > 10_000_000:
        raise ChartError("rendered chart exceeds the 10 MB delivery limit")

    day = time.strftime("%Y-%m-%d", time.gmtime())
    output_dir = (workspace / "charts" / day).resolve(strict=False)
    if not output_dir.is_relative_to(workspace):
        raise ChartError("invalid chart output directory")
    output_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    target = output_dir / f"chart-{stamp}-{uuid.uuid4().hex[:8]}.png"
    with tempfile.NamedTemporaryFile("wb", dir=output_dir, prefix=".chart-", delete=False) as handle:
        handle.write(png)
        staged = Path(handle.name)
    try:
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
        "size_bytes": len(png),
    }


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
    except Exception as exc:  # noqa: BLE001 - CLI boundary emits one bounded JSON error
        print(
            json.dumps(
                {"success": False, "error": str(exc)[:1000], "error_type": type(exc).__name__},
                ensure_ascii=False,
            )
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
