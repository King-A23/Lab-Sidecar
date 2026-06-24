from __future__ import annotations

from lab_sidecar.core.models import ArtifactRecord, TaskRecord


def upsert_artifact(record: TaskRecord, artifact: ArtifactRecord) -> None:
    """Register one artifact in the task manifest, replacing an older entry."""
    record.artifacts = [item for item in record.artifacts if item.artifact_id != artifact.artifact_id]
    record.artifacts.append(artifact)
