from __future__ import annotations

import json
import shutil
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

import pandas as pd
import yaml

from lab_sidecar.core.artifacts import upsert_artifact
from lab_sidecar.core.manifest import load_task, manifest_path, write_manifest
from lab_sidecar.core.models import ArtifactRecord, TaskRecord
from lab_sidecar.core.paths import resolve_workspace_path, to_manifest_path
from lab_sidecar.core.provenance import file_provenance
from lab_sidecar.core.traceability import refresh_traceability
from lab_sidecar.figures.render import render_figure
from lab_sidecar.figures.specs import (
    ExplicitFigureSpecBundle,
    FigurePlan,
    FigureOutput,
    FigureSpec,
    FigureSpecValidationError,
    build_auto_figure_plan,
    build_explicit_figure_plan,
    parse_explicit_specs,
)
from lab_sidecar.figures.fallback_worker import (
    FallbackWorkerMode,
    FigureFallbackProposal,
    FigureFallbackWorkerRequest,
    configured_fallback_worker,
    validate_fallback_output,
    worker_output_display_paths,
    write_worker_request,
    write_worker_result,
)
from lab_sidecar.intelligence.paths import create_worker_run_dirs, generate_worker_run_id, sandbox_dir, worker_run_dir
from lab_sidecar.intelligence.schemas import ValidatorCheck, ValidatorResult
from lab_sidecar.storage.sqlite_index import upsert_task


class MetricsNotReadyError(RuntimeError):
    pass


class FigureSpecLoadError(RuntimeError):
    pass


FallbackMode = Literal["off", "bounded"]


class NoFiguresGeneratedError(RuntimeError):
    def __init__(
        self,
        message: str,
        warnings: list[str],
        skipped_candidates: list[dict[str, str]] | None = None,
        errors: list[str] | None = None,
        summary_path: Path | None = None,
        unsupported_chart_diagnostics: list[dict[str, Any]] | None = None,
        fallback: dict[str, Any] | None = None,
    ):
        super().__init__(message)
        self.warnings = warnings
        self.skipped_candidates = skipped_candidates or []
        self.errors = errors or []
        self.summary_path = summary_path
        self.unsupported_chart_diagnostics = unsupported_chart_diagnostics or []
        self.fallback = fallback or {}


@dataclass
class GeneratedFigure:
    spec: FigureSpec
    png_path: Path
    svg_path: Path
    source: Literal["deterministic", "fallback"] = "deterministic"
    worker_run_id: str | None = None
    validation_status: str | None = None
    validation_checks: list[dict[str, Any]] | None = None
    field_sources: dict[str, list[str]] | None = None
    fallback_lineage: dict[str, Any] | None = None


@dataclass
class FigureGenerationResult:
    record: TaskRecord
    generated: list[GeneratedFigure]
    warnings: list[str]
    skipped_candidates: list[dict[str, str]]
    errors: list[str]
    spec_path: Path
    summary_path: Path
    fallback: dict[str, Any]


class FigureGenerationService:
    def __init__(self, root: Path):
        self.root = root.resolve()

    def generate(
        self,
        task_id: str,
        spec_path: Path | None = None,
        fallback_mode: FallbackMode = "off",
        fallback_worker_mode: FallbackWorkerMode = "unavailable",
    ) -> FigureGenerationResult:
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
        fallback = self._fallback_summary(mode=fallback_mode)
        if not plan.specs:
            fallback, fallback_generated = self._prepare_fallback(
                record=record,
                task_path=task_path,
                spec=_fallback_spec(explicit_spec),
                metrics_path=metrics_path,
                metrics_metadata=metrics_metadata,
                plan=plan,
                fallback_mode=fallback_mode,
                fallback_worker_mode=fallback_worker_mode,
            )
            if fallback_generated:
                _write_yaml(
                    output_spec_path,
                    self._build_output_spec_payload(
                        record=record,
                        generated=fallback_generated,
                        warnings=plan.warnings,
                        skipped_candidates=plan.skipped_candidates,
                        errors=plan.errors,
                        metrics_path=metrics_path,
                        spec_input_path=spec_path,
                        metrics_metadata=metrics_metadata,
                        fallback=fallback,
                    ),
                )
                summary = self._build_summary(
                    record=record,
                    generated=fallback_generated,
                    warnings=plan.warnings,
                    skipped_candidates=plan.skipped_candidates,
                    errors=plan.errors,
                    metrics_path=metrics_path,
                    spec_input_path=spec_path,
                    metrics_metadata=metrics_metadata,
                    unsupported_chart_diagnostics=plan.unsupported_chart_diagnostics,
                    fallback=fallback,
                )
                _write_json(summary_path, summary)
                self._upsert_artifacts(record, fallback_generated, output_spec_path, summary_path, metrics_path)
                record.updated_at = _now_iso()
                record = refresh_traceability(self.root, record)
                write_manifest(manifest_path(self.root, task_id), record)
                upsert_task(self.root, record)
                return FigureGenerationResult(
                    record=record,
                    generated=fallback_generated,
                    warnings=plan.warnings,
                    skipped_candidates=plan.skipped_candidates,
                    errors=plan.errors,
                    spec_path=output_spec_path,
                    summary_path=summary_path,
                    fallback=fallback,
                )
            summary = self._build_summary(
                record=record,
                generated=[],
                warnings=plan.warnings,
                skipped_candidates=plan.skipped_candidates,
                errors=plan.errors,
                metrics_path=metrics_path,
                spec_input_path=spec_path,
                metrics_metadata=metrics_metadata,
                unsupported_chart_diagnostics=plan.unsupported_chart_diagnostics,
                fallback=fallback,
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
                summary_path=summary_path,
                unsupported_chart_diagnostics=plan.unsupported_chart_diagnostics,
                fallback=fallback,
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
                unsupported_chart_diagnostics=plan.unsupported_chart_diagnostics,
                fallback=fallback,
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
                summary_path=summary_path,
                unsupported_chart_diagnostics=plan.unsupported_chart_diagnostics,
                fallback=fallback,
            )

        _write_yaml(
            output_spec_path,
            self._build_output_spec_payload(
                record=record,
                generated=generated,
                warnings=warnings,
                skipped_candidates=skipped_candidates,
                errors=errors,
                metrics_path=metrics_path,
                spec_input_path=spec_path,
                metrics_metadata=metrics_metadata,
                fallback=fallback,
            ),
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
            unsupported_chart_diagnostics=plan.unsupported_chart_diagnostics,
            fallback=fallback,
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
            fallback=fallback,
        )

    def _load_explicit_spec(self, task_path: Path, spec_path: Path) -> ExplicitFigureSpecBundle:
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
            return parse_explicit_specs(spec_data, task_path)
        except FigureSpecValidationError as exc:
            raise FigureSpecLoadError(str(exc)) from exc

    def _build_plan(
        self,
        df: pd.DataFrame,
        explicit_spec: ExplicitFigureSpecBundle | None,
        metrics_metadata: dict[str, Any],
    ) -> FigurePlan:
        if explicit_spec is None:
            return build_auto_figure_plan(
                df,
                units=metrics_metadata["units"],
                groups=metrics_metadata["groups"],
            )
        return build_explicit_figure_plan(
            df,
            explicit_spec.specs,
            units=metrics_metadata["units"],
            warnings=explicit_spec.warnings,
            skipped_candidates=explicit_spec.skipped_candidates,
            errors=explicit_spec.errors,
        )

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
        metrics_metadata: dict[str, Any],
        unsupported_chart_diagnostics: list[dict[str, Any]],
        fallback: dict[str, Any],
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
                "field_sources": item.field_sources
                if item.field_sources is not None
                else _figure_field_sources(item.spec, metrics_metadata["field_sources"]),
                "source": item.source,
                "worker_run_id": item.worker_run_id,
                "validation_status": item.validation_status,
                "validation_checks": item.validation_checks or [],
                "fallback_lineage": item.fallback_lineage or {},
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
            "field_sources": metrics_metadata["field_sources"],
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
                    "field_sources": item.field_sources
                    if item.field_sources is not None
                    else _figure_field_sources(item.spec, metrics_metadata["field_sources"]),
                    "source": item.source,
                    "worker_run_id": item.worker_run_id,
                    "validation_status": item.validation_status,
                    "validation_checks": item.validation_checks or [],
                    "fallback_lineage": item.fallback_lineage or {},
                }
                for item in generated
            ],
            "generated_figures": generated_figures,
            "unsupported_chart_diagnostics": unsupported_chart_diagnostics,
            "skipped_candidates": skipped_candidates,
            "warnings": warnings,
            "errors": errors,
            "fallback": fallback,
        }

    def _fallback_summary(self, mode: FallbackMode) -> dict[str, Any]:
        return {
            "mode": mode,
            "attempted": False,
            "worker_run_id": None,
            "status": "not_needed",
            "request_path": None,
            "validator_result_path": None,
            "adoption_record_path": None,
            "validation_status": None,
            "validation_checks": [],
            "adopted_figures": [],
            "adopted_artifact_paths": [],
            "diagnostics": [],
        }

    def _build_output_spec_payload(
        self,
        record: TaskRecord,
        generated: list[GeneratedFigure],
        warnings: list[str],
        skipped_candidates: list[dict[str, str]],
        errors: list[str],
        metrics_path: Path,
        spec_input_path: Path | None,
        metrics_metadata: dict[str, Any],
        fallback: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "schema_version": "1",
            "task_id": record.task_id,
            "generated_at": _now_iso(),
            "source_metrics": to_manifest_path(metrics_path, self.root),
            "spec_input_path": to_manifest_path(spec_input_path, self.root) if spec_input_path else None,
            "units": metrics_metadata["units"],
            "groups": metrics_metadata["groups"],
            "field_sources": metrics_metadata["field_sources"],
            "figures": [
                {
                    **item.spec.to_dict(),
                    "source": item.source,
                    "worker_run_id": item.worker_run_id,
                    "validation_status": item.validation_status,
                }
                for item in generated
            ],
            "warnings": warnings,
            "skipped_candidates": skipped_candidates,
            "errors": errors,
            "fallback": fallback,
        }

    def _prepare_fallback(
        self,
        record: TaskRecord,
        task_path: Path,
        spec: FigureSpec | None,
        metrics_path: Path,
        metrics_metadata: dict[str, Any],
        plan: FigurePlan,
        fallback_mode: FallbackMode,
        fallback_worker_mode: FallbackWorkerMode,
    ) -> tuple[dict[str, Any], list[GeneratedFigure]]:
        fallback = self._fallback_summary(mode=fallback_mode)
        if not plan.unsupported_chart_diagnostics:
            return fallback, []
        if fallback_mode == "off":
            fallback["diagnostics"] = [
                "Unsupported chart intent was diagnosed, but fallback mode is off. Re-run with `--fallback bounded` to write a bounded figure request."
            ]
            return fallback, []

        worker_run_id = generate_worker_run_id()
        run_dir = create_worker_run_dirs(self.root, record.task_id, worker_run_id)
        request_path = run_dir / "figure-request.json"
        validator_path = run_dir / "validator-result.json"
        bundle = self._build_figure_request(
            record=record,
            task_path=task_path,
            spec=spec,
            metrics_path=metrics_path,
            metrics_metadata=metrics_metadata,
            plan=plan,
        )
        _write_json(request_path, bundle)
        worker = configured_fallback_worker(fallback_worker_mode)
        if worker is None:
            validator = self._write_unavailable_worker_result(record.task_id, worker_run_id, task_path, request_path)
            fallback.update(
                {
                    "attempted": True,
                    "worker_run_id": worker_run_id,
                    "status": "unavailable",
                    "request_path": _task_relative_path(request_path, task_path),
                    "validator_result_path": _task_relative_path(validator_path, task_path),
                    "adoption_record_path": None,
                    "validation_status": "rejected",
                    "validation_checks": [check.model_dump(mode="json") for check in validator.checks],
                    "diagnostics": list(validator.diagnostics),
                }
            )
            return fallback, []

        sandbox_path = sandbox_dir(self.root, record.task_id, worker_run_id)
        request = FigureFallbackWorkerRequest(
            task_id=record.task_id,
            worker_run_id=worker_run_id,
            worker_type=worker.worker_type,
            figure_request_path=_task_relative_path(request_path, task_path),
            sandbox_path=_task_relative_path(sandbox_path, task_path),
            requested_chart_intent=bundle.get("requested_chart_intent")
            if isinstance(bundle.get("requested_chart_intent"), dict)
            else None,
            available_fields=[str(field) for field in bundle.get("available_fields", []) if isinstance(field, str)],
            row_count=bundle.get("row_count") if isinstance(bundle.get("row_count"), int) else None,
        )
        worker_request_path = run_dir / "worker-request.json"
        worker_result_path = run_dir / "worker-result.json"
        write_worker_request(worker_request_path, request)
        worker_result = worker.run(request, bundle, sandbox_path)
        write_worker_result(worker_result_path, worker_result)
        validation = validate_fallback_output(
            task_id=record.task_id,
            worker_run_id=worker_run_id,
            sandbox_path=sandbox_path,
            figure_request=bundle,
            worker_result=worker_result,
        )
        validator = validation.validator
        fallback_generated: list[GeneratedFigure] = []
        adoption_record_path: Path | None = None
        if validator.accepted:
            try:
                fallback_generated, adoption_record_path = self._adopt_fallback_output(
                    record=record,
                    task_path=task_path,
                    metrics_path=metrics_path,
                    metrics_metadata=metrics_metadata,
                    worker_run_id=worker_run_id,
                    run_dir=run_dir,
                    request_path=request_path,
                    worker_request_path=worker_request_path,
                    worker_result_path=worker_result_path,
                    validator_path=validator_path,
                    validation=validation,
                )
                validator.adopted_config_path = "figures/figure-spec.yaml"
            except Exception as exc:
                validator.accepted = False
                validator.checks.append(
                    ValidatorCheck(
                        name="adoption",
                        status="failed",
                        message=f"validated fallback output could not be adopted: {exc}",
                    )
                )
                validator.diagnostics.append(f"figure_fallback_adoption_error: {exc}")
                fallback_generated = []
                adoption_record_path = None
        _write_json(validator_path, validator.model_dump(mode="json"))
        self._write_worker_diagnostics(
            task_path=task_path,
            run_dir=run_dir,
            request_path=request_path,
            worker_request_path=worker_request_path,
            worker_result_path=worker_result_path,
            validator=validator,
            adoption_record_path=adoption_record_path,
        )
        status = "adopted" if validator.accepted else "rejected"
        fallback.update(
            {
                "attempted": True,
                "worker_run_id": worker_run_id,
                "worker_type": worker.worker_type,
                "status": status,
                "request_path": _task_relative_path(request_path, task_path),
                "worker_request_path": _task_relative_path(worker_request_path, task_path),
                "worker_result_path": _task_relative_path(worker_result_path, task_path),
                "validator_result_path": _task_relative_path(validator_path, task_path),
                "adoption_record_path": _task_relative_path(adoption_record_path, task_path)
                if adoption_record_path
                else None,
                "proposal_path": (
                    _task_relative_path(sandbox_path / worker_result.proposal_path, task_path)
                    if worker_result.proposal_path
                    else None
                ),
                "sandbox_artifact_paths": worker_output_display_paths(
                    task_path,
                    sandbox_path,
                    worker_result.artifact_paths,
                ),
                "validation_status": "accepted" if validator.accepted else "rejected",
                "validation_checks": [check.model_dump(mode="json") for check in validator.checks],
                "adopted_figures": [
                    {
                        "figure_id": item.spec.figure_id,
                        "chart_type": item.spec.chart_type,
                        "png": to_manifest_path(item.png_path, self.root),
                        "svg": to_manifest_path(item.svg_path, self.root),
                        "source_metrics": to_manifest_path(metrics_path, self.root),
                        "fields_used": _figure_fields(item.spec),
                        "field_sources": item.field_sources or {},
                    }
                    for item in fallback_generated
                ],
                "adopted_artifact_paths": [
                    to_manifest_path(path, self.root)
                    for item in fallback_generated
                    for path in [item.png_path, item.svg_path]
                ],
                "diagnostics": list(validator.diagnostics),
            }
        )
        return fallback, fallback_generated

    def _adopt_fallback_output(
        self,
        record: TaskRecord,
        task_path: Path,
        metrics_path: Path,
        metrics_metadata: dict[str, Any],
        worker_run_id: str,
        run_dir: Path,
        request_path: Path,
        worker_request_path: Path,
        worker_result_path: Path,
        validator_path: Path,
        validation,
    ) -> tuple[list[GeneratedFigure], Path]:
        proposal = validation.proposal
        if not isinstance(proposal, FigureFallbackProposal):
            raise ValueError("accepted fallback validation did not include a proposal")
        if validation.sandbox_png_path is None or validation.sandbox_svg_path is None:
            raise ValueError("accepted fallback validation did not include sandbox PNG/SVG paths")

        official_png_path, official_svg_path = _fallback_official_paths(task_path, proposal)
        official_png_path.parent.mkdir(parents=True, exist_ok=True)
        copied_paths: list[Path] = []
        adoption_record_path = run_dir / "adoption-record.json"
        try:
            shutil.copy2(validation.sandbox_png_path, official_png_path)
            copied_paths.append(official_png_path)
            shutil.copy2(validation.sandbox_svg_path, official_svg_path)
            copied_paths.append(official_svg_path)

            figure = _fallback_generated_figure(
                root=self.root,
                task_path=task_path,
                metrics_path=metrics_path,
                metrics_metadata=metrics_metadata,
                proposal=proposal,
                worker_run_id=worker_run_id,
                png_path=official_png_path,
                svg_path=official_svg_path,
                request_path=request_path,
                worker_request_path=worker_request_path,
                worker_result_path=worker_result_path,
                validator_path=validator_path,
                sandbox_png_path=validation.sandbox_png_path,
                sandbox_svg_path=validation.sandbox_svg_path,
                validation_checks=[check.model_dump(mode="json") for check in validation.validator.checks],
            )
            _write_json(
                adoption_record_path,
                _fallback_adoption_record(
                    root=self.root,
                    record=record,
                    task_path=task_path,
                    metrics_path=metrics_path,
                    proposal=proposal,
                    worker_run_id=worker_run_id,
                    request_path=request_path,
                    worker_request_path=worker_request_path,
                    worker_result_path=worker_result_path,
                    validator_path=validator_path,
                    sandbox_png_path=validation.sandbox_png_path,
                    sandbox_svg_path=validation.sandbox_svg_path,
                    official_png_path=official_png_path,
                    official_svg_path=official_svg_path,
                    generated_figure=figure,
                    validation_checks=[check.model_dump(mode="json") for check in validation.validator.checks],
                ),
            )
        except Exception:
            for path in [*copied_paths, adoption_record_path]:
                try:
                    path.unlink()
                except FileNotFoundError:
                    pass
            raise
        return [figure], adoption_record_path

    def _build_figure_request(
        self,
        record: TaskRecord,
        task_path: Path,
        spec: FigureSpec | None,
        metrics_path: Path,
        metrics_metadata: dict[str, Any],
        plan: FigurePlan,
    ) -> dict[str, Any]:
        collection_summary = _read_json(task_path / "metrics" / "collection-summary.json")
        diagnostics = plan.unsupported_chart_diagnostics[0] if plan.unsupported_chart_diagnostics else {}
        artifact_entry = _safe_artifact_entry(
            metrics_path,
            artifact_id="metrics_normalized_csv",
            display_path=to_manifest_path(metrics_path, self.root),
        )
        output_files = collection_summary.get("output_files")
        return {
            "schema_version": "1",
            "task_id": record.task_id,
            "task_status": record.status.value,
            "task_mode": record.mode,
            "generated_at": _now_iso(),
            "requested_chart_intent": diagnostics.get("requested_chart_intent")
            or _spec_chart_intent(spec),
            "metric_columns": list(_read_csv_columns(metrics_path)),
            "row_count": _read_csv_row_count(metrics_path),
            "units": metrics_metadata["units"],
            "groups": metrics_metadata["groups"],
            "field_sources": metrics_metadata["field_sources"],
            "available_fields": diagnostics.get("available_fields") or list(_read_csv_columns(metrics_path)),
            "warnings": list(plan.warnings),
            "errors": list(plan.errors),
            "skipped_candidates": list(plan.skipped_candidates),
            "unsupported_chart_diagnostics": list(plan.unsupported_chart_diagnostics),
            "artifacts": [artifact_entry] if artifact_entry else [],
            "collection_diagnostics": {
                "summary_path": "metrics/collection-summary.json" if collection_summary else None,
                "warnings": collection_summary.get("warnings") or [],
                "diagnostics": collection_summary.get("diagnostics") or [],
                "unit_diagnostics": collection_summary.get("unit_diagnostics") or [],
                "processed_files": _bounded_processed_files(collection_summary.get("processed_files")),
                "skipped_files": _bounded_skipped_files(collection_summary.get("skipped_files")),
                "output_files": output_files if isinstance(output_files, list) else [],
            },
            "omitted": {
                "raw_rows": "full normalized metrics rows omitted",
                "raw_logs": "stdout/stderr bodies omitted",
                "raw_source_bodies": "raw source file bodies omitted",
                "report_bodies": "report Markdown bodies omitted",
                "pptx_internals": "slide deck internals omitted",
                "worker_transcripts": "worker prompt/response bodies omitted",
                "artifact_bodies": "artifact file bodies omitted",
            },
        }

    def _write_unavailable_worker_result(
        self,
        task_id: str,
        worker_run_id: str,
        task_path: Path,
        request_path: Path,
    ) -> ValidatorResult:
        request_display_path = _task_relative_path(request_path, task_path)
        result = ValidatorResult(
            accepted=False,
            proposal_type="figure",
            checks=[
                ValidatorCheck(
                    name="worker_available",
                    status="failed",
                    message="No Alpha4 chart fallback worker is configured; only bounded figure-request diagnostics were recorded.",
                )
            ],
            diagnostics=[
                "figure_fallback_unavailable: no chart worker is configured.",
                f"figure_request_recorded: {request_display_path}",
            ],
        )
        run_dir = worker_run_dir(self.root, task_id, worker_run_id)
        run_dir.mkdir(parents=True, exist_ok=True)
        _write_json(run_dir / "validator-result.json", result.model_dump(mode="json"))
        diagnostics_lines = [
            "# Lab-Sidecar Figure Fallback Diagnostics",
            "",
            "- figure fallback worker status: unavailable",
            f"- figure request: {request_display_path}",
            "- no worker prompt, response, proposal, or adopted figure artifact was produced.",
        ]
        (run_dir / "diagnostics.md").write_text("\n".join(diagnostics_lines) + "\n", encoding="utf-8")
        return result

    def _write_worker_diagnostics(
        self,
        task_path: Path,
        run_dir: Path,
        request_path: Path,
        worker_request_path: Path,
        worker_result_path: Path,
        validator: ValidatorResult,
        adoption_record_path: Path | None = None,
    ) -> None:
        status = "adopted" if validator.accepted else "rejected"
        lines = [
            "# Lab-Sidecar Figure Fallback Diagnostics",
            "",
            f"- figure fallback proposal status: {status}",
            f"- figure request: {_task_relative_path(request_path, task_path)}",
            f"- worker request: {_task_relative_path(worker_request_path, task_path)}",
            f"- worker result: {_task_relative_path(worker_result_path, task_path)}",
            f"- validator result: {_task_relative_path(run_dir / 'validator-result.json', task_path)}",
        ]
        if adoption_record_path is not None:
            lines.append(f"- adoption record: {_task_relative_path(adoption_record_path, task_path)}")
            lines.append("- accepted sandbox outputs were copied into official figures/ after validation.")
        else:
            lines.append("- no fallback proposal was adopted into official figures.")
        if validator.diagnostics:
            lines.append("")
            lines.append("## Diagnostics")
            lines.extend(f"- {item}" for item in validator.diagnostics)
        (run_dir / "diagnostics.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

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
            upsert_artifact(
                record,
                ArtifactRecord(
                    artifact_id=f"figure_{item.spec.figure_id}_png",
                    type="figure",
                    path=to_manifest_path(item.png_path, self.root),
                    description=item.spec.title,
                    source_paths=source_paths,
                ),
            )
            upsert_artifact(
                record,
                ArtifactRecord(
                    artifact_id=f"figure_{item.spec.figure_id}_svg",
                    type="figure",
                    path=to_manifest_path(item.svg_path, self.root),
                    description=item.spec.title,
                    source_paths=source_paths,
                ),
            )
        upsert_artifact(
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
        upsert_artifact(
            record,
            ArtifactRecord(
                artifact_id="figures_summary",
                type="config",
                path=to_manifest_path(summary_path, self.root),
                description="Figure generation summary and warnings",
                source_paths=[to_manifest_path(metrics_path, self.root)],
            ),
        )



def _write_yaml(path: Path, data: dict[str, Any]) -> None:
    path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")


def _write_json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _read_metrics_summary(task_path: Path) -> dict[str, Any]:
    path = task_path / "metrics" / "collection-summary.json"
    empty = {"units": {}, "groups": {}, "field_sources": {}}
    if not path.exists():
        return empty
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return empty
    units = data.get("units")
    groups = data.get("groups")
    field_sources = data.get("matched_source_fields")
    return {
        "units": {str(key): str(value) for key, value in units.items()} if isinstance(units, dict) else {},
        "groups": {str(key): str(value) for key, value in groups.items()} if isinstance(groups, dict) else {},
        "field_sources": _string_list_mapping(field_sources),
    }


def _figure_field_sources(spec: FigureSpec, field_sources: dict[str, list[str]]) -> dict[str, list[str]]:
    fields = [spec.x, spec.y]
    if spec.group_by:
        fields.append(spec.group_by)
    return {field: field_sources[field] for field in fields if field in field_sources}


def _figure_fields(spec: FigureSpec) -> list[str]:
    fields = [spec.x, spec.y]
    if spec.group_by:
        fields.append(spec.group_by)
    return fields


def _fallback_official_paths(task_path: Path, proposal: FigureFallbackProposal) -> tuple[Path, Path]:
    figures_dir = (task_path / "figures").resolve()
    safe_id = _safe_artifact_stem(proposal.figure_id)
    png_path = (figures_dir / f"{safe_id}-fallback.png").resolve()
    svg_path = (figures_dir / f"{safe_id}-fallback.svg").resolve()
    _assert_under_directory(png_path, figures_dir, "adopted PNG")
    _assert_under_directory(svg_path, figures_dir, "adopted SVG")
    return png_path, svg_path


def _fallback_generated_figure(
    root: Path,
    task_path: Path,
    metrics_path: Path,
    metrics_metadata: dict[str, Any],
    proposal: FigureFallbackProposal,
    worker_run_id: str,
    png_path: Path,
    svg_path: Path,
    request_path: Path,
    worker_request_path: Path,
    worker_result_path: Path,
    validator_path: Path,
    sandbox_png_path: Path,
    sandbox_svg_path: Path,
    validation_checks: list[dict[str, Any]],
) -> GeneratedFigure:
    spec = FigureSpec(
        figure_id=proposal.figure_id,
        chart_type=proposal.chart_type,
        title=proposal.title,
        x=proposal.x,
        y=proposal.y,
        group_by=proposal.group_by,
        output=FigureOutput(
            png=_task_relative_path(png_path, task_path),
            svg=_task_relative_path(svg_path, task_path),
        ),
        units=_field_units_for_fields(_figure_proposal_fields(proposal), metrics_metadata["units"]),
    )
    field_sources = {
        field: metrics_metadata["field_sources"][field]
        for field in _figure_proposal_fields(proposal)
        if field in metrics_metadata["field_sources"]
    }
    return GeneratedFigure(
        spec=spec,
        png_path=png_path,
        svg_path=svg_path,
        source="fallback",
        worker_run_id=worker_run_id,
        validation_status="accepted",
        validation_checks=validation_checks,
        field_sources=field_sources,
        fallback_lineage={
            "source_metrics": to_manifest_path(metrics_path, root),
            "fields_used": _figure_proposal_fields(proposal),
            "field_sources": field_sources,
            "worker_run_id": worker_run_id,
            "request_path": _task_relative_path(request_path, task_path),
            "worker_request_path": _task_relative_path(worker_request_path, task_path),
            "worker_result_path": _task_relative_path(worker_result_path, task_path),
            "validator_result_path": _task_relative_path(validator_path, task_path),
            "sandbox_png_path": _task_relative_path(sandbox_png_path, task_path),
            "sandbox_svg_path": _task_relative_path(sandbox_svg_path, task_path),
            "adopted_png_path": to_manifest_path(png_path, root),
            "adopted_svg_path": to_manifest_path(svg_path, root),
        },
    )


def _fallback_adoption_record(
    root: Path,
    record: TaskRecord,
    task_path: Path,
    metrics_path: Path,
    proposal: FigureFallbackProposal,
    worker_run_id: str,
    request_path: Path,
    worker_request_path: Path,
    worker_result_path: Path,
    validator_path: Path,
    sandbox_png_path: Path,
    sandbox_svg_path: Path,
    official_png_path: Path,
    official_svg_path: Path,
    generated_figure: GeneratedFigure,
    validation_checks: list[dict[str, Any]],
) -> dict[str, Any]:
    official_artifacts = [
        to_manifest_path(official_png_path, root),
        to_manifest_path(official_svg_path, root),
        "figures/figure-summary.json",
        "figures/figure-spec.yaml",
    ]
    return {
        "schema_version": "1",
        "task_id": record.task_id,
        "worker_run_id": worker_run_id,
        "proposal_type": proposal.proposal_type,
        "adopted_at": _now_iso(),
        "source_metrics": to_manifest_path(metrics_path, root),
        "fields_used": _figure_proposal_fields(proposal),
        "field_sources": generated_figure.field_sources or {},
        "request_path": _task_relative_path(request_path, task_path),
        "worker_request_path": _task_relative_path(worker_request_path, task_path),
        "worker_result_path": _task_relative_path(worker_result_path, task_path),
        "validator_result_path": _task_relative_path(validator_path, task_path),
        "sandbox_artifacts": [
            _task_relative_path(sandbox_png_path, task_path),
            _task_relative_path(sandbox_svg_path, task_path),
        ],
        "official_artifacts": official_artifacts,
        "figure": {
            "figure_id": generated_figure.spec.figure_id,
            "chart_type": generated_figure.spec.chart_type,
            "title": generated_figure.spec.title,
            "x": generated_figure.spec.x,
            "y": generated_figure.spec.y,
            "group_by": generated_figure.spec.group_by,
            "png": to_manifest_path(official_png_path, root),
            "svg": to_manifest_path(official_svg_path, root),
            "source": "fallback",
        },
        "validation": {
            "status": "accepted",
            "checks": validation_checks,
        },
        "omitted": {
            "raw_rows": "full normalized metrics rows omitted",
            "raw_logs": "stdout/stderr bodies omitted",
            "raw_source_bodies": "raw source file bodies omitted",
            "worker_transcripts": "worker prompt/response bodies omitted",
            "artifact_bodies": "artifact file bodies omitted",
        },
    }


def _figure_proposal_fields(proposal: FigureFallbackProposal) -> list[str]:
    fields = [proposal.x, proposal.y]
    if proposal.group_by:
        fields.append(proposal.group_by)
    return fields


def _fallback_spec(bundle: ExplicitFigureSpecBundle | None) -> FigureSpec | None:
    if bundle is None or not bundle.specs:
        return None
    return bundle.specs[0]


def _field_units_for_fields(fields: list[str], units: dict[str, str]) -> dict[str, str]:
    return {field: units[field] for field in fields if field in units}


def _safe_artifact_stem(value: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9_-]+", "_", value).strip("_-")
    if not safe:
        safe = "fallback_figure"
    return safe[:80]


def _assert_under_directory(path: Path, directory: Path, label: str) -> None:
    try:
        path.resolve().relative_to(directory.resolve())
    except ValueError as exc:
        raise ValueError(f"{label} path escapes official figures directory: {path}") from exc


def _string_list_mapping(value: Any) -> dict[str, list[str]]:
    if not isinstance(value, dict):
        return {}
    result: dict[str, list[str]] = {}
    for key, raw_items in value.items():
        if not isinstance(key, str):
            continue
        if not isinstance(raw_items, list):
            continue
        items = [str(item) for item in raw_items if isinstance(item, (str, int, float))]
        if items:
            result[key] = items
    return result


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _read_csv_columns(path: Path) -> list[str]:
    try:
        df = pd.read_csv(path, nrows=0)
    except (OSError, pd.errors.EmptyDataError):
        return []
    return [str(column) for column in df.columns]


def _read_csv_row_count(path: Path) -> int:
    try:
        with path.open("r", encoding="utf-8", newline="") as fh:
            row_count = sum(1 for _ in fh) - 1
    except OSError:
        return 0
    return max(0, row_count)


def _spec_chart_intent(spec: FigureSpec | None) -> dict[str, Any] | None:
    if spec is None:
        return None
    return {
        "figure_id": spec.figure_id,
        "chart_type": spec.chart_type,
        "title": spec.title,
        "x": spec.x,
        "y": spec.y,
        "group_by": spec.group_by,
    }


def _safe_artifact_entry(path: Path, artifact_id: str, display_path: str) -> dict[str, Any] | None:
    if not path.exists() or not path.is_file():
        return None
    provenance = file_provenance(path)
    return {
        "artifact_id": artifact_id,
        "path": display_path,
        "size_bytes": int(provenance["size_bytes"]),
        "sha256": str(provenance["sha256"]),
    }


def _bounded_processed_files(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    items: list[dict[str, Any]] = []
    for entry in value:
        if not isinstance(entry, dict):
            continue
        items.append(
            {
                "source_file": entry.get("source_file"),
                "file_type": entry.get("file_type"),
                "row_count": entry.get("row_count"),
                "detected_fields": entry.get("detected_fields") or [],
                "mapped_fields": entry.get("mapped_fields") or [],
                "matched_source_fields": entry.get("matched_source_fields") or {},
                "source_provenance": entry.get("source_provenance") or {},
            }
        )
    return items


def _bounded_skipped_files(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    items: list[dict[str, Any]] = []
    for entry in value:
        if not isinstance(entry, dict):
            continue
        items.append(
            {
                "source_file": entry.get("source_file"),
                "reason": entry.get("reason"),
                "message": entry.get("message"),
            }
        )
    return items


def _task_relative_path(path: Path, task_path: Path) -> str:
    return path.resolve().relative_to(task_path.resolve()).as_posix()


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
