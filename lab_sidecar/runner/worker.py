from __future__ import annotations

import argparse
from pathlib import Path

from lab_sidecar.runner.service import execute_task, load_run_spec_json


def main() -> None:
    parser = argparse.ArgumentParser(description="Internal Lab-Sidecar task worker.")
    parser.add_argument("--root", required=True)
    parser.add_argument("--task-id", required=True)
    command_group = parser.add_mutually_exclusive_group(required=True)
    command_group.add_argument("--run-spec")
    command_group.add_argument("--command")
    parser.add_argument("--cwd", required=True)
    args = parser.parse_args()

    command = load_run_spec_json(args.run_spec) if args.run_spec is not None else args.command
    execute_task(
        root=Path(args.root),
        task_id=args.task_id,
        command=command,
        run_cwd=Path(args.cwd),
    )


if __name__ == "__main__":
    main()
