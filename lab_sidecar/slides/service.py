from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import PP_ALIGN
from pptx.util import Inches, Pt

from lab_sidecar.core.manifest import load_task, manifest_path, write_manifest
from lab_sidecar.core.models import ArtifactRecord, TaskRecord, TaskStatus
from lab_sidecar.core.paths import resolve_workspace_path
from lab_sidecar.storage.sqlite_index import upsert_task


SUPPORTED_SLIDE_TEMPLATES = {"zh-summary", "en-summary"}
UNKNOWN_ZH = "未自动推断"
UNKNOWN_EN = "Not automatically inferred"
MAX_FIGURES = 4
MAX_FIGURES_PER_SLIDE = 2
MAX_NUMERIC_COLUMNS = 6
MAX_KEY_COLUMNS = 10
MAX_REPORT_BULLETS = 5
MAX_LOG_LINES = 8
MAX_LOG_CHARS = 860


class InvalidSlidesTemplateError(RuntimeError):
    pass


class SlidesArtifactsRequiredError(RuntimeError):
    pass


class SlidesWriteError(RuntimeError):
    pass


@dataclass
class SlidesGenerationResult:
    record: TaskRecord
    template: str
    pptx_path: Path
    summary_path: Path
    summary: dict[str, Any]


@dataclass
class FigureItem:
    figure_id: str
    chart_type: str
    path: Path
    x: str
    y: str
    group_by: str

    def caption(self, task_path: Path) -> str:
        parts = [self.figure_id, self.chart_type]
        if self.x:
            parts.append(f"x={self.x}")
        if self.y:
            parts.append(f"y={self.y}")
        if self.group_by:
            parts.append(f"group_by={self.group_by}")
        return " | ".join(part for part in parts if part)

    def to_summary(self, task_path: Path) -> dict[str, str]:
        return {
            "figure_id": self.figure_id,
            "chart_type": self.chart_type,
            "path": _task_relative(self.path, task_path),
            "x": self.x,
            "y": self.y,
            "group_by": self.group_by,
        }


@dataclass
class SlideRecord:
    slide_index: int
    title: str
    purpose: str
    source_artifacts: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "slide_index": self.slide_index,
            "title": self.title,
            "purpose": self.purpose,
            "source_artifacts": self.source_artifacts,
        }


class SlidesGenerationService:
    def __init__(self, root: Path):
        self.root = root.resolve()

    def generate(self, task_id: str, template: str = "zh-summary") -> SlidesGenerationResult:
        if template not in SUPPORTED_SLIDE_TEMPLATES:
            allowed = ", ".join(sorted(SUPPORTED_SLIDE_TEMPLATES))
            raise InvalidSlidesTemplateError(f"unsupported template '{template}'. Allowed: {allowed}")

        record = load_task(self.root, task_id)
        task_path = resolve_workspace_path(record.paths.task_dir, self.root)
        slides_dir = task_path / "slides"
        pptx_path = slides_dir / "presentation-draft.pptx"
        summary_path = slides_dir / "slides-summary.json"

        context = self._build_context(record, task_path, template)
        if not context["is_diagnostic"] and not context["has_completed_inputs"]:
            raise SlidesArtifactsRequiredError("metrics, figures, or report artifacts are missing")

        slides_dir.mkdir(parents=True, exist_ok=True)
        builder = _PresentationBuilder(context)
        presentation = builder.build()
        context["slides"] = builder.slide_records
        try:
            presentation.save(pptx_path)
            summary = self._build_summary(record, task_path, pptx_path, summary_path, context, presentation)
            summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        except OSError as exc:
            raise SlidesWriteError(f"slides files could not be written: {exc}") from exc

        self._upsert_artifacts(record, context["source_artifacts"])
        record.updated_at = _now_iso()
        write_manifest(manifest_path(self.root, task_id), record)
        upsert_task(self.root, record)

        return SlidesGenerationResult(
            record=record,
            template=template,
            pptx_path=pptx_path,
            summary_path=summary_path,
            summary=summary,
        )

    def _build_context(self, record: TaskRecord, task_path: Path, template: str) -> dict[str, Any]:
        metrics_path = task_path / "metrics" / "normalized_metrics.csv"
        report_path = task_path / "reports" / "report-fragment.md"
        figure_summary_path = task_path / "figures" / "figure-summary.json"
        source_refs_path = task_path / "raw" / "source_refs.json"
        stdout_path = resolve_workspace_path(record.paths.stdout, self.root)
        stderr_path = resolve_workspace_path(record.paths.stderr, self.root)
        figure_items, figure_warnings = self._find_png_figures(record, task_path, figure_summary_path)
        is_diagnostic = record.status in {TaskStatus.FAILED, TaskStatus.CANCELLED}
        metrics_summary = self._metrics_summary(metrics_path)
        report_excerpt = self._report_excerpt(report_path, template)
        stdout_tail = _bounded_log_tail(stdout_path)
        stderr_tail = _bounded_log_tail(stderr_path)
        source_artifacts = self._source_artifacts(
            task_path=task_path,
            metrics_path=metrics_path,
            report_path=report_path,
            figure_summary_path=figure_summary_path,
            source_refs_path=source_refs_path,
            stdout_path=stdout_path,
            stderr_path=stderr_path,
            figure_items=figure_items,
        )
        warnings = list(figure_warnings)
        if metrics_summary.get("numeric_omitted_count", 0):
            warnings.append(f"omitted {metrics_summary['numeric_omitted_count']} numeric metric column(s) from slides")
        if metrics_summary.get("omitted_key_column_count", 0):
            warnings.append(f"omitted {metrics_summary['omitted_key_column_count']} metric column name(s) from slides")

        return {
            "template": template,
            "language": "zh" if template.startswith("zh") else "en",
            "unknown": UNKNOWN_ZH if template.startswith("zh") else UNKNOWN_EN,
            "is_diagnostic": is_diagnostic,
            "has_completed_inputs": metrics_path.exists() or bool(figure_items) or report_path.exists(),
            "record": record,
            "task_path": task_path,
            "metrics_path": metrics_path if metrics_path.exists() else None,
            "metrics_summary": metrics_summary,
            "figure_items": figure_items,
            "figure_summary_path": figure_summary_path if figure_summary_path.exists() else None,
            "report_path": report_path if report_path.exists() else None,
            "report_excerpt": report_excerpt,
            "source_refs_path": source_refs_path if source_refs_path.exists() else None,
            "stdout_tail": stdout_tail,
            "stderr_tail": stderr_tail,
            "source_artifacts": source_artifacts,
            "warnings": warnings,
        }

    def _metrics_summary(self, metrics_path: Path) -> dict[str, Any]:
        base = {
            "present": False,
            "path": "metrics/normalized_metrics.csv",
            "row_count": 0,
            "columns": [],
            "key_columns": [],
            "omitted_key_column_count": 0,
            "numeric": [],
            "numeric_omitted_count": 0,
        }
        if not metrics_path.exists():
            return base
        try:
            df = pd.read_csv(metrics_path)
        except (OSError, pd.errors.EmptyDataError):
            return base

        columns = [str(column) for column in df.columns]
        numeric: list[dict[str, Any]] = []
        for column in df.columns:
            values = pd.to_numeric(df[column], errors="coerce")
            count = int(values.notna().sum())
            if count == 0:
                continue
            final_value = _json_float(values.dropna().iloc[-1]) if count else None
            numeric.append(
                {
                    "column": str(column),
                    "count": count,
                    "mean": _json_float(values.mean()),
                    "min": _json_float(values.min()),
                    "max": _json_float(values.max()),
                    "final": final_value,
                }
            )
        return {
            "present": True,
            "path": "metrics/normalized_metrics.csv",
            "row_count": int(len(df)),
            "columns": columns,
            "key_columns": columns[:MAX_KEY_COLUMNS],
            "omitted_key_column_count": max(0, len(columns) - MAX_KEY_COLUMNS),
            "numeric": numeric[:MAX_NUMERIC_COLUMNS],
            "numeric_omitted_count": max(0, len(numeric) - MAX_NUMERIC_COLUMNS),
        }

    def _report_excerpt(self, report_path: Path, template: str) -> list[str]:
        if not report_path.exists():
            return []
        text = report_path.read_text(encoding="utf-8", errors="replace")
        lines: list[str] = []
        for raw_line in text.splitlines():
            line = _clean_markdown_line(raw_line)
            if not line:
                continue
            lines.append(_short_text(line, 125))
            if len(lines) >= MAX_REPORT_BULLETS:
                break
        return lines or [UNKNOWN_ZH if template.startswith("zh") else UNKNOWN_EN]

    def _find_png_figures(self, record: TaskRecord, task_path: Path, figure_summary_path: Path) -> tuple[list[FigureItem], list[str]]:
        items: list[FigureItem] = []
        warnings: list[str] = []
        if figure_summary_path.exists():
            data = _read_json(figure_summary_path)
            for raw_item in data.get("generated_figures") or data.get("figures") or []:
                path_text = raw_item.get("png_path") or raw_item.get("png")
                if not path_text:
                    continue
                path = _resolve_task_or_workspace_path(path_text, self.root, task_path)
                if path.exists() and path.suffix.lower() == ".png":
                    items.append(
                        FigureItem(
                            figure_id=str(raw_item.get("figure_id") or path.stem),
                            chart_type=str(raw_item.get("chart_type") or "figure"),
                            path=path,
                            x=str(raw_item.get("x") or ""),
                            y=str(raw_item.get("y") or ""),
                            group_by=str(raw_item.get("group_by") or ""),
                        )
                    )

        known_paths = {item.path.resolve() for item in items}
        for artifact in record.artifacts:
            if artifact.type != "figure" or not artifact.path.lower().endswith(".png"):
                continue
            path = _resolve_task_or_workspace_path(artifact.path, self.root, task_path)
            if path.exists() and path.resolve() not in known_paths:
                items.append(FigureItem(path.stem, "figure", path, "", "", ""))
                known_paths.add(path.resolve())

        figures_dir = task_path / "figures"
        if figures_dir.exists():
            for path in sorted(figures_dir.glob("*.png")):
                if path.resolve() not in known_paths:
                    items.append(FigureItem(path.stem, "figure", path, "", "", ""))
                    known_paths.add(path.resolve())

        if len(items) > MAX_FIGURES:
            warnings.append(f"limited figures to first {MAX_FIGURES} PNG artifact(s); omitted {len(items) - MAX_FIGURES}")
        return items[:MAX_FIGURES], warnings

    def _source_artifacts(
        self,
        task_path: Path,
        metrics_path: Path,
        report_path: Path,
        figure_summary_path: Path,
        source_refs_path: Path,
        stdout_path: Path,
        stderr_path: Path,
        figure_items: list[FigureItem],
    ) -> list[str]:
        candidates = [
            task_path / "manifest.json",
            metrics_path,
            task_path / "metrics" / "collection-summary.json",
            figure_summary_path,
            report_path,
            source_refs_path,
            stdout_path,
            stderr_path,
            task_path / "reproduce" / "command.txt",
            *[item.path for item in figure_items],
        ]
        return [_task_relative(path, task_path) for path in _unique_paths([path for path in candidates if path.exists()])]

    def _build_summary(
        self,
        record: TaskRecord,
        task_path: Path,
        pptx_path: Path,
        summary_path: Path,
        context: dict[str, Any],
        presentation: Presentation,
    ) -> dict[str, Any]:
        included_figures = [item.to_summary(task_path) for item in context["figure_items"]]
        included_metrics = {
            "present": context["metrics_summary"]["present"],
            "path": context["metrics_summary"]["path"],
            "row_count": context["metrics_summary"]["row_count"],
            "key_columns": context["metrics_summary"]["key_columns"],
            "numeric": context["metrics_summary"]["numeric"],
        }
        return {
            "schema_version": "1",
            "task_id": record.task_id,
            "task_status": record.status.value,
            "template": context["template"],
            "generated_at": _now_iso(),
            "pptx_path": _task_relative(pptx_path, task_path),
            "summary_path": _task_relative(summary_path, task_path),
            "slide_count": len(presentation.slides),
            "included_figures": included_figures,
            "included_metrics": included_metrics,
            "warnings": context["warnings"],
            "slides": [slide.to_dict() for slide in context.get("slides", [])],
            "report_excerpt": context["report_excerpt"],
            "source_artifacts": context["source_artifacts"],
            # Backward-compatible aliases for Phase 4.1 tests/users.
            "slide_titles": [slide.title for slide in context.get("slides", [])],
            "metrics": context["metrics_summary"],
            "figures": [item.to_summary(task_path)["path"] for item in context["figure_items"]],
        }

    def _upsert_artifacts(self, record: TaskRecord, source_artifacts: list[str]) -> None:
        _upsert_artifact(
            record,
            ArtifactRecord(
                artifact_id="slides_presentation_draft_pptx",
                type="presentation",
                path="slides/presentation-draft.pptx",
                description="Static editable PowerPoint draft",
                source_paths=source_artifacts,
            ),
        )
        _upsert_artifact(
            record,
            ArtifactRecord(
                artifact_id="slides_summary_json",
                type="config",
                path="slides/slides-summary.json",
                description="Slides generation summary and provenance",
                source_paths=source_artifacts,
            ),
        )


class _PresentationBuilder:
    def __init__(self, context: dict[str, Any]):
        self.context = context
        self.prs = Presentation()
        self.prs.slide_width = Inches(13.333)
        self.prs.slide_height = Inches(7.5)
        self.slide_records: list[SlideRecord] = []
        self.zh = context["language"] == "zh"
        self.unknown = context["unknown"]
        self.primary = RGBColor(35, 48, 62)
        self.accent = RGBColor(15, 118, 110)
        self.warn = RGBColor(185, 28, 28)
        self.bg = RGBColor(248, 250, 252)
        self.muted = RGBColor(100, 116, 139)

    def build(self) -> Presentation:
        if self.context["is_diagnostic"]:
            self._build_diagnostic()
        else:
            self._build_completed()
        return self.prs

    def _build_completed(self) -> None:
        record: TaskRecord = self.context["record"]
        source = record.command or record.source_path or self.unknown
        self._title_slide(
            "实验结果演示草稿" if self.zh else "Experiment Results Draft",
            [f"task_id: {record.task_id}", f"{'来源' if self.zh else 'Source'}: {source}"],
            "task overview",
            ["manifest.json"],
        )
        self._settings_slide()
        self._metrics_slide()
        self._figure_slides()
        self._result_summary_slide()
        self._reproduce_slide()

    def _build_diagnostic(self) -> None:
        record: TaskRecord = self.context["record"]
        if record.status == TaskStatus.CANCELLED:
            title = "取消任务诊断草稿" if self.zh else "Cancelled Task Diagnostics"
            purpose = "cancelled task overview"
        else:
            title = "失败任务诊断草稿" if self.zh else "Failed Task Diagnostics"
            purpose = "failed task overview"
        self._title_slide(title, [f"task_id: {record.task_id}", f"status: {record.status.value}"], purpose, ["manifest.json"], danger=True)
        self._settings_slide()
        if record.status == TaskStatus.CANCELLED:
            self._cancelled_summary_slide()
        else:
            self._failed_summary_slide()
        self._logs_slide()
        self._reproduce_slide()

    def _title_slide(self, title: str, subtitles: list[str], purpose: str, sources: list[str], danger: bool = False) -> None:
        slide = self._blank_slide(title, purpose, sources, dark=True, danger=danger)
        title_box = slide.shapes.add_textbox(Inches(0.75), Inches(1.25), Inches(11.8), Inches(1.2))
        self._set_text(title_box, title, size=34, bold=True, color=RGBColor(255, 255, 255))
        self._status_bar(slide, Inches(0.78), Inches(2.72), Inches(4.5), self.context["record"].status.value, danger=danger)

        y = 3.42
        for subtitle in subtitles[:3]:
            box = slide.shapes.add_textbox(Inches(0.82), Inches(y), Inches(11.6), Inches(0.42))
            self._set_text(box, _short_text(subtitle, 150), size=15, color=RGBColor(232, 236, 241))
            y += 0.5

    def _settings_slide(self) -> None:
        record: TaskRecord = self.context["record"]
        title = "实验设置" if self.zh else "Experiment Settings"
        rows = [
            ("mode", record.mode),
            ("status", record.status.value),
            ("command", record.command or self.unknown),
            ("source_path", record.source_path or self.unknown),
            ("working_dir", record.working_dir or self.unknown),
            ("exit_code", record.exit_code if record.exit_code is not None else self.unknown),
        ]
        self._table_slide(title, rows, "manifest settings and provenance", ["manifest.json"], note="来源: manifest.json" if self.zh else "Source: manifest.json")

    def _metrics_slide(self) -> None:
        metrics = self.context["metrics_summary"]
        title = "指标摘要" if self.zh else "Metrics Summary"
        slide = self._blank_slide(title, "summarize normalized metrics", ["metrics/normalized_metrics.csv"])
        self._add_title(slide, title)
        if not metrics["present"]:
            self._callout_row(slide, [("rows", "0"), ("metrics", self.unknown)], y=Inches(1.25))
            self._add_bullets(slide, ["metrics/normalized_metrics.csv not found"], Inches(0.9), Inches(3.2), Inches(11.2), Inches(1.0))
            return

        self._callout_row(
            slide,
            [
                ("rows", str(metrics["row_count"])),
                ("columns", str(len(metrics["columns"]))),
                ("numeric", str(len(metrics.get("numeric", [])) + metrics.get("numeric_omitted_count", 0))),
            ],
            y=Inches(1.14),
        )
        key_columns = ", ".join(metrics["key_columns"]) or self.unknown
        if metrics["omitted_key_column_count"]:
            key_columns += f", ... (+{metrics['omitted_key_column_count']})"
        self._caption(slide, f"key columns: {key_columns}", Inches(0.75), Inches(2.62), Inches(11.7))

        numeric = metrics.get("numeric") or []
        if not numeric:
            self._add_bullets(slide, [self.unknown], Inches(0.9), Inches(3.1), Inches(11.0), Inches(1.0))
            return

        table = slide.shapes.add_table(len(numeric) + 1, 5, Inches(0.75), Inches(3.05), Inches(11.8), Inches(3.05)).table
        headers = ["metric", "min", "mean", "max", "final"]
        for index, header in enumerate(headers):
            cell = table.cell(0, index)
            cell.text = header
            self._style_cell(cell, bold=True, fill=RGBColor(226, 232, 240))
        for row_index, item in enumerate(numeric, start=1):
            values = [
                item["column"],
                _format_number(item["min"], self.unknown),
                _format_number(item["mean"], self.unknown),
                _format_number(item["max"], self.unknown),
                _format_number(item["final"], self.unknown),
            ]
            for col_index, value in enumerate(values):
                cell = table.cell(row_index, col_index)
                cell.text = _short_text(value, 34)
                self._style_cell(cell)

    def _figure_slides(self) -> None:
        figure_items: list[FigureItem] = self.context["figure_items"]
        title_base = "图表" if self.zh else "Figures"
        if not figure_items:
            slide = self._blank_slide(title_base, "show generated figures", ["figures/"])
            self._add_title(slide, title_base)
            self._empty_visual(slide, self.unknown, "figures/*.png not found")
            return

        chunks = [figure_items[index : index + MAX_FIGURES_PER_SLIDE] for index in range(0, len(figure_items), MAX_FIGURES_PER_SLIDE)]
        for page_index, chunk in enumerate(chunks, start=1):
            title = title_base if len(chunks) == 1 else f"{title_base} {page_index}/{len(chunks)}"
            sources = [_task_relative(item.path, self.context["task_path"]) for item in chunk]
            if self.context["figure_summary_path"]:
                sources.insert(0, "figures/figure-summary.json")
            slide = self._blank_slide(title, "show generated figure artifacts", sources)
            self._add_title(slide, title)
            if len(chunk) == 1:
                item = chunk[0]
                self._add_picture_fit(slide, item.path, Inches(0.9), Inches(1.25), Inches(11.55), Inches(5.2))
                self._caption(slide, item.caption(self.context["task_path"]), Inches(0.9), Inches(6.55), Inches(11.4))
            else:
                x_positions = [Inches(0.68), Inches(6.82)]
                for index, item in enumerate(chunk):
                    self._add_picture_fit(slide, item.path, x_positions[index], Inches(1.32), Inches(5.78), Inches(4.85))
                    self._caption(slide, item.caption(self.context["task_path"]), x_positions[index], Inches(6.3), Inches(5.76))

    def _result_summary_slide(self) -> None:
        title = "结果摘要" if self.zh else "Result Summary"
        bullets = self.context["report_excerpt"] or [self.unknown]
        if self.context["report_path"]:
            sources = ["reports/report-fragment.md"]
            suffix = "来源: reports/report-fragment.md" if self.zh else "Source: reports/report-fragment.md"
        else:
            sources = []
            suffix = self.unknown
        slide = self._blank_slide(title, "summarize report fragment", sources)
        self._add_title(slide, title)
        self._add_info_blocks(slide, [*bullets, suffix])

    def _failed_summary_slide(self) -> None:
        record: TaskRecord = self.context["record"]
        title = "失败诊断" if self.zh else "Failure Diagnostics"
        bullets = [
            f"status: {record.status.value}",
            f"exit_code: {record.exit_code if record.exit_code is not None else self.unknown}",
            f"failure_summary: {_short_text(record.failure_summary or self.unknown, 210)}",
            "该任务不会被写成成功实验结果。" if self.zh else "This task is not summarized as a successful experiment.",
        ]
        slide = self._blank_slide(title, "diagnose failed task", ["manifest.json", "stderr.log"], danger=True)
        self._add_title(slide, title)
        self._status_bar(slide, Inches(0.75), Inches(1.18), Inches(3.4), record.status.value, danger=True)
        self._add_info_blocks(slide, bullets, top=Inches(2.05))

    def _cancelled_summary_slide(self) -> None:
        record: TaskRecord = self.context["record"]
        title = "取消诊断" if self.zh else "Cancellation Diagnostics"
        note = _first_non_empty(self.context["stderr_tail"]) or self.unknown
        bullets = [
            f"status: {record.status.value}",
            f"started_at: {record.started_at or self.unknown}",
            f"finished_at: {record.finished_at or self.unknown}",
            f"cancellation note: {_short_text(note, 180)}",
            "该任务不会被写成成功实验结果。" if self.zh else "This task is not summarized as a successful experiment.",
        ]
        slide = self._blank_slide(title, "diagnose cancelled task", ["manifest.json", "stderr.log"], danger=True)
        self._add_title(slide, title)
        self._status_bar(slide, Inches(0.75), Inches(1.18), Inches(3.4), record.status.value, danger=True)
        self._add_info_blocks(slide, bullets, top=Inches(2.05))

    def _logs_slide(self) -> None:
        title = "日志尾部" if self.zh else "Log Tail"
        lines = [
            "stderr.log:",
            *(self.context["stderr_tail"] or [self.unknown]),
            "",
            "stdout.log:",
            *(self.context["stdout_tail"] or [self.unknown]),
        ]
        slide = self._blank_slide(title, "show bounded stdout/stderr tails", ["stderr.log", "stdout.log"])
        self._add_title(slide, title)
        self._text_panel(slide, lines[:22], Inches(0.75), Inches(1.25), Inches(11.85), Inches(5.35), font_size=8)

    def _reproduce_slide(self) -> None:
        record: TaskRecord = self.context["record"]
        title = "复现信息" if self.zh else "Reproducibility"
        rows = [
            ("command", record.command or self.unknown),
            ("source_path", record.source_path or self.unknown),
            ("working_dir", record.working_dir or self.unknown),
            ("artifact_dir", record.paths.task_dir),
            ("source_refs", "raw/source_refs.json" if self.context["source_refs_path"] else self.unknown),
            ("generated_from", ", ".join(self.context["source_artifacts"][:6]) or self.unknown),
        ]
        self._table_slide(
            title,
            rows,
            "record reproducibility details",
            ["manifest.json", "reproduce/command.txt"],
            note="SQLite 不是唯一事实来源；本草稿基于 task artifact 文件生成。" if self.zh else "SQLite is not the source of truth; this draft uses task artifact files.",
        )

    def _blank_slide(
        self,
        title: str,
        purpose: str,
        sources: list[str],
        dark: bool = False,
        danger: bool = False,
    ):
        slide = self.prs.slides.add_slide(self.prs.slide_layouts[6])
        self.slide_records.append(SlideRecord(len(self.slide_records) + 1, title, purpose, sources))
        fill = slide.background.fill
        fill.solid()
        fill.fore_color.rgb = RGBColor(30, 41, 59) if dark else self.bg
        accent_color = self.warn if danger else self.accent
        accent = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0), Inches(0), Inches(0.24), Inches(7.5))
        accent.fill.solid()
        accent.fill.fore_color.rgb = accent_color
        accent.line.color.rgb = accent_color
        self._footer(slide, danger=danger, dark=dark)
        return slide

    def _add_title(self, slide, title: str) -> None:
        box = slide.shapes.add_textbox(Inches(0.72), Inches(0.36), Inches(11.8), Inches(0.56))
        self._set_text(box, title, size=25, bold=True, color=self.primary)

    def _footer(self, slide, danger: bool = False, dark: bool = False) -> None:
        record: TaskRecord = self.context["record"]
        text = f"Lab-Sidecar | {record.task_id} | {record.status.value}"
        box = slide.shapes.add_textbox(Inches(0.72), Inches(7.08), Inches(11.9), Inches(0.22))
        self._set_text(box, text, size=8, color=RGBColor(203, 213, 225) if dark else self.muted)
        line = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0.72), Inches(6.98), Inches(11.85), Inches(0.02))
        line.fill.solid()
        line.fill.fore_color.rgb = self.warn if danger else RGBColor(203, 213, 225)
        line.line.color.rgb = line.fill.fore_color.rgb

    def _status_bar(self, slide, left, top, width, text: str, danger: bool = False) -> None:
        color = self.warn if danger else self.accent
        box = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, left, top, width, Inches(0.42))
        box.fill.solid()
        box.fill.fore_color.rgb = color
        box.line.color.rgb = color
        self._set_text(box, text.upper(), size=13, bold=True, color=RGBColor(255, 255, 255), align=PP_ALIGN.CENTER)

    def _callout_row(self, slide, values: list[tuple[str, str]], y) -> None:
        width = Inches(3.55)
        gap = Inches(0.34)
        x = Inches(0.75)
        for label, value in values[:3]:
            shape = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, x, y, width, Inches(1.18))
            shape.fill.solid()
            shape.fill.fore_color.rgb = RGBColor(236, 253, 245)
            shape.line.color.rgb = RGBColor(153, 246, 228)
            self._set_text(shape, f"{value}\n{label}", size=16, bold=True, color=self.primary, align=PP_ALIGN.CENTER)
            x += width + gap

    def _add_info_blocks(self, slide, bullets: list[str], top=Inches(1.25)) -> None:
        y = top
        for bullet in bullets[:6]:
            block = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(0.82), y, Inches(11.15), Inches(0.58))
            block.fill.solid()
            block.fill.fore_color.rgb = RGBColor(241, 245, 249)
            block.line.color.rgb = RGBColor(226, 232, 240)
            self._set_text(block, _short_text(bullet, 165), size=12, color=self.primary)
            y += Inches(0.72)

    def _add_bullets(self, slide, bullets: list[str], left, top, width, height, font_size: int = 14) -> None:
        box = slide.shapes.add_textbox(left, top, width, height)
        frame = box.text_frame
        frame.word_wrap = True
        frame.clear()
        for index, bullet in enumerate(bullets):
            paragraph = frame.paragraphs[0] if index == 0 else frame.add_paragraph()
            paragraph.text = _short_text(bullet, 160)
            paragraph.level = 0
            paragraph.font.size = Pt(font_size)
            paragraph.font.color.rgb = self.primary

    def _text_panel(self, slide, lines: list[str], left, top, width, height, font_size: int = 9) -> None:
        panel = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, left, top, width, height)
        panel.fill.solid()
        panel.fill.fore_color.rgb = RGBColor(15, 23, 42)
        panel.line.color.rgb = RGBColor(51, 65, 85)
        box = slide.shapes.add_textbox(left + Inches(0.18), top + Inches(0.15), width - Inches(0.36), height - Inches(0.3))
        self._set_text(box, "\n".join(_short_text(line, 150) for line in lines), size=font_size, color=RGBColor(226, 232, 240), font_name="Consolas")

    def _table_slide(self, title: str, rows: list[tuple[str, Any]], purpose: str, sources: list[str], note: str | None = None) -> None:
        slide = self._blank_slide(title, purpose, sources)
        self._add_title(slide, title)
        table = slide.shapes.add_table(len(rows) + 1, 2, Inches(0.75), Inches(1.16), Inches(11.85), Inches(4.95)).table
        table.columns[0].width = Inches(2.25)
        table.columns[1].width = Inches(9.6)
        for index, header in enumerate(["field", "value"]):
            cell = table.cell(0, index)
            cell.text = header
            self._style_cell(cell, bold=True, fill=RGBColor(226, 232, 240))
        for row_index, (key, value) in enumerate(rows, start=1):
            cells = [table.cell(row_index, 0), table.cell(row_index, 1)]
            cells[0].text = str(key)
            cells[1].text = _short_text(value, 122)
            self._style_cell(cells[0], bold=True)
            self._style_cell(cells[1])
        if note:
            self._caption(slide, note, Inches(0.75), Inches(6.55), Inches(11.8))

    def _style_cell(self, cell, bold: bool = False, fill: RGBColor | None = None) -> None:
        if fill:
            cell.fill.solid()
            cell.fill.fore_color.rgb = fill
        cell.margin_left = Inches(0.04)
        cell.margin_right = Inches(0.04)
        for paragraph in cell.text_frame.paragraphs:
            paragraph.font.size = Pt(9.5)
            paragraph.font.bold = bold
            paragraph.font.color.rgb = self.primary
            paragraph.alignment = PP_ALIGN.LEFT

    def _add_picture_fit(self, slide, path: Path, left, top, width, height) -> None:
        from PIL import Image

        with Image.open(path) as image:
            img_width, img_height = image.size
        img_ratio = img_width / img_height if img_height else 1
        box_ratio = width / height
        if img_ratio >= box_ratio:
            draw_width = width
            draw_height = width / img_ratio
            draw_left = left
            draw_top = top + (height - draw_height) / 2
        else:
            draw_height = height
            draw_width = height * img_ratio
            draw_left = left + (width - draw_width) / 2
            draw_top = top
        slide.shapes.add_picture(str(path), draw_left, draw_top, width=draw_width, height=draw_height)

    def _caption(self, slide, text: str, left, top, width) -> None:
        box = slide.shapes.add_textbox(left, top, width, Inches(0.35))
        self._set_text(box, _short_text(text, 145), size=8.5, color=self.muted)

    def _empty_visual(self, slide, title: str, detail: str) -> None:
        shape = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(2.0), Inches(2.25), Inches(9.2), Inches(2.0))
        shape.fill.solid()
        shape.fill.fore_color.rgb = RGBColor(241, 245, 249)
        shape.line.color.rgb = RGBColor(203, 213, 225)
        self._set_text(shape, f"{title}\n{detail}", size=16, bold=True, color=self.primary, align=PP_ALIGN.CENTER)

    def _set_text(
        self,
        shape,
        text: str,
        size: float,
        color: RGBColor,
        bold: bool = False,
        font_name: str = "Calibri",
        align: PP_ALIGN = PP_ALIGN.LEFT,
    ) -> None:
        frame = shape.text_frame
        frame.word_wrap = True
        frame.clear()
        paragraph = frame.paragraphs[0]
        paragraph.text = text
        paragraph.alignment = align
        for run in paragraph.runs:
            run.font.name = font_name
            run.font.size = Pt(size)
            run.font.bold = bold
            run.font.color.rgb = color


def _read_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _bounded_log_tail(path: Path) -> list[str]:
    if not path.exists():
        return []
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()[-MAX_LOG_LINES:]
    bounded: list[str] = []
    used = 0
    for line in lines:
        text = _short_text(line, 150)
        if used + len(text) > MAX_LOG_CHARS:
            bounded.append("... truncated ...")
            break
        bounded.append(text)
        used += len(text)
    return bounded


def _clean_markdown_line(line: str) -> str:
    stripped = line.strip()
    if not stripped or stripped in {"```", "```text"}:
        return ""
    stripped = re.sub(r"^#+\s*", "", stripped)
    stripped = re.sub(r"^[-*]\s*", "", stripped)
    stripped = stripped.replace("`", "")
    stripped = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", stripped)
    stripped = stripped.replace("|", " ").strip()
    return re.sub(r"\s+", " ", stripped)


def _resolve_task_or_workspace_path(path_text: str, root: Path, task_path: Path) -> Path:
    path = Path(path_text)
    if path.is_absolute():
        return path
    workspace_candidate = (root / path).resolve()
    if workspace_candidate.exists() or path_text.startswith(".lab-sidecar/"):
        return workspace_candidate
    return (task_path / path).resolve()


def _task_relative(path: Path, task_path: Path) -> str:
    return path.resolve().relative_to(task_path.resolve()).as_posix()


def _unique_paths(paths: list[Path]) -> list[Path]:
    seen: set[Path] = set()
    result: list[Path] = []
    for path in paths:
        resolved = path.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        result.append(resolved)
    return result


def _upsert_artifact(record: TaskRecord, artifact: ArtifactRecord) -> None:
    record.artifacts = [item for item in record.artifacts if item.artifact_id != artifact.artifact_id]
    record.artifacts.append(artifact)


def _json_float(value: Any) -> float | None:
    if pd.isna(value):
        return None
    return float(value)


def _format_number(value: Any, unknown: str = UNKNOWN_ZH) -> str:
    if value is None:
        return unknown
    if isinstance(value, float):
        return f"{value:.6g}"
    return str(value)


def _short_text(value: Any, limit: int) -> str:
    text = str(value).replace("\r", " ").replace("\n", " ")
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) <= limit:
        return text
    return text[: limit - 3].rstrip() + "..."


def _first_non_empty(lines: list[str]) -> str | None:
    for line in reversed(lines):
        if line.strip():
            return line
    return None


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
