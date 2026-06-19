from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import yaml

from lab_sidecar.core.manifest import load_task, manifest_path, write_manifest
from lab_sidecar.core.models import ArtifactRecord, TaskRecord
from lab_sidecar.core.paths import resolve_workspace_path, to_manifest_path
from lab_sidecar.core.traceability import refresh_traceability
from lab_sidecar.figures.render import render_figure
from lab_sidecar.figures.specs import (
    FigurePlan,
    FigureSpec,
    FigureSpecValidationError,
    build_auto_figure_plan,
    build_explicit_figure_plan,
    parse_explicit_spec,
)
from lab_sidecar.storage.sqlite_index import upsert_task


class MetricsNotReadyError(RuntimeError):
    pass


class FigureSpecLoadError(RuntimeError):
    pass


class NoFiguresGeneratedError(RuntimeError):
    def __init__(
        self,
        message: str,
        warnings: list[str],
        skipped_candidates: list[dict[str, str]] | None = None,
        errors: list[str] | None = None,
    ):
        super().__init__(message)
        self.warnings = warnings
        self.skipped_candidates = skipped_candidates or []
        self.errors = errors or []


@dataclass
class GeneratedFigure:
    spec: FigureSpec
    png_path: Path
    svg_path: Path


@dataclass
class FigureGenerationResult:
    record: TaskRecord
    generated: list[GeneratedFigure]
    warnings: list[str]
    skipped_candidates: list[dict[str, str]]
    errors: list[str]
    spec_path: Path
    summary_path: Path


class FigureGenerationService:
    def __init__(self, root: Path):
        self.root = root.resolve()

    def generate(self, task_id: str, spec_path: Path | None = None) -> FigureGenerationResult:
        record = load_task(self.root, task_id)
        task_path = resolve_workspace_path(record.paths.task_dir, self.root)
        explicit_spec = self._load_explicit_spec(task_path, spec_path) if spec_path else None

        metrics_path = task_path / "metrics" / "normalized_metrics.csv"
        if not metrics_path.exists():
            raise MetricsNotReadyError("metrics/normalized_metrics.csv is missing")

        figures_dir = task_path / "figures"
        figures_dir.mkdir(parents=True, exist_ok=True)
        output_spec_path = figures_dir / "figure-spec.yaml"
        summary_path = figures_dir / "figure-summary.json"

        df = self._read_metrics(metrics_path)
        metrics_metadata = _read_metrics_summary(task_path)
        plan = self._build_plan(df, explicit_spec, metrics_metadata)
        if not plan.specs:
            summary = self._build_summary(
                record=record,
                generated=[],
                warnings=plan.warnings,
                skipped_candidates=plan.skipped_candidates,
                errors=plan.errors,
                metrics_path=metrics_path,
                spec_input_path=spec_path,
                metrics_metadata=metrics_metadata,
            )
            _write_json(summary_path, summary)
            self._upsert_summary_artifact(record, summary_path, metrics_path)
            record.updated_at = _now_iso()
            record = refresh_traceability(self.root, record)
            write_manifest(manifest_path(self.root, task_id), record)
            upsert_task(self.root, record)
            raise NoFiguresGeneratedError(
                "no supported chart could be generated",
                plan.warnings,
                skipped_candidates=plan.skipped_candidates,
                errors=plan.errors,
            )

        generated: list[GeneratedFigure] = []
        warnings = list(plan.warnings)
        skipped_candidates = list(plan.skipped_candidates)
        errors = list(plan.errors)
        for spec in plan.specs:
            try:
                png_path, svg_path = render_figure(df, spec, task_path)
            except Exception as exc:
                error = f"Failed to render {spec.figure_id}: {exc}"
                warnings.append(error)
                errors.append(error)
                skipped_candidates.append(
                    {
                        "figure_id": spec.figure_id,
                        "chart_type": spec.chart_type,
                        "x": spec.x,
                        "y": spec.y,
                        "reason": error,
                    }
                )
                continue
            generated.append(GeneratedFigure(spec=spec, png_path=png_path, svg_path=svg_path))

        if not generated:
            summary = self._build_summary(
                record=record,
                generated=[],
                warnings=warnings,
                skipped_candidates=skipped_candidates,
                errors=errors,
                metrics_path=metrics_path,
                spec_input_path=spec_path,
                metrics_metadata=metrics_metadata,
            )
            _write_json(summary_path, summary)
            self._upsert_summary_artifact(record, summary_path, metrics_path)
            record.updated_at = _now_iso()
            record = refresh_traceability(self.root, record)
            write_manifest(manifest_path(self.root, task_id), record)
            upsert_task(self.root, record)
            raise NoFiguresGeneratedError(
                "all planned figures failed to render",
                warnings,
                skipped_candidates=skipped_candidates,
                errors=errors,
            )

        _write_yaml(
            output_spec_path,
            {
                "schema_version": "1",
                "task_id": record.task_id,
                "generated_at": _now_iso(),
                "source_metrics": to_manifest_path(metrics_path, self.root),
                "spec_input_path": to_manifest_path(spec_path, self.root) if spec_path else None,
                "units": metrics_metadata["units"],
                "groups": metrics_metadata["groups"],
                "figures": [item.spec.to_dict() for item in generated],
                "warnings": warnings,
                "skipped_candidates": skipped_candidates,
                "errors": errors,
            },
        )
        summary = self._build_summary(
            record=record,
            generated=generated,
            warnings=warnings,
            skipped_candidates=skipped_candidates,
            errors=errors,
            metrics_path=metrics_path,
            spec_input_path=spec_path,
            metrics_metadata=metrics_metadata,
        )
        _write_json(summary_path, summary)

        self._upsert_artifacts(record, generated, output_spec_path, summary_path, metrics_path)
        record.updated_at = _now_iso()
        record = refresh_traceability(self.root, record)
        write_manifest(manifest_path(self.root, task_id), record)
        upsert_task(self.root, record)
        return FigureGenerationResult(
            record=record,
            generated=generated,
            warnings=warnings,
            skipped_candidates=skipped_candidates,
            errors=errors,
            spec_path=output_spec_path,
            summary_path=summary_path,
        )

    def _load_explicit_spec(self, task_path: Path, spec_path: Path) -> FigureSpec:
        resolved_spec_path = spec_path.resolve()
        if not resolved_spec_path.exists():
            raise FigureSpecLoadError(f"spec file does not exist: {spec_path}")
        try:
            spec_data = yaml.safe_load(resolved_spec_path.read_text(encoding="utf-8"))
        except yaml.YAMLError as exc:
            raise FigureSpecLoadError(f"spec YAML could not be parsed: {exc}") from exc
        except OSError as exc:
            raise FigureSpecLoadError(f"spec file could not be read: {exc}") from exc

        try:
            return parse_explicit_spec(spec_data, task_path)
        except FigureSpecValidationError as exc:
            raise FigureSpecLoadError(str(exc)) from exc

    def _build_plan(
        self,
        df: pd.DataFrame,
        explicit_spec: FigureSpec | None,
        metrics_metadata: dict[str, dict[str, str]],
    ) -> FigurePlan:
        if explicit_spec is None:
            return build_auto_figure_plan(
                df,
                units=metrics_metadata["units"],
                groups=metrics_metadata["groups"],
            )
        return build_explicit_figure_plan(df, explicit_spec, units=metrics_metadata["units"])

    def _read_metrics(self, metrics_path: Path) -> pd.DataFrame:
        try:
            df = pd.read_csv(metrics_path)
        except pd.errors.EmptyDataError as exc:
            raise MetricsNotReadyError("metrics/normalized_metrics.csv is empty") from exc
        if df.empty:
            raise MetricsNotReadyError("metrics/normalized_metrics.csv is empty")
        return df

    def _build_summary(
        self,
        record: TaskRecord,
        generated: list[GeneratedFigure],
        warnings: list[str],
        skipped_candidates: list[dict[str, str]],
        errors: list[str],
        metrics_path: Path,
        spec_input_path: Path | None,
        metrics_metadata: dict[str, dict[str, str]],
    ) -> dict[str, Any]:
        generated_figures = [
            {
                "figure_id": item.spec.figure_id,
                "chart_type": item.spec.chart_type,
                "png_path": to_manifest_path(item.png_path, self.root),
                "svg_path": to_manifest_path(item.svg_path, self.root),
                "source_metrics": to_manifest_path(metrics_path, self.root),
                "x": item.spec.x,
                "y": item.spec.y,
                "group_by": item.spec.group_by,
                "units": dict(item.spec.units),
            }
            for item in generated
        ]
        return {
            "schema_version": "1",
            "task_id": record.task_id,
            "task_status": record.status.value,
            "generated_at": _now_iso(),
            "metrics_path": to_manifest_path(metrics_path, self.root),
            "spec_path": to_manifest_path(spec_input_path, self.root) if spec_input_path else None,
            "source_metrics": to_manifest_path(metrics_path, self.root),
            "spec_input_path": to_manifest_path(spec_input_path, self.root) if spec_input_path else None,
            "units": metrics_metadata["units"],
            "groups": metrics_metadata["groups"],
            "figure_count": len(generated),
            "figures": [
                {
                    "figure_id": item.spec.figure_id,
                    "chart_type": item.spec.chart_type,
                    "png": to_manifest_path(item.png_path, self.root),
                    "svg": to_manifest_path(item.svg_path, self.root),
                    "x": item.spec.x,
                    "y": item.spec.y,
                    "group_by": item.spec.group_by,
                    "units": dict(item.spec.units),
                }
                for item in generated
            ],
            "generated_figures": generated_figures,
            "skipped_candidates": skipped_candidates,
            "warnings": warnings,
            "errors": errors,
        }

    def _upsert_artifacts(
        self,
        record: TaskRecord,
        generated: list[GeneratedFigure],
        spec_path: Path,
        summary_path: Path,
        metrics_path: Path,
    ) -> None:
        source_paths = [to_manifest_path(metrics_path, self.root)]
        for item in generated:
            _upsert_artifact(
                record,
                ArtifactRecord(
                    artifact_id=f"figure_{item.spec.figure_id}_png",
                    type="figure",
                    path=to_manifest_path(item.png_path, self.root),
                    description=item.spec.title,
                    source_paths=source_paths,
                ),
            )
            _upsert_artifact(
                record,
                ArtifactRecord(
                    artifact_id=f"figure_{item.spec.figure_id}_svg",
                    type="figure",
                    path=to_manifest_path(item.svg_path, self.root),
                    description=item.spec.title,
                    source_paths=source_paths,
                ),
            )
        _upsert_artifact(
            record,
            ArtifactRecord(
                artifact_id="figures_spec",
                type="config",
                path=to_manifest_path(spec_path, self.root),
                description="Figure generation specification",
                source_paths=source_paths,
            ),
        )
        self._upsert_summary_artifact(record, summary_path, metrics_path)

    def _upsert_summary_artifact(
        self,
        record: TaskRecord,
        summary_path: Path,
        metrics_path: Path,
    ) -> None:
        _upsert_artifact(
            record,
            ArtifactRecord(
                artifact_id="figures_summary",
                type="config",
                path=to_manifest_path(summary_path, self.root),
                description="Figure generation summary and warnings",
                source_paths=[to_manifest_path(metrics_path, self.root)],
            ),
        )


def _upsert_artifact(record: TaskRecord, artifact: ArtifactRecord) -> None:
    record.artifacts = [item for item in record.artifacts if item.artifact_id != artifact.artifact_id]
    record.artifacts.append(artifact)


def _write_yaml(path: Path, data: dict[str, Any]) -> None:
    path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")


def _write_json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _read_metrics_summary(task_path: Path) -> dict[str, dict[str, str]]:
    path = task_path / "metrics" / "collection-summary.json"
    empty = {"units": {}, "groups": {}}
    if not path.exists():
        return empty
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return empty
    units = data.get("units")
    groups = data.get("groups")
    return {
        "units": {str(key): str(value) for key, value in units.items()} if isinstance(units, dict) else {},
        "groups": {str(key): str(value) for key, value in groups.items()} if isinstance(groups, dict) else {},
    }


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
