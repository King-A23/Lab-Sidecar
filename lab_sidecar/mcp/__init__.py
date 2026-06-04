"""MCP-facing tool adapters for Lab-Sidecar.

The package keeps MCP integration as a thin layer over the existing services.
"""

from lab_sidecar.mcp.tools import LabSidecarMCPTools

__all__ = ["LabSidecarMCPTools"]
