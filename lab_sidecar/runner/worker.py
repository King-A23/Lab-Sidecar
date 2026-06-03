from __future__ import annotations

import argparse
from pathlib import Path

from lab_sidecar.runner.service import execute_task


def main() -> None:
    parser = argparse.ArgumentParser(description="Internal Lab-Sidecar task worker.")
    parser.add_argument("--root", required=True)
    parser.add_argument("--task-id", required=True)
    parser.add_argument("--command", required=True)
    parser.add_argument("--cwd", required=True)
    args = parser.parse_args()

    execute_task(
        root=Path(args.root),
        task_id=args.task_id,
        command=args.command,
        run_cwd=Path(args.cwd),
    )


if __name__ == "__main__":
    main()
