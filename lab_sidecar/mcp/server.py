from __future__ import annotations

from pathlib import Path
from typing import Any

from lab_sidecar.mcp.tools import LabSidecarMCPTools


def create_server(root: str | Path | None = None) -> Any:
    """Create an MCP SDK server when the optional SDK is installed."""
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError as exc:
        raise RuntimeError(
            "The optional MCP SDK is not installed. Install the 'mcp' package to run the stdio server; "
            "the LabSidecarMCPTools adapter remains available for local smoke tests."
        ) from exc

    workspace = Path(root or Path.cwd()).resolve()
    tools = LabSidecarMCPTools(workspace)
    server = FastMCP("lab-sidecar")

    server.tool()(tools.run_experiment)
    server.tool()(tools.inspect_results)
    server.tool()(tools.make_figures)
    server.tool()(tools.generate_report_fragment)
    server.tool()(tools.generate_slides)
    return server


def main() -> None:
    server = create_server(Path.cwd())
    server.run()


if __name__ == "__main__":
    main()
