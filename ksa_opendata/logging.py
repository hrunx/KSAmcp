"""Logging helpers used throughout the MCP service."""

from __future__ import annotations

import logging
import sys


def configure_logging() -> None:
    """Configure structured logging for the MCP server."""
    handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter(
        fmt="%(asctime)s %(levelname)s [%(name)s] %(message)s", datefmt="%Y-%m-%dT%H:%M:%SZ"
    )
    handler.setFormatter(formatter)
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.handlers[:] = [handler]
