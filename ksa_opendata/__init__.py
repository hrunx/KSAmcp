"""Core package for the KSA Open Data MCP server."""

from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _version

try:
    __version__ = _version("ksa-opendata-mcp")
except PackageNotFoundError:
    __version__ = "0.0.0"
