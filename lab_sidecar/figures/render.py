from __future__ import annotations

from pathlib import Path
from typing import Iterable

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import pandas as pd

from lab_sidecar.figures.specs import FigureSpec, PALETTE, friendly_label


def render_figure(df: pd.DataFrame, spec: FigureSpec, task_path: Path) -> tuple[Path, Path]:
    png_path = task_path / spec.output.png
    svg_path = task_path / spec.output.svg
    png_path.parent.mkdir(parents=True, exist_ok=True)
    svg_path.parent.mkdir(parents=True, exist_ok=True)

    if spec.chart_type == "line":
        _render_line(df, spec, png_path, svg_path)
    elif spec.chart_type == "bar":
        _render_bar(df, spec, png_path, svg_path)
    else:
        raise ValueError(f"unsupported chart type: {spec.chart_type}")
    return png_path, svg_path


def _render_line(df: pd.DataFrame, spec: FigureSpec, png_path: Path, svg_path: Path) -> None:
    fig, ax = plt.subplots(figsize=(10, 6), dpi=200)
    try:
        ax.set_facecolor("white")
        fig.patch.set_facecolor("white")

        if spec.group_by:
            plotted = 0
            for index, (group_value, group_df) in enumerate(_stable_groups(df, spec.group_by)):
                series = _line_points(group_df, spec.x, spec.y)
                if len(series) < 2:
                    continue
                label = _legend_label(group_value, spec.group_by)
                ax.plot(
                    series[spec.x],
                    series[spec.y],
                    marker="o",
                    linewidth=2,
                    label=label,
                    color=PALETTE[index % len(PALETTE)],
                )
                plotted += 1
            if plotted == 0:
                raise ValueError(f"no plottable groups for '{spec.y}'")
            if plotted > 1:
                ax.legend(loc="best", frameon=False)
        else:
            series = _line_points(df, spec.x, spec.y)
            if len(series) < 2:
                raise ValueError(f"fewer than 2 plottable points for '{spec.y}'")
            ax.plot(series[spec.x], series[spec.y], marker="o", linewidth=2, color=PALETTE[0])

        ax.set_title(spec.title)
        ax.set_xlabel(_axis_label(spec, spec.x))
        ax.set_ylabel(_axis_label(spec, spec.y))
        ax.grid(True, color="#E5E5E5", linewidth=0.8)
        fig.tight_layout()
        _save(fig, png_path, svg_path)
    finally:
        plt.close(fig)


def _render_bar(df: pd.DataFrame, spec: FigureSpec, png_path: Path, svg_path: Path) -> None:
    fig, ax = plt.subplots(figsize=(10, 6), dpi=200)
    try:
        ax.set_facecolor("white")
        fig.patch.set_facecolor("white")
        data = df[[spec.x, spec.y]].copy()
        data[spec.y] = pd.to_numeric(data[spec.y], errors="coerce")
        data = data.dropna(subset=[spec.y])
        if data.empty:
            raise ValueError(f"no numeric values for '{spec.y}'")

        data[spec.x] = data[spec.x].fillna("(missing)").astype(str)
        grouped = data.groupby(spec.x, sort=True, dropna=False)[spec.y].mean().reset_index()
        if grouped.empty:
            raise ValueError(f"no categories for '{spec.x}'")

        colors = [PALETTE[index % len(PALETTE)] for index in range(len(grouped))]
        ax.bar(grouped[spec.x], grouped[spec.y], color=colors)
        ax.set_title(spec.title)
        ax.set_xlabel(_axis_label(spec, spec.x))
        ax.set_ylabel(_axis_label(spec, spec.y))
        ax.grid(True, axis="y", color="#E5E5E5", linewidth=0.8)
        ax.set_axisbelow(True)
        if len(grouped) > 4:
            ax.tick_params(axis="x", labelrotation=30)
            for label in ax.get_xticklabels():
                label.set_ha("right")
        fig.tight_layout()
        _save(fig, png_path, svg_path)
    finally:
        plt.close(fig)


def _line_points(df: pd.DataFrame, x: str, y: str) -> pd.DataFrame:
    data = df[[x, y]].copy()
    data[x] = pd.to_numeric(data[x], errors="coerce")
    data[y] = pd.to_numeric(data[y], errors="coerce")
    return data.dropna(subset=[x, y]).sort_values(x)


def _stable_groups(df: pd.DataFrame, group_by: str) -> Iterable[tuple[object, pd.DataFrame]]:
    values = sorted(df[group_by].fillna("(missing)").astype(str).unique())
    for value in values:
        yield value, df[df[group_by].fillna("(missing)").astype(str) == value]


def _save(fig, png_path: Path, svg_path: Path) -> None:
    fig.savefig(png_path, dpi=200, bbox_inches="tight", facecolor="white")
    fig.savefig(svg_path, bbox_inches="tight", facecolor="white")


def _axis_label(spec: FigureSpec, value: str) -> str:
    label = friendly_label(value)
    unit = spec.units.get(value)
    if unit and f"({unit})" not in label:
        return f"{label} ({unit})"
    return label


def _legend_label(value: object, group_by: str) -> str:
    text = str(value)
    if group_by == "source_file":
        return Path(text).stem
    return text
