from __future__ import annotations

from typing import Any

from lab_sidecar.intelligence.worker_invocation import SidecarWorker, WorkerInvocation, WorkerRequest, WorkerResult

__all__ = [
    "SidecarWorker",
    "cancel_sidecar_task",
    "delegate_experiment_artifacts",
    "inspect_sidecar_task",
    "preview_sidecar_artifact",
    "WorkerInvocation",
    "WorkerRequest",
    "WorkerResult",
]


def __getattr__(name: str) -> Any:
    if name in {
        "cancel_sidecar_task",
        "delegate_experiment_artifacts",
        "inspect_sidecar_task",
        "preview_sidecar_artifact",
    }:
        from lab_sidecar.intelligence.tools import (
            cancel_sidecar_task,
            delegate_experiment_artifacts,
            inspect_sidecar_task,
            preview_sidecar_artifact,
        )

        exports = {
            "cancel_sidecar_task": cancel_sidecar_task,
            "delegate_experiment_artifacts": delegate_experiment_artifacts,
            "inspect_sidecar_task": inspect_sidecar_task,
            "preview_sidecar_artifact": preview_sidecar_artifact,
        }
        return exports[name]
    raise AttributeError(name)
