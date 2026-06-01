"""Personal asset aggregation MCP server."""

from importlib.metadata import PackageNotFoundError, version

__all__ = ["__version__"]

try:
    __version__ = version("asset-mcp")
except PackageNotFoundError:
    __version__ = "0.1.1"
