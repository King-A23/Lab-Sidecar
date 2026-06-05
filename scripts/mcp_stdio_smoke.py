from __future__ import annotations

import argparse
import asyncio
import json
import shutil
import sys
import time
from pathlib import Path
from typing import Any

from lab_sidecar.core.config import init_workspace

PROJECT_ROOT = Path(__file__).resolve().parents[1]
MARKER_FILE = ".lab-sidecar-mcp-stdio-smoke"


def _example_command(workspace: Path) -> str:
    script = workspace / "examples" / "simple-success" / "train.py"
    return f'"{sys.executable}" "{script}" --output metrics.csv'


def _cancel_command(workspace: Path) -> str:
    script = workspace / "cancel_me.py"
    if not script.exists():
        script.write_text(
            "\n".join(
                [
                    "import time",
                    "print('cancel-ready', flush=True)",
                    "time.sleep(30)",
                ]
            )
            + "\n",
            encoding="utf-8",
        )
    return f'"{sys.executable}" "{script}"'


async def _run_smoke(workspace: Path) -> dict[str, Any]:
    try:
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client
    except ImportError as exc:
        raise RuntimeError("Install MCP support first: py -3 -m pip install -e .[mcp]") from exc

    server_params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "lab_sidecar.mcp.server"],
        cwd=str(workspace),
    )
    server_log_path = workspace / "mcp-server.stderr.log"

    with server_log_path.open("w", encoding="utf-8") as server_err:
        async with stdio_client(server_params, errlog=server_err) as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                listed = await session.list_tools()
                tool_names = sorted(tool.name for tool in listed.tools)

                run_result = await _call_tool(
                    session,
                    "run_experiment",
                    {
                        "command": _example_command(workspace),
                        "background": True,
                    },
                    timeout=30,
                )
                task_id = run_result["task_id"]
                inspect_result = await _wait_for_completed(session, task_id)
                figures_result = await _call_tool(session, "make_figures", {"task_id": task_id}, timeout=90)
                report_result = await _call_tool(
                    session,
                    "generate_report_fragment",
                    {"task_id": task_id},
                    timeout=60,
                )
                slides_result = await _call_tool(session, "generate_slides", {"task_id": task_id}, timeout=90)
                cancel_run_result = await _call_tool(
                    session,
                    "run_experiment",
                    {
                        "command": _cancel_command(workspace),
                        "background": True,
                    },
                    timeout=30,
                )
                cancel_task_id = cancel_run_result["task_id"]
                await asyncio.sleep(1)
                cancel_result = await _call_tool(
                    session,
                    "cancel_experiment",
                    {"task_id": cancel_task_id},
                    timeout=30,
                )
                blocked_result = await _call_tool(
                    session,
                    "run_experiment",
                    {
                        "command": "Remove-Item -Recurse .",
                        "background": True,
                    },
                    timeout=30,
                )

    expected = {
        "run_experiment",
        "inspect_results",
        "cancel_experiment",
        "make_figures",
        "generate_report_fragment",
        "generate_slides",
    }
    missing = sorted(expected.difference(tool_names))
    if missing:
        raise RuntimeError(f"MCP server did not expose expected tools: {missing}")
    if run_result.get("task_status") != "running":
        raise RuntimeError(f"run_experiment did not return a running background task: {run_result}")
    if inspect_result.get("task_status") != "completed":
        raise RuntimeError(f"background task did not complete: {inspect_result}")
    if inspect_result.get("summary", {}).get("metrics", {}).get("row_count") != 5:
        raise RuntimeError(f"inspect_results did not report 5 metric rows: {inspect_result}")
    if figures_result.get("summary", {}).get("figure_count", 0) < 1:
        raise RuntimeError(f"make_figures did not generate figures: {figures_result}")
    if report_result.get("summary", {}).get("preview") is not None:
        raise RuntimeError("generate_report_fragment returned a report preview by default")
    if slides_result.get("summary", {}).get("slide_count", 0) < 1:
        raise RuntimeError(f"generate_slides did not generate slides: {slides_result}")
    if cancel_run_result.get("task_status") != "running":
        raise RuntimeError(f"cancel smoke task did not start in background: {cancel_run_result}")
    if cancel_result.get("task_status") != "cancelled":
        raise RuntimeError(f"cancel_experiment did not cancel task: {cancel_result}")
    if blocked_result.get("summary", {}).get("status") != "blocked":
        raise RuntimeError(f"destructive command was not blocked: {blocked_result}")

    return {
        "workspace": str(workspace),
        "server_log": str(server_log_path),
        "tools": tool_names,
        "task_id": task_id,
        "run_status": run_result["task_status"],
        "final_status": inspect_result["task_status"],
        "metrics_rows": inspect_result["summary"]["metrics"]["row_count"],
        "figure_count": figures_result["summary"]["figure_count"],
        "report_path": report_result["summary"]["report_path"],
        "slide_count": slides_result["summary"]["slide_count"],
        "slide_qa_checks": slides_result["summary"].get("qa_checks", {}),
        "cancel_task_id": cancel_task_id,
        "cancel_status": cancel_result["task_status"],
        "blocked_command_status": blocked_result["summary"]["status"],
        "omitted_contract": slides_result["omitted"],
        "artifact_count": len(slides_result["artifacts"]),
    }


async def _wait_for_completed(session: Any, task_id: str) -> dict[str, Any]:
    deadline = time.time() + 90
    latest: dict[str, Any] | None = None
    while time.time() < deadline:
        latest = await _call_tool(
            session,
            "inspect_results",
            {"task_id": task_id, "collect_metrics": True},
            timeout=30,
        )
        if latest.get("task_status") in {"completed", "failed", "cancelled"}:
            return latest
        await asyncio.sleep(0.5)
    raise RuntimeError(f"background task did not finish before timeout: {latest}")


async def _call_tool(
    session: Any,
    name: str,
    arguments: dict[str, Any],
    timeout: float = 60,
) -> dict[str, Any]:
    result = await asyncio.wait_for(session.call_tool(name, arguments), timeout=timeout)
    text_parts = [part.text for part in result.content if getattr(part, "type", None) == "text"]
    if not text_parts:
        raise RuntimeError(f"tool {name} returned no text content")
    return json.loads(text_parts[0])


def _prepare_workspace(path: Path) -> Path:
    workspace = path.resolve()
    if workspace.exists():
        marker_path = workspace / MARKER_FILE
        has_existing_content = any(workspace.iterdir())
        if has_existing_content and not marker_path.is_file():
            raise RuntimeError(
                f"refusing to remove existing workspace without {MARKER_FILE} marker: {workspace}"
            )
        if has_existing_content:
            shutil.rmtree(workspace)
    workspace.mkdir(parents=True, exist_ok=True)
    (workspace / MARKER_FILE).write_text("temporary Lab-Sidecar MCP stdio smoke workspace\n", encoding="utf-8")
    shutil.copytree(PROJECT_ROOT / "examples", workspace / "examples")
    init_workspace(workspace)
    return workspace


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a real stdio MCP client smoke against Lab-Sidecar.")
    parser.add_argument(
        "--workspace",
        type=Path,
        default=Path.cwd() / ".tmp" / "mcp-stdio-smoke",
        help="Temporary workspace to create and use for the smoke.",
    )
    args = parser.parse_args()

    workspace = _prepare_workspace(args.workspace)
    result = asyncio.run(_run_smoke(workspace))
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
