from __future__ import annotations

import re


COMMON_METRIC_FIELDS = {
    "epoch",
    "step",
    "loss",
    "accuracy",
    "precision",
    "recall",
    "f1",
    "latency",
    "memory",
    "score",
    "util",
    "utilization",
    "timeout",
    "duration",
    "packet",
    "packets",
    "error",
    "errors",
    "seed",
    "model",
    "method",
}

FIELD_ALIASES = {
    "algorithm": "method",
    "runtime": "latency",
    "avgutil": "utilization",
    "autil": "utilization",
    "butil": "utilization",
    "durationsec": "duration",
    "wallseconds": "duration",
    "datatimeoutpermin": "timeout",
    "datatimeouttotal": "timeout",
    "acktimeouttotal": "timeout",
    "sendacktotal": "packets",
    "sendnaktotal": "packets",
    "badcrctotal": "errors",
}


def detect_metric_fields(field_names: list[str]) -> list[str]:
    detected: list[str] = []
    for field_name in field_names:
        if is_metric_field(field_name):
            detected.append(field_name)
    return detected


def is_metric_field(field_name: str) -> bool:
    normalized = field_name.strip().lower()
    if normalized in COMMON_METRIC_FIELDS or normalized in FIELD_ALIASES:
        return True
    tokens = [token for token in re.split(r"[^a-z0-9]+", normalized) if token]
    return any(token in COMMON_METRIC_FIELDS or token in FIELD_ALIASES for token in tokens)
