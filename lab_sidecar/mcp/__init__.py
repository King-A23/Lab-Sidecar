"""MCP-facing tool adapters for Lab-Sidecar.

The package keeps MCP integration as a thin layer over the existing services.
"""

__all__ = ["LabSidecarMCPTools"]


def __getattr__(name: str):
    if name == "LabSidecarMCPTools":
        from lab_sidecar.mcp.tools import LabSidecarMCPTools

        return LabSidecarMCPTools
    raise AttributeError(name)
