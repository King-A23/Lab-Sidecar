from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd


PALETTE = ["#4E79A7", "#F28E2B", "#59A14F", "#E15759", "#76B7B2", "#9C755F"]

PROCESS_METRIC_PRIORITY = [
    "accuracy",
    "val_accuracy",
    "test_accuracy",
    "acc",
    "throughput_rps",
    "loss",
    "train_loss",
    "val_loss",
    "f1",
    "f1_score",
    "macro_f1",
    "precision",
    "macro_precision",
    "recall",
    "macro_recall",
]
BAR_CATEGORY_PRIORITY = [
    "model",
    "method",
    "algorithm",
    "variant",
    "class",
    "label",
    "category",
    "dataset",
    "DATA_TIMER",
    "BACKLOG_FACTOR",
    "Stage",
    "Scenario",
    "source_file",
]
BAR_METRIC_PRIORITY = [
    "accuracy",
    "final_accuracy",
    "val_accuracy",
    "test_accuracy",
    "acc",
    "error_rate",
    "f1",
    "f1_score",
    "macro_f1",
    "throughput_rps",
    "latency",
    "latency_ms",
    "runtime",
    "runtime_ms",
    "time",
    "time_ms",
    "memory",
    "memory_mb",
    "peak_memory_mb",
    "score",
    "Score",
    "AvgUtil",
    "AUtil",
    "BUtil",
    "DataTimeoutPerMin",
    "BadCrcTotal",
    "WallSeconds",
]
LINE_GROUP_PRIORITY = ["split", "config_id", "service", "model", "method", "experiment", "source_file"]
TIME_AXIS_PRIORITY = ["timestamp", "time", "date", "datetime"]
BOX_CATEGORY_PRIORITY = ["method", "model", "algorithm", "variant", "config_id", "dataset", "source_file"]
BOX_METRIC_PRIORITY = [
    "accuracy",
    "final_accuracy",
    "val_accuracy",
    "test_accuracy",
    "acc",
    "f1",
    "f1_score",
    "macro_f1",
    "score",
]

METRIC_ALIASES = {
    "accuracy": ["accuracy", "val_accuracy", "test_accuracy", "acc"],
    "loss": ["loss", "train_loss", "val_loss"],
    "f1": ["f1", "f1_score", "macro_f1"],
    "precision": ["precision", "macro_precision"],
    "recall": ["recall", "macro_recall"],
    "runtime": ["runtime", "runtime_ms", "latency", "latency_ms", "time", "time_ms"],
    "latency": ["latency", "latency_ms", "runtime", "runtime_ms", "time", "time_ms"],
    "throughput": ["throughput", "throughput_rps", "rps", "requests_per_second"],
    "throughput_rps": ["throughput_rps", "throughput", "rps", "requests_per_second"],
    "memory": ["memory", "memory_mb", "peak_memory_mb"],
    "score": ["score", "Score"],
    "error_rate": ["error_rate", "error", "errors"],
    "utilization": ["util", "utilization", "AvgUtil", "AUtil", "BUtil"],
    "timeout": ["timeout", "DataTimeoutPerMin", "DataTimeoutTotal", "AckTimeoutTotal"],
    "errors": ["error", "errors", "BadCrcTotal"],
    "duration": ["duration", "DurationSec", "WallSeconds"],
}

FRIENDLY_LABELS = {
    "acc": "Accuracy",
    "accuracy": "Accuracy",
    "val_accuracy": "Validation Accuracy",
    "test_accuracy": "Test Accuracy",
    "loss": "Loss",
    "train_loss": "Training Loss",
    "val_loss": "Validation Loss",
    "f1": "F1",
    "f1_score": "F1 Score",
    "macro_f1": "Macro F1",
    "precision": "Precision",
    "macro_precision": "Macro Precision",
    "recall": "Recall",
    "macro_recall": "Macro Recall",
    "latency": "Latency",
    "latency_ms": "Latency (ms)",
    "throughput_rps": "Throughput (rps)",
    "runtime": "Runtime",
    "runtime_ms": "Runtime (ms)",
    "time": "Time",
    "time_ms": "Time (ms)",
    "memory": "Memory",
    "memory_mb": "Memory (MB)",
    "peak_memory_mb": "Peak Memory (MB)",
    "Score": "Score",
    "AvgUtil": "Average Utilization",
    "AUtil": "A Utilization",
    "BUtil": "B Utilization",
    "DataTimeoutPerMin": "Data Timeouts / Min",
    "DataTimeoutTotal": "Data Timeouts",
    "AckTimeoutTotal": "ACK Timeouts",
    "BadCrcTotal": "Bad CRC Count",
    "error_rate": "Error Rate",
    "DurationSec": "Duration (s)",
    "WallSeconds": "Wall Time (s)",
    "DATA_TIMER": "DATA_TIMER",
    "BACKLOG_FACTOR": "BACKLOG_FACTOR",
    "Stage": "Stage",
    "Scenario": "Scenario",
    "epoch": "Epoch",
    "step": "Step",
    "timestamp": "Timestamp",
    "time": "Time",
    "date": "Date",
    "datetime": "Datetime",
    "split": "Split",
    "config_id": "Config",
    "service": "Service",
    "class": "Class",
    "model": "Model",
    "method": "Method",
    "algorithm": "Algorithm",
    "variant": "Variant",
    "source_file": "Source File",
}

MAX_AUTO_LINE_CHARTS = 2
MAX_COMPARISON_LINES = 8
MAX_BAR_CATEGORIES = 12
MAX_BAR_GROUPS = 8
MAX_BOX_CATEGORIES = 12

SUPPORTED_CHART_TYPES = {"line", "bar", "box"}


class FigureSpecValidationError(ValueError):
    pass


@dataclass
class FigureOutput:
    png: str
    svg: str


@dataclass
class FigureSpec:
    figure_id: str
    chart_type: str
    title: str
    x: str
    y: str
    output: FigureOutput
    group_by: str | None = None
    aggregation: str | None = None
    source: str = "metrics/normalized_metrics.csv"
    units: dict[str, str] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class FigurePlan:
    specs: list[FigureSpec]
    warnings: list[str] = field(default_factory=list)
    skipped_candidates: list[dict[str, str]] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    unsupported_chart_diagnostics: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class ExplicitFigureSpecBundle:
    specs: list[FigureSpec]
    warnings: list[str] = field(default_factory=list)
    skipped_candidates: list[dict[str, str]] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def build_auto_figure_plan(
    df: pd.DataFrame,
    units: dict[str, str] | None = None,
    groups: dict[str, str] | None = None,
) -> FigurePlan:
    warnings: list[str] = []
    skipped: list[dict[str, str]] = []
    if df.empty:
        reason = "normalized_metrics.csv is empty."
        return FigurePlan(specs=[], warnings=[reason], skipped_candidates=[_skip("auto", reason)])

    x_column = _process_axis(df)
    if x_column:
        specs = _build_line_specs(df, x_column, warnings, skipped, units or {}, groups or {})
        if specs:
            return FigurePlan(specs=specs, warnings=warnings, skipped_candidates=skipped)

    if _seed_distribution_candidate(df):
        specs = _build_box_specs(df, warnings, skipped, units or {})
        if specs:
            return FigurePlan(specs=specs, warnings=warnings, skipped_candidates=skipped)

    specs = _build_bar_specs(df, warnings, skipped, units or {}, groups or {})
    return FigurePlan(specs=specs, warnings=warnings, skipped_candidates=skipped)


def build_explicit_figure_plan(
    df: pd.DataFrame,
    spec: FigureSpec | list[FigureSpec],
    units: dict[str, str] | None = None,
    warnings: list[str] | None = None,
    skipped_candidates: list[dict[str, str]] | None = None,
    errors: list[str] | None = None,
) -> FigurePlan:
    plan = FigurePlan(
        specs=[],
        warnings=list(warnings or []),
        skipped_candidates=list(skipped_candidates or []),
        errors=list(errors or []),
    )
    specs = spec if isinstance(spec, list) else [spec]
    for item in specs:
        item_plan = _build_single_explicit_figure_plan(df, item, units=units)
        plan.specs.extend(item_plan.specs)
        plan.warnings.extend(item_plan.warnings)
        plan.skipped_candidates.extend(item_plan.skipped_candidates)
        plan.errors.extend(item_plan.errors)
        plan.unsupported_chart_diagnostics.extend(item_plan.unsupported_chart_diagnostics)
    return plan


def _build_single_explicit_figure_plan(
    df: pd.DataFrame,
    spec: FigureSpec,
    units: dict[str, str] | None = None,
) -> FigurePlan:
    errors: list[str] = []
    skipped: list[dict[str, str]] = []
    unsupported_chart_diagnostics: list[dict[str, Any]] = []

    if spec.chart_type not in SUPPORTED_CHART_TYPES:
        reason = (
            f"Requested chart_type '{spec.chart_type}' is unsupported by deterministic figures; "
            f"supported types are {', '.join(sorted(SUPPORTED_CHART_TYPES))}."
        )
        errors.append(reason)
        skipped.append(
            _skip(
                spec.figure_id,
                reason,
                chart_type=spec.chart_type,
                x=spec.x,
                y=spec.y,
                group_by=spec.group_by,
            )
        )
        unsupported_chart_diagnostics.append(
            _unsupported_chart_diagnostic(
                spec,
                available_fields=list(df.columns),
                reason=reason,
            )
        )
        return FigurePlan(
            specs=[],
            skipped_candidates=skipped,
            errors=errors,
            unsupported_chart_diagnostics=unsupported_chart_diagnostics,
        )

    missing = [field for field in _required_metric_fields(spec) if field not in df.columns]
    if missing:
        reason = f"Spec references missing metrics field(s): {', '.join(missing)}."
        errors.append(reason)
        skipped.append(_skip(spec.figure_id, reason, chart_type=spec.chart_type))
        return FigurePlan(specs=[], skipped_candidates=skipped, errors=errors)

    reason = _quality_refusal_reason(df, spec)
    if reason:
        errors.append(reason)
        skipped.append(_skip(spec.figure_id, reason, chart_type=spec.chart_type, x=spec.x, y=spec.y))
        return FigurePlan(specs=[], skipped_candidates=skipped, errors=errors)

    spec.units = _spec_units(spec, units or {})
    return FigurePlan(specs=[spec], unsupported_chart_diagnostics=unsupported_chart_diagnostics)


def parse_explicit_specs(data: Any, task_path: Path) -> ExplicitFigureSpecBundle:
    if not isinstance(data, dict):
        raise FigureSpecValidationError("spec must be a YAML object")

    if "figures" not in data:
        return ExplicitFigureSpecBundle(specs=[parse_explicit_spec(data, task_path)])

    raw_figures = data.get("figures")
    if not isinstance(raw_figures, list):
        raise FigureSpecValidationError("field 'figures' must be a list of figure specs")
    if not raw_figures:
        raise FigureSpecValidationError("field 'figures' must contain at least one figure spec")

    specs: list[FigureSpec] = []
    skipped: list[dict[str, str]] = []
    errors: list[str] = []
    for index, item in enumerate(raw_figures, start=1):
        figure_id = _figure_id_for_diagnostic(item, index)
        if not isinstance(item, dict):
            reason = f"Figure spec item {index} must be a YAML object."
            errors.append(reason)
            skipped.append(_skip(figure_id, reason))
            continue
        try:
            specs.append(parse_explicit_spec(item, task_path))
        except FigureSpecValidationError as exc:
            reason = f"Figure spec '{figure_id}' is invalid: {exc}"
            errors.append(reason)
            skipped.append(_skip(figure_id, reason))
    return ExplicitFigureSpecBundle(specs=specs, skipped_candidates=skipped, errors=errors)


def parse_explicit_spec(data: Any, task_path: Path) -> FigureSpec:
    if not isinstance(data, dict):
        raise FigureSpecValidationError("spec must be a YAML object")

    required = ["figure_id", "chart_type", "title", "x", "y"]
    missing = [field for field in required if field not in data]
    if missing:
        raise FigureSpecValidationError(f"missing required spec field(s): {', '.join(missing)}")

    figure_id = _required_string(data, "figure_id")
    chart_type = _required_string(data, "chart_type")
    title = _required_string(data, "title")
    x = _required_string(data, "x")
    y = _required_string(data, "y")
    group_by = data.get("group_by")
    if group_by is not None and not isinstance(group_by, str):
        raise FigureSpecValidationError("field 'group_by' must be a string when provided")

    output = _parse_output(data.get("output"), figure_id, task_path)
    return FigureSpec(
        figure_id=figure_id,
        chart_type=chart_type,
        title=title,
        x=x,
        y=y,
        group_by=group_by,
        aggregation="mean" if chart_type == "bar" else ("distribution" if chart_type == "box" else None),
        output=output,
    )


def friendly_label(value: str) -> str:
    if value in FRIENDLY_LABELS:
        return FRIENDLY_LABELS[value]
    return Path(value).stem.replace("_", " ").title() if value == "source_file" else value.replace("_", " ").title()


def _build_line_specs(
    df: pd.DataFrame,
    x_column: str,
    warnings: list[str],
    skipped: list[dict[str, str]],
    units: dict[str, str],
    groups: dict[str, str],
) -> list[FigureSpec]:
    numeric_columns = _numeric_columns(df)
    metric_columns = [
        column
        for column in _select_priority_columns(PROCESS_METRIC_PRIORITY, numeric_columns)
        if column != x_column
    ]
    if not metric_columns:
        reason = "No numeric metric column was found for a line chart."
        warnings.append(reason)
        skipped.append(_skip("auto_line", reason, chart_type="line", x=x_column))
        return []

    group_by = _configured_group_column(df, groups) or _first_existing_column(df, LINE_GROUP_PRIORITY)
    if group_by:
        group_count = int(df[group_by].nunique(dropna=False))
        if group_count > MAX_COMPARISON_LINES:
            reason = (
                f"Refused line charts because group '{group_by}' has {group_count} values; "
                f"limit is {MAX_COMPARISON_LINES}."
            )
            warnings.append(reason)
            skipped.append(_skip("auto_line", reason, chart_type="line", x=x_column, group_by=group_by))
            return []

    specs: list[FigureSpec] = []
    for y_column in metric_columns:
        figure_id = f"line_{_slug(y_column)}_over_{_slug(x_column)}"
        if len(specs) >= MAX_AUTO_LINE_CHARTS:
            reason = f"Skipped '{y_column}' because auto line chart limit is {MAX_AUTO_LINE_CHARTS}."
            warnings.append(reason)
            skipped.append(_skip(figure_id, reason, chart_type="line", x=x_column, y=y_column, group_by=group_by))
            continue

        valid_rows = _valid_line_rows(df, x_column, y_column)
        if len(valid_rows) < 2:
            reason = f"Skipped '{y_column}' because fewer than 2 numeric points are available."
            warnings.append(reason)
            skipped.append(_skip(figure_id, reason, chart_type="line", x=x_column, y=y_column, group_by=group_by))
            continue

        specs.append(
            FigureSpec(
                figure_id=figure_id,
                chart_type="line",
                title=f"{friendly_label(y_column)} over {friendly_label(x_column)}",
                x=x_column,
                y=y_column,
                group_by=group_by,
                units=_field_units([x_column, y_column, group_by], units),
                output=FigureOutput(
                    png=f"figures/{figure_id}.png",
                    svg=f"figures/{figure_id}.svg",
                ),
            )
        )
    return specs


def _build_bar_specs(
    df: pd.DataFrame,
    warnings: list[str],
    skipped: list[dict[str, str]],
    units: dict[str, str],
    groups: dict[str, str],
) -> list[FigureSpec]:
    category = _first_existing_column(df, BAR_CATEGORY_PRIORITY)
    if not category:
        reason = "No supported category column was found for a bar chart."
        warnings.append(reason)
        skipped.append(_skip("auto_bar", reason, chart_type="bar"))
        return []

    category_count = int(df[category].nunique(dropna=False))
    if category_count > MAX_BAR_CATEGORIES:
        reason = (
            f"Refused bar chart because category '{category}' has {category_count} values; "
            f"limit is {MAX_BAR_CATEGORIES}."
        )
        warnings.append(reason)
        skipped.append(_skip("auto_bar", reason, chart_type="bar", x=category))
        return []

    numeric_columns = _numeric_columns(df)
    metric = _select_priority_column(BAR_METRIC_PRIORITY, numeric_columns)
    if not metric:
        reason = "No supported numeric metric column was found for a bar chart."
        warnings.append(reason)
        skipped.append(_skip("auto_bar", reason, chart_type="bar", x=category))
        return []

    valid_rows = _valid_numeric_rows(df, [metric])
    if valid_rows.empty:
        reason = f"Skipped bar chart because '{metric}' has no numeric values."
        warnings.append(reason)
        skipped.append(_skip("auto_bar", reason, chart_type="bar", x=category, y=metric))
        return []

    group_by = _bar_group_column(df, groups, category)
    if group_by:
        group_count = int(df[group_by].nunique(dropna=False))
        if group_count > MAX_BAR_GROUPS:
            reason = (
                f"Refused grouped bar chart because group '{group_by}' has {group_count} values; "
                f"limit is {MAX_BAR_GROUPS}."
            )
            warnings.append(reason)
            skipped.append(_skip("auto_bar", reason, chart_type="bar", x=category, y=metric, group_by=group_by))
            return []

    figure_id = f"bar_{_slug(metric)}_by_{_slug(category)}"
    return [
        FigureSpec(
            figure_id=figure_id,
            chart_type="bar",
            title=f"Mean {friendly_label(metric)} by {friendly_label(category)}",
            x=category,
            y=metric,
            group_by=group_by,
            aggregation="mean",
            units=_field_units([category, metric, group_by], units),
            output=FigureOutput(
                png=f"figures/{figure_id}.png",
                svg=f"figures/{figure_id}.svg",
            ),
        )
    ]


def _build_box_specs(
    df: pd.DataFrame,
    warnings: list[str],
    skipped: list[dict[str, str]],
    units: dict[str, str],
) -> list[FigureSpec]:
    category = _first_existing_column(df, BOX_CATEGORY_PRIORITY)
    if not category:
        reason = "No supported category column was found for a box chart."
        warnings.append(reason)
        skipped.append(_skip("auto_box", reason, chart_type="box"))
        return []

    category_count = int(df[category].nunique(dropna=False))
    if category_count > MAX_BOX_CATEGORIES:
        reason = (
            f"Refused box chart because category '{category}' has {category_count} values; "
            f"limit is {MAX_BOX_CATEGORIES}."
        )
        warnings.append(reason)
        skipped.append(_skip("auto_box", reason, chart_type="box", x=category))
        return []

    metric = _select_priority_column(BOX_METRIC_PRIORITY, _numeric_columns(df))
    if not metric:
        reason = "No supported numeric metric column was found for a box chart."
        warnings.append(reason)
        skipped.append(_skip("auto_box", reason, chart_type="box", x=category))
        return []

    valid_rows = _valid_numeric_rows(df, [metric])
    if len(valid_rows) < 2:
        reason = f"Skipped box chart because fewer than 2 numeric values are available for '{metric}'."
        warnings.append(reason)
        skipped.append(_skip("auto_box", reason, chart_type="box", x=category, y=metric))
        return []

    figure_id = f"box_{_slug(metric)}_by_{_slug(category)}"
    return [
        FigureSpec(
            figure_id=figure_id,
            chart_type="box",
            title=f"{friendly_label(metric)} distribution by {friendly_label(category)}",
            x=category,
            y=metric,
            aggregation="distribution",
            units=_field_units([category, metric], units),
            output=FigureOutput(
                png=f"figures/{figure_id}.png",
                svg=f"figures/{figure_id}.svg",
            ),
        )
    ]


def _quality_refusal_reason(df: pd.DataFrame, spec: FigureSpec) -> str | None:
    if not _column_is_numeric(df[spec.y]):
        return f"Refused {spec.figure_id} because y field '{spec.y}' is not numeric."

    if spec.chart_type == "line":
        if not _column_is_numeric(df[spec.x]) and not _column_is_datetime(df[spec.x]):
            return f"Refused {spec.figure_id} because x field '{spec.x}' is not numeric or datetime-like."
        if spec.group_by:
            group_count = int(df[spec.group_by].nunique(dropna=False))
            if group_count > MAX_COMPARISON_LINES:
                return (
                    f"Refused {spec.figure_id} because group '{spec.group_by}' has {group_count} values; "
                    f"limit is {MAX_COMPARISON_LINES}."
                )
        valid_rows = _valid_line_rows(df, spec.x, spec.y)
        if len(valid_rows) < 2:
            return f"Refused {spec.figure_id} because fewer than 2 numeric points are available."
        return None

    if spec.chart_type == "box":
        category_count = int(df[spec.x].nunique(dropna=False))
        if category_count > MAX_BOX_CATEGORIES:
            return (
                f"Refused {spec.figure_id} because category '{spec.x}' has {category_count} values; "
                f"limit is {MAX_BOX_CATEGORIES}."
            )
        if len(_valid_numeric_rows(df, [spec.y])) < 2:
            return f"Refused {spec.figure_id} because fewer than 2 numeric values are available."
        return None

    category_count = int(df[spec.x].nunique(dropna=False))
    if category_count > MAX_BAR_CATEGORIES:
        return (
            f"Refused {spec.figure_id} because category '{spec.x}' has {category_count} values; "
            f"limit is {MAX_BAR_CATEGORIES}."
        )
    if _valid_numeric_rows(df, [spec.y]).empty:
        return f"Refused {spec.figure_id} because y field '{spec.y}' has no numeric values."
    if spec.group_by:
        group_count = int(df[spec.group_by].nunique(dropna=False))
        if group_count > MAX_BAR_GROUPS:
            return (
                f"Refused {spec.figure_id} because group '{spec.group_by}' has {group_count} values; "
                f"limit is {MAX_BAR_GROUPS}."
            )
    return None


def _required_metric_fields(spec: FigureSpec) -> list[str]:
    fields = [spec.x, spec.y]
    if spec.group_by:
        fields.append(spec.group_by)
    return fields


def _parse_output(value: Any, figure_id: str, task_path: Path) -> FigureOutput:
    if value is None:
        safe_id = _slug(figure_id)
        return FigureOutput(
            png=f"figures/{safe_id}.png",
            svg=f"figures/{safe_id}.svg",
        )

    output_items: list[str]
    if isinstance(value, list):
        output_items = value
    elif isinstance(value, dict):
        output_items = [value.get("png"), value.get("svg")]
    else:
        raise FigureSpecValidationError("field 'output' must be a list or an object with png/svg")

    if len(output_items) != 2 or not all(isinstance(item, str) for item in output_items):
        raise FigureSpecValidationError("field 'output' must contain one PNG path and one SVG path")

    png_candidates = [item for item in output_items if Path(item).suffix.lower() == ".png"]
    svg_candidates = [item for item in output_items if Path(item).suffix.lower() == ".svg"]
    if len(png_candidates) != 1 or len(svg_candidates) != 1:
        raise FigureSpecValidationError("field 'output' must contain exactly one .png path and one .svg path")

    return FigureOutput(
        png=_normalize_output_path(png_candidates[0], ".png", task_path),
        svg=_normalize_output_path(svg_candidates[0], ".svg", task_path),
    )


def _normalize_output_path(path_text: str, suffix: str, task_path: Path) -> str:
    path = Path(path_text)
    if path.is_absolute():
        raise FigureSpecValidationError("output paths must be relative to the task directory")
    if path.suffix.lower() != suffix:
        raise FigureSpecValidationError(f"output path '{path_text}' must end with {suffix}")

    task_root = task_path.resolve()
    figures_dir = (task_root / "figures").resolve()
    candidate = (task_root / path).resolve()
    try:
        candidate.relative_to(figures_dir)
    except ValueError as exc:
        raise FigureSpecValidationError("output paths must stay inside the current task figures/ directory") from exc
    return candidate.relative_to(task_root).as_posix()


def _required_string(data: dict[str, Any], field_name: str) -> str:
    value = data.get(field_name)
    if not isinstance(value, str) or not value.strip():
        raise FigureSpecValidationError(f"field '{field_name}' must be a non-empty string")
    return value.strip()


def _figure_id_for_diagnostic(item: Any, index: int) -> str:
    if isinstance(item, dict):
        figure_id = item.get("figure_id")
        if isinstance(figure_id, str) and figure_id.strip():
            return figure_id.strip()
    return f"figure_{index}"


def _process_axis(df: pd.DataFrame) -> str | None:
    for column in ["epoch", "step"]:
        if column in df.columns and _column_is_numeric(df[column]):
            return column
    for column in TIME_AXIS_PRIORITY:
        if column in df.columns and _column_is_datetime(df[column]):
            return column
    return None


def _numeric_columns(df: pd.DataFrame) -> list[str]:
    return [column for column in df.columns if _column_is_numeric(df[column])]


def _column_is_numeric(series: pd.Series) -> bool:
    return pd.to_numeric(series, errors="coerce").notna().any()


def _column_is_datetime(series: pd.Series) -> bool:
    return pd.to_datetime(series, errors="coerce").notna().any()


def _valid_numeric_rows(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    converted = pd.DataFrame({column: pd.to_numeric(df[column], errors="coerce") for column in columns})
    return df.loc[converted.notna().all(axis=1)]


def _valid_line_rows(df: pd.DataFrame, x: str, y: str) -> pd.DataFrame:
    y_values = pd.to_numeric(df[y], errors="coerce")
    if _column_is_numeric(df[x]):
        x_values = pd.to_numeric(df[x], errors="coerce")
    else:
        x_values = pd.to_datetime(df[x], errors="coerce")
    return df.loc[x_values.notna() & y_values.notna()]


def _first_existing_column(df: pd.DataFrame, priority: list[str]) -> str | None:
    for column in priority:
        if column in df.columns:
            return column
    return None


def _configured_group_column(df: pd.DataFrame, groups: dict[str, str]) -> str | None:
    for key in ["primary", "secondary"]:
        column = groups.get(key)
        if column in df.columns:
            return column
    for column in groups.values():
        if column in df.columns:
            return column
    return None


def _bar_group_column(df: pd.DataFrame, groups: dict[str, str], category: str) -> str | None:
    for key in ["secondary", "group_by"]:
        column = groups.get(key)
        if column in df.columns and column != category:
            return column
    for key in ["primary"]:
        column = groups.get(key)
        if column in df.columns and column != category:
            return column
    return None


def _seed_distribution_candidate(df: pd.DataFrame) -> bool:
    if "seed" not in df.columns:
        return False
    return int(df["seed"].nunique(dropna=True)) >= 2


def _field_units(fields: list[str | None], units: dict[str, str]) -> dict[str, str]:
    return {field: units[field] for field in fields if field and field in units}


def _spec_units(spec: FigureSpec, units: dict[str, str]) -> dict[str, str]:
    return _field_units(_required_metric_fields(spec), units)


def _select_priority_columns(priority: list[str], columns: list[str]) -> list[str]:
    selected: list[str] = []
    for item in priority:
        column = _select_priority_column([item], columns)
        if column and column not in selected:
            selected.append(column)
    return selected


def _select_priority_column(priority: list[str], columns: list[str]) -> str | None:
    for item in priority:
        aliases = METRIC_ALIASES.get(item, [item])
        for alias in aliases:
            for column in columns:
                if column == alias:
                    return column
        for alias in aliases:
            for column in columns:
                if _matches_metric_name(column, alias):
                    return column
    return None


def _matches_metric_name(column: str, target: str) -> bool:
    tokens = [token for token in re.split(r"[^a-z0-9]+", column.lower()) if token]
    return target in tokens or column.lower().startswith(f"{target}_")


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")
    return slug or "figure"


def _skip(
    figure_id: str,
    reason: str,
    chart_type: str | None = None,
    x: str | None = None,
    y: str | None = None,
    group_by: str | None = None,
) -> dict[str, str]:
    data = {"figure_id": figure_id, "reason": reason}
    if chart_type:
        data["chart_type"] = chart_type
    if x:
        data["x"] = x
    if y:
        data["y"] = y
    if group_by:
        data["group_by"] = group_by
    return data


def _unsupported_chart_diagnostic(
    spec: FigureSpec,
    available_fields: list[str],
    reason: str,
) -> dict[str, Any]:
    return {
        "figure_id": spec.figure_id,
        "requested_chart_intent": {
            "figure_id": spec.figure_id,
            "chart_type": spec.chart_type,
            "title": spec.title,
            "x": spec.x,
            "y": spec.y,
            "group_by": spec.group_by,
        },
        "available_fields": [str(field) for field in available_fields],
        "reason": reason,
        "safe_next_action": (
            "Rewrite the figure spec as line, bar, or box, or rerun with "
            "`--fallback bounded` to record a bounded figure request."
        ),
    }
