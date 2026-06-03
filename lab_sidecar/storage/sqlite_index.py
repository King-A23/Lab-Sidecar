from __future__ import annotations

import sqlite3
from pathlib import Path

from lab_sidecar.core.paths import sqlite_path


def ensure_index(root: Path) -> None:
    path = sqlite_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS tasks (
              task_id TEXT PRIMARY KEY,
              mode TEXT NOT NULL,
              status TEXT NOT NULL,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL,
              working_dir TEXT NOT NULL,
              command TEXT,
              source_path TEXT,
              exit_code INTEGER
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS artifacts (
              task_id TEXT NOT NULL,
              artifact_id TEXT NOT NULL,
              type TEXT NOT NULL,
              path TEXT NOT NULL,
              description TEXT NOT NULL,
              PRIMARY KEY (task_id, artifact_id)
            )
            """
        )
        conn.commit()
    finally:
        conn.close()


def upsert_task(root: Path, record) -> None:
    ensure_index(root)
    conn = sqlite3.connect(sqlite_path(root))
    try:
        conn.execute(
            """
            INSERT INTO tasks (
              task_id, mode, status, created_at, updated_at,
              working_dir, command, source_path, exit_code
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(task_id) DO UPDATE SET
              mode=excluded.mode,
              status=excluded.status,
              created_at=excluded.created_at,
              updated_at=excluded.updated_at,
              working_dir=excluded.working_dir,
              command=excluded.command,
              source_path=excluded.source_path,
              exit_code=excluded.exit_code
            """,
            (
                record.task_id,
                record.mode,
                record.status.value,
                record.created_at,
                record.updated_at,
                record.working_dir,
                record.command,
                record.source_path,
                record.exit_code,
            ),
        )
        conn.execute("DELETE FROM artifacts WHERE task_id = ?", (record.task_id,))
        conn.executemany(
            """
            INSERT INTO artifacts (task_id, artifact_id, type, path, description)
            VALUES (?, ?, ?, ?, ?)
            """,
            [
                (
                    record.task_id,
                    artifact.artifact_id,
                    artifact.type,
                    artifact.path,
                    artifact.description,
                )
                for artifact in record.artifacts
            ],
        )
        conn.commit()
    finally:
        conn.close()
