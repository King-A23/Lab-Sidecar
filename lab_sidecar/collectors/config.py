from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


class MetricsConfigError(ValueError):
    pass


@dataclass(frozen=True)
class FieldMapping:
    target: str
    sources: tuple[str, ...]
    unit: str | None = None

    def to_summary(self) -> dict[str, object]:
        data: dict[str, object] = {
            "target": self.target,
            "sources": list(self.sources),
        }
        if self.unit:
            data["unit"] = self.unit
        return data


@dataclass(frozen=True)
class MetricsCollectionConfig:
    path: Path
    sources: tuple[str, ...] = ()
    exclude_sources: tuple[str, ...] = ()
    field_mappings: tuple[FieldMapping, ...] = ()
    units: dict[str, str] = field(default_factory=dict)
    groups: dict[str, str] = field(default_factory=dict)
    diagnostics: tuple[dict[str, str], ...] = ()

    @property
    def has_explicit_sources(self) -> bool:
        return bool(self.sources)

    @property
    def has_field_mappings(self) -> bool:
        return bool(self.field_mappings)

    def to_summary(self) -> dict[str, object]:
        data: dict[str, object] = {
            "sources": list(self.sources),
            "field_mappings": [item.to_summary() for item in self.field_mappings],
            "units": dict(self.units),
        }
        if self.exclude_sources:
            data["exclude_sources"] = list(self.exclude_sources)
        if self.groups:
            data["groups"] = dict(self.groups)
        if self.diagnostics:
            data["diagnostics"] = list(self.diagnostics)
        return data


def load_metrics_config(path: Path) -> MetricsCollectionConfig:
    resolved = path.resolve()
    if not resolved.exists():
        raise MetricsConfigError(f"metrics config file does not exist: {path}")

    try:
        data = yaml.safe_load(resolved.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise MetricsConfigError(f"metrics config YAML could not be parsed: {exc}") from exc
    except OSError as exc:
        raise MetricsConfigError(f"metrics config file could not be read: {exc}") from exc

    if data is None:
        data = {}
    if not isinstance(data, dict):
        raise MetricsConfigError("metrics config must be a YAML object")

    include_sources, exclude_sources = _parse_sources(data)
    units = _parse_units(data.get("units"))
    field_mappings, diagnostics = _parse_field_mappings(data, units)
    return MetricsCollectionConfig(
        path=resolved,
        sources=tuple(include_sources),
        exclude_sources=tuple(exclude_sources),
        field_mappings=tuple(field_mappings),
        units={mapping.target: mapping.unit for mapping in field_mappings if mapping.unit},
        groups=_parse_groups(data.get("groups")),
        diagnostics=tuple(diagnostics),
    )


def _parse_sources(data: dict[str, Any]) -> tuple[list[str], list[str]]:
    value = data.get("sources", data.get("source_files"))
    if value is None:
        return [], []

    if isinstance(value, str):
        return _parse_source_items([value], "sources"), []
    if isinstance(value, list):
        return _parse_source_items(value, "sources"), []
    if isinstance(value, dict):
        if "include" in value or "exclude" in value:
            include_value = value.get("include")
            exclude_value = value.get("exclude")
            include = _parse_source_items(include_value, "sources.include")
            exclude = _parse_source_items(exclude_value, "sources.exclude")
            if not include:
                raise MetricsConfigError("field 'sources.include' must contain at least one source")
            return include, exclude
        source_value = value.get("path", value.get("glob"))
        if not isinstance(source_value, str):
            raise MetricsConfigError(
                "field 'sources' must be a string, list, or include/exclude object"
            )
        return _parse_source_items([source_value], "sources"), []
    raise MetricsConfigError("field 'sources' must be a string, list, or include/exclude object")


def _parse_source_items(value: Any, field_name: str) -> list[str]:
    if value is None:
        return []
    items: list[Any]
    if isinstance(value, str):
        items = [value]
    elif isinstance(value, list):
        items = value
    else:
        raise MetricsConfigError(f"field '{field_name}' must be a string or list")

    sources: list[str] = []
    for item in items:
        if isinstance(item, str):
            source = item.strip()
        elif isinstance(item, dict):
            source_value = item.get("path", item.get("glob"))
            if not isinstance(source_value, str):
                raise MetricsConfigError("source objects must contain a string 'path' or 'glob'")
            source = source_value.strip()
        else:
            raise MetricsConfigError("source entries must be strings or objects")
        if not source:
            raise MetricsConfigError("source entries must not be empty")
        sources.append(source)
    return sources


def _parse_units(value: Any) -> dict[str, str]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise MetricsConfigError("field 'units' must be an object")

    units: dict[str, str] = {}
    for key, unit in value.items():
        if not isinstance(key, str) or not key.strip():
            raise MetricsConfigError("unit field names must be non-empty strings")
        if not isinstance(unit, str) or not unit.strip():
            raise MetricsConfigError(f"unit for field '{key}' must be a non-empty string")
        units[key.strip()] = unit.strip()
    return units


def _parse_field_mappings(
    data: dict[str, Any],
    units: dict[str, str],
) -> tuple[list[FieldMapping], list[dict[str, str]]]:
    mappings_by_target: dict[str, FieldMapping] = {}
    diagnostics: list[dict[str, str]] = []
    for key in ["fields", "field_mapping", "metrics", "aliases"]:
        value = data.get(key)
        if value is None:
            continue
        if not isinstance(value, dict):
            raise MetricsConfigError(f"field '{key}' must be an object")

        for target, mapping_value in value.items():
            if not isinstance(target, str) or not target.strip():
                raise MetricsConfigError("mapped field names must be non-empty strings")
            target_name = target.strip()
            sources, inline_unit = _parse_mapping_sources(target_name, mapping_value)
            top_level_unit = units.get(target_name)
            if inline_unit and top_level_unit and inline_unit != top_level_unit:
                diagnostics.append(
                    {
                        "reason": "configured_unit_conflict",
                        "field": target_name,
                        "message": (
                            f"Configured unit conflict for '{target_name}': "
                            f"field mapping declares '{inline_unit}' but units declares '{top_level_unit}'."
                        ),
                    }
                )
            unit = inline_unit or top_level_unit
            previous = mappings_by_target.get(target_name)
            if previous and previous.unit and unit and previous.unit != unit:
                diagnostics.append(
                    {
                        "reason": "configured_unit_conflict",
                        "field": target_name,
                        "message": (
                            f"Configured unit conflict for '{target_name}': "
                            f"'{previous.unit}' was replaced by '{unit}'."
                        ),
                    }
                )
            mappings_by_target[target_name] = FieldMapping(
                target=target_name,
                sources=tuple(sources),
                unit=unit,
            )
    return list(mappings_by_target.values()), diagnostics


def _parse_mapping_sources(target: str, value: Any) -> tuple[list[str], str | None]:
    inline_unit: str | None = None
    source_value: Any = value
    if isinstance(value, dict):
        inline_unit_value = value.get("unit")
        if inline_unit_value is not None:
            if not isinstance(inline_unit_value, str) or not inline_unit_value.strip():
                raise MetricsConfigError(f"unit for field '{target}' must be a non-empty string")
            inline_unit = inline_unit_value.strip()
        source_value = (
            value.get("source")
            or value.get("source_field")
            or value.get("field")
            or value.get("sources")
            or value.get("source_fields")
            or value.get("aliases")
        )

    if isinstance(source_value, str):
        sources = [source_value.strip()]
    elif isinstance(source_value, list):
        sources = []
        for item in source_value:
            if not isinstance(item, str) or not item.strip():
                raise MetricsConfigError(f"sources for field '{target}' must be non-empty strings")
            sources.append(item.strip())
    else:
        raise MetricsConfigError(
            f"mapping for field '{target}' must be a source string, list, or object"
        )

    if not sources or any(not source for source in sources):
        raise MetricsConfigError(f"mapping for field '{target}' must contain at least one source")
    return sources, inline_unit


def _parse_groups(value: Any) -> dict[str, str]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise MetricsConfigError("field 'groups' must be an object")

    groups: dict[str, str] = {}
    for key, group_value in value.items():
        if not isinstance(key, str) or not key.strip():
            raise MetricsConfigError("group names must be non-empty strings")
        if not isinstance(group_value, str) or not group_value.strip():
            raise MetricsConfigError(f"group '{key}' must be a non-empty string")
        groups[key.strip()] = group_value.strip()
    return groups
