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
    field_mappings: tuple[FieldMapping, ...] = ()
    units: dict[str, str] = field(default_factory=dict)

    @property
    def has_explicit_sources(self) -> bool:
        return bool(self.sources)

    @property
    def has_field_mappings(self) -> bool:
        return bool(self.field_mappings)

    def to_summary(self) -> dict[str, object]:
        return {
            "sources": list(self.sources),
            "field_mappings": [item.to_summary() for item in self.field_mappings],
            "units": dict(self.units),
        }


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

    units = _parse_units(data.get("units"))
    field_mappings = _parse_field_mappings(data, units)
    return MetricsCollectionConfig(
        path=resolved,
        sources=tuple(_parse_sources(data)),
        field_mappings=tuple(field_mappings),
        units={mapping.target: mapping.unit for mapping in field_mappings if mapping.unit},
    )


def _parse_sources(data: dict[str, Any]) -> list[str]:
    value = data.get("sources", data.get("source_files"))
    if value is None:
        return []

    if isinstance(value, str):
        items: list[Any] = [value]
    elif isinstance(value, list):
        items = value
    else:
        raise MetricsConfigError("field 'sources' must be a string or list")

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


def _parse_field_mappings(data: dict[str, Any], units: dict[str, str]) -> list[FieldMapping]:
    merged: dict[str, Any] = {}
    for key in ["fields", "field_mapping", "metrics", "aliases"]:
        value = data.get(key)
        if value is None:
            continue
        if not isinstance(value, dict):
            raise MetricsConfigError(f"field '{key}' must be an object")
        merged.update(value)

    mappings: list[FieldMapping] = []
    for target, value in merged.items():
        if not isinstance(target, str) or not target.strip():
            raise MetricsConfigError("mapped field names must be non-empty strings")
        target_name = target.strip()
        sources, inline_unit = _parse_mapping_sources(target_name, value)
        unit = inline_unit or units.get(target_name)
        mappings.append(FieldMapping(target=target_name, sources=tuple(sources), unit=unit))
    return mappings


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
